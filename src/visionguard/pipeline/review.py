"""Shared synchronous execution template for full and cascaded review pipelines."""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np

from visionguard.fusion import RiskFusionEngine, build_fusion_signals
from visionguard.moderation.policy import ModerationPolicy
from visionguard.pipeline.adapters import (
    DetectorProtocol,
    OCRProtocol,
    TextBaselineProtocol,
)
from visionguard.pipeline.artifacts import PipelineArtifactStore
from visionguard.pipeline.config import PipelineConfig
from visionguard.pipeline.exceptions import (
    ArtifactSaveError,
    PipelineExecutionError,
    PipelineFatalError,
    safe_error,
)
from visionguard.pipeline.schemas import (
    ArtifactState,
    ArtifactStatus,
    ModuleState,
    PipelineTiming,
    ReviewImage,
    ReviewMetadata,
    ReviewModuleStatus,
    ReviewResult,
    ReviewStatus,
)
from visionguard.routing.schemas import (
    DecisionSource,
    Route,
    RoutingDecision,
    RoutingReasonCode,
    RoutingSignals,
)
from visionguard.utils.image import ImageInput, load_image
from visionguard.vlm import VLMProvider, build_context

LOGGER = logging.getLogger(__name__)
MODULES = ("detector", "ocr", "baseline", "vlm")


def _now() -> datetime:
    return datetime.now(UTC)


def _image_hash(image: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str((image.shape, image.dtype)).encode())
    digest.update(image.tobytes())
    return digest.hexdigest()


class MultimodalReviewPipeline:
    """Orchestrate initialized models without owning their lifecycle or training."""

    def __init__(
        self,
        detector: DetectorProtocol | None,
        ocr_engine: OCRProtocol | None,
        text_baseline: TextBaselineProtocol | None,
        vlm_provider: VLMProvider | None,
        moderation_policy: ModerationPolicy,
        config: PipelineConfig,
        *,
        fusion_engine: RiskFusionEngine,
        artifact_store: PipelineArtifactStore | None = None,
    ) -> None:
        self.detector = detector
        self.ocr_engine = ocr_engine
        self.text_baseline = text_baseline
        self.vlm_provider = vlm_provider
        self.policy = moderation_policy
        self.config = config
        self.fusion_engine = fusion_engine
        self.artifact_store = artifact_store or PipelineArtifactStore(config)
        dependencies = {
            "detector": (config.enable_detector, detector),
            "ocr": (config.enable_ocr, ocr_engine),
            "baseline": (config.enable_text_baseline, text_baseline),
            "vlm": (config.enable_vlm, vlm_provider),
        }
        missing = [
            name
            for name, (enabled, dependency) in dependencies.items()
            if enabled and dependency is None
        ]
        if missing:
            raise ValueError(f"enabled pipeline dependencies are missing: {', '.join(missing)}")

    def run(self, source: ImageInput, *, save_artifacts: bool | None = None) -> ReviewResult:
        should_save_artifacts = (
            self.config.save_artifacts if save_artifacts is None else save_artifacts
        )
        run_id = uuid4().hex
        started = perf_counter()
        timestamp = _now()
        self._log(run_id, "pipeline started")
        try:
            image_started = perf_counter()
            image = load_image(source)
            height, width = image.shape[:2]
            image_info = ReviewImage(
                input_type="path" if isinstance(source, (str, Path)) else "ndarray",
                source_path=str(Path(source).expanduser().resolve())
                if isinstance(source, (str, Path))
                else None,
                width=width,
                height=height,
                sha256=_image_hash(image),
            )
            image_load_ms = (perf_counter() - image_started) * 1000
        except Exception as exc:
            LOGGER.exception("[run_id=%s] fatal image load failure", run_id)
            raise PipelineFatalError(
                f"pipeline input could not be loaded: {safe_error(exc)[1]}", run_id=run_id
            ) from exc

        statuses = {
            name: ReviewModuleStatus(
                status=ModuleState.SKIPPED,
                error_message="disabled by pipeline configuration",
            )
            for name in MODULES
        }
        detection = ocr = baseline = vlm = None

        if self.config.enable_detector:
            detection = self._execute(
                run_id, "detector", statuses, lambda: self.detector.predict(image)
            )
        if self.config.enable_ocr:
            ocr = self._execute(run_id, "ocr", statuses, lambda: self.ocr_engine.recognize(image))
        if self.config.enable_text_baseline:
            if ocr is None:
                statuses["baseline"] = ReviewModuleStatus(
                    status=ModuleState.SKIPPED,
                    error_message="OCR result unavailable",
                )
            elif not ocr.full_text.strip():
                statuses["baseline"] = ReviewModuleStatus(
                    status=ModuleState.SKIPPED,
                    error_message="empty OCR text",
                )
            else:
                baseline_text = ocr.full_text[: self.config.max_ocr_chars_for_baseline]
                baseline = self._execute(
                    run_id,
                    "baseline",
                    statuses,
                    lambda: self.text_baseline.predict(baseline_text),
                )

        routing_started = perf_counter()
        signals = self._build_routing_signals(detection, ocr, baseline, statuses)
        routing = self._decide_route(signals)
        routing_ms = (perf_counter() - routing_started) * 1000
        self._log(
            run_id,
            "routing=%s reasons=%s",
            routing.route,
            ",".join(routing.reason_codes),
        )

        fusion_ms = 0.0
        if routing.route == Route.FAST_PATH:
            guard_started = perf_counter()
            guard_signals = build_fusion_signals(
                detection,
                ocr,
                baseline,
                None,
                routing,
                statuses,
                self.fusion_engine.config,
            )
            guard_decision = self.fusion_engine.decide(guard_signals)
            fusion_ms += (perf_counter() - guard_started) * 1000
            if guard_decision.risk_level != "low":
                original_route = routing.route
                reason_codes = [
                    *routing.reason_codes,
                    RoutingReasonCode.FUSION_SAFETY_GUARD,
                ]
                update = {
                    "reason_codes": list(dict.fromkeys(reason_codes)),
                    "explanation": (
                        routing.explanation
                        + " Fusion safety guard rejected the low-risk fast path."
                    ),
                    "routing_overridden_by_fusion": True,
                    "original_route": original_route,
                }
                if self.config.enable_vlm:
                    update.update({"route": Route.VLM_PATH, "call_vlm": True})
                routing = routing.model_copy(update=update)
                self._log(
                    run_id,
                    "fusion safety guard override=%s pre_fusion_risk=%s",
                    self.config.enable_vlm,
                    guard_decision.risk_level,
                )

        context_ms = 0.0
        if routing.call_vlm and self.config.enable_vlm:
            context_started = perf_counter()
            context = build_context(detection, ocr, baseline)
            context_ms = (perf_counter() - context_started) * 1000
            vlm = self._execute(
                run_id,
                "vlm",
                statuses,
                lambda: self.vlm_provider.analyze(image, context, self.policy),
            )
        elif self.config.enable_vlm:
            statuses["vlm"] = ReviewModuleStatus(
                status=ModuleState.SKIPPED,
                error_message="skipped by routing policy",
            )

        signals = signals.model_copy(
            update={
                "vlm_confidence": vlm.confidence_score if vlm else None,
                "vlm_requires_manual_review": vlm.requires_manual_review if vlm else None,
            }
        )
        routing = routing.model_copy(update={"signals": signals})

        aggregation_started = perf_counter()
        fusion_started = perf_counter()
        fusion_signals = build_fusion_signals(
            detection,
            ocr,
            baseline,
            vlm,
            routing,
            statuses,
            self.fusion_engine.config,
        )
        fusion = self.fusion_engine.decide(fusion_signals)
        fusion_ms += (perf_counter() - fusion_started) * 1000
        final = fusion
        review_status = self._review_status(statuses)
        decision_source = DecisionSource.FUSION
        aggregation_ms = (perf_counter() - aggregation_started) * 1000
        timing = PipelineTiming(
            image_load_ms=image_load_ms,
            detector_ms=statuses["detector"].latency_ms,
            ocr_ms=statuses["ocr"].latency_ms,
            baseline_ms=statuses["baseline"].latency_ms,
            routing_ms=routing_ms,
            context_build_ms=context_ms,
            vlm_ms=statuses["vlm"].latency_ms,
            fusion_ms=fusion_ms,
            aggregation_ms=aggregation_ms,
            total_ms=(perf_counter() - started) * 1000,
        )
        result = ReviewResult(
            run_id=run_id,
            image=image_info,
            detection=detection,
            ocr=ocr,
            baseline=baseline,
            vlm=vlm,
            final=final,
            review_status=review_status,
            decision_source=decision_source,
            routing=routing,
            fusion=fusion,
            module_status=statuses,
            timing=timing,
            routing_signals=signals,
            artifacts=ArtifactStatus(
                status=ArtifactState.PENDING if should_save_artifacts else ArtifactState.SKIPPED,
                error_message=None if should_save_artifacts else "artifact saving disabled",
            ),
            metadata=ReviewMetadata(
                pipeline_version=self.config.pipeline_version,
                policy_version=self.policy.version,
                prompt_version=self._vlm_config_value("prompt_version"),
                routing_policy_version=routing.policy_version,
                fusion_policy_version=self.fusion_engine.version,
                timestamp=timestamp,
                component_versions=self._component_versions(detection, ocr),
            ),
        )
        if should_save_artifacts:
            artifact_started = perf_counter()
            try:
                expected = self.artifact_store.directory_for(run_id)
                result.artifacts = ArtifactStatus(
                    status=ArtifactState.SUCCESS,
                    directory=str(expected.resolve()),
                )
                directory = self.artifact_store.save(result, image)
                result.artifacts.directory = str(directory)
                result.timing.artifact_save_ms = (perf_counter() - artifact_started) * 1000
                result.timing.total_ms = (perf_counter() - started) * 1000
                self.artifact_store.refresh_result(directory, result)
            except ArtifactSaveError as exc:
                error_type, error_message = safe_error(exc.cause)
                result.artifacts = ArtifactStatus(
                    status=ArtifactState.FAILED,
                    directory=str(self.artifact_store.directory_for(run_id).resolve()),
                    error_type=error_type,
                    error_message=error_message,
                )
                result.timing.artifact_save_ms = (perf_counter() - artifact_started) * 1000
                result.timing.total_ms = (perf_counter() - started) * 1000
                LOGGER.exception("[run_id=%s] artifact persistence failed", run_id)
            except Exception as exc:
                error_type, error_message = safe_error(exc)
                result.artifacts = ArtifactStatus(
                    status=ArtifactState.FAILED,
                    error_type=error_type,
                    error_message=error_message,
                )
                result.timing.artifact_save_ms = (perf_counter() - artifact_started) * 1000
                result.timing.total_ms = (perf_counter() - started) * 1000
                LOGGER.exception("[run_id=%s] artifact adapter failed", run_id)
        else:
            result.timing.total_ms = (perf_counter() - started) * 1000
        self._log(
            run_id,
            "pipeline completed status=%s total_ms=%.2f",
            result.review_status,
            result.timing.total_ms,
        )
        return result

    def _execute(self, run_id, name, statuses, operation):
        stage_started = perf_counter()
        started_at = _now()
        self._log(run_id, "%s started", name)
        try:
            value = operation()
        except Exception as exc:
            latency = (perf_counter() - stage_started) * 1000
            error_type, error_message = safe_error(exc)
            statuses[name] = ReviewModuleStatus(
                status=ModuleState.FAILED,
                started_at=started_at,
                latency_ms=latency,
                error_type=error_type,
                error_message=error_message,
            )
            LOGGER.exception("[run_id=%s] %s failed", run_id, name)
            if self.config.fail_fast:
                raise PipelineExecutionError(
                    f"fail-fast stopped after {name} failed",
                    run_id=run_id,
                    module=name,
                    cause=exc,
                ) from exc
            return None
        latency = (perf_counter() - stage_started) * 1000
        statuses[name] = ReviewModuleStatus(
            status=ModuleState.SUCCESS,
            started_at=started_at,
            latency_ms=latency,
        )
        self._log(run_id, "%s completed in %.2f ms", name, latency)
        return value

    @staticmethod
    def _review_status(statuses):
        failures = [status for status in statuses.values() if status.status == ModuleState.FAILED]
        successful = any(status.status == ModuleState.SUCCESS for status in statuses.values())
        if failures:
            return ReviewStatus.PARTIAL if successful else ReviewStatus.FAILED
        return ReviewStatus.COMPLETED if successful else ReviewStatus.FAILED

    def _build_routing_signals(self, detection, ocr, baseline, statuses):
        detection_confidences = (
            [item.confidence for item in detection.detections] if detection else []
        )
        ocr_confidences = [item.confidence for item in ocr.blocks] if ocr else []
        original_chars = len(ocr.full_text) if ocr else 0
        return RoutingSignals(
            detection_count=len(detection_confidences),
            max_detection_confidence=max(detection_confidences, default=None),
            mean_detection_confidence=(
                sum(detection_confidences) / len(detection_confidences)
                if detection_confidences
                else None
            ),
            ocr_block_count=len(ocr_confidences),
            mean_ocr_confidence=sum(ocr_confidences) / len(ocr_confidences)
            if ocr_confidences
            else None,
            baseline_probability=baseline.probability if baseline else None,
            ocr_text_length=len(ocr.full_text.strip()) if ocr else 0,
            detector_status=str(statuses["detector"].status),
            ocr_status=str(statuses["ocr"].status),
            baseline_status=str(statuses["baseline"].status),
            ocr_text_truncated_for_baseline=(
                original_chars > self.config.max_ocr_chars_for_baseline
            ),
            baseline_input_chars=len(baseline.text) if baseline else 0,
        )

    def _decide_route(self, signals: RoutingSignals) -> RoutingDecision:
        return RoutingDecision(
            route=Route.FULL_PIPELINE,
            call_vlm=self.config.enable_vlm,
            reason_codes=[RoutingReasonCode.FULL_PIPELINE],
            explanation="Phase 7 full pipeline always calls VLM when it is enabled.",
            signals=signals,
            policy_version="full_pipeline_v1",
        )

    def _component_versions(self, detection, ocr):
        return {
            "detector_model": detection.model_name if detection else None,
            "ocr_engine": ocr.engine_name if ocr else None,
            "baseline_experiment": getattr(self.text_baseline, "experiment_name", None),
            "vlm_model": self._vlm_config_value("model_name_or_path"),
            "vlm_provider": self._vlm_config_value("provider"),
        }

    def _vlm_config_value(self, name):
        return getattr(getattr(self.vlm_provider, "config", None), name, None)

    def _log(self, run_id: str, message: str, *args) -> None:
        if self.config.trace.enabled:
            LOGGER.info("[run_id=%s] " + message, run_id, *args)
