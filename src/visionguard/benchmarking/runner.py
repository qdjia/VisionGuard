"""Module and pipeline benchmark runners with honest batch capability labels."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import numpy as np

from visionguard.benchmarking.config import BenchmarkConfig
from visionguard.benchmarking.memory import empty_cuda_cache, is_cuda_oom
from visionguard.benchmarking.profiler import environment_snapshot, profile_operation
from visionguard.benchmarking.schemas import (
    BatchMode,
    BenchmarkRecord,
    BenchmarkStatus,
    BenchmarkSummary,
    ModuleTimingBreakdown,
)
from visionguard.benchmarking.statistics import latency_statistics, throughput
from visionguard.fusion import build_fusion_signals
from visionguard.pipeline.exceptions import safe_error
from visionguard.pipeline.schemas import (
    ArtifactState,
    ArtifactStatus,
    ModuleState,
    PipelineTiming,
    ReviewImage,
    ReviewMetadata,
    ReviewModuleStatus,
    ReviewResult,
)
from visionguard.routing.schemas import DecisionSource, Route, RoutingReasonCode
from visionguard.utils.image import ImageInput, load_image
from visionguard.vlm import build_context


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_image(image: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str((image.shape, image.dtype)).encode())
    digest.update(image.tobytes())
    return digest.hexdigest()


def _status_map() -> dict[str, ReviewModuleStatus]:
    return {
        name: ReviewModuleStatus(
            status=ModuleState.SKIPPED,
            error_message="disabled by pipeline configuration",
        )
        for name in ("detector", "ocr", "baseline", "vlm")
    }


def _success(latency_ms: float) -> ReviewModuleStatus:
    return ReviewModuleStatus(status=ModuleState.SUCCESS, started_at=_now(), latency_ms=latency_ms)


def _failed(exc: BaseException, latency_ms: float) -> ReviewModuleStatus:
    error_type, error_message = safe_error(exc)
    return ReviewModuleStatus(
        status=ModuleState.FAILED,
        started_at=_now(),
        latency_ms=latency_ms,
        error_type=error_type,
        error_message=error_message,
    )


class BatchReviewRunner:
    """Stage-wise mixed batching with selective, currently sequential, VLM calls."""

    batch_mode = BatchMode.MIXED

    def __init__(self, pipeline) -> None:
        self.pipeline = pipeline

    def run(self, sources: Sequence[ImageInput]) -> list[ReviewResult]:
        if not sources:
            return []
        batch_started = perf_counter()
        images: list[np.ndarray] = []
        image_info: list[ReviewImage] = []
        image_load_ms: list[float] = []
        for source in sources:
            started = perf_counter()
            image = load_image(source)
            elapsed = (perf_counter() - started) * 1000
            height, width = image.shape[:2]
            images.append(image)
            image_load_ms.append(elapsed)
            image_info.append(
                ReviewImage(
                    input_type="path" if isinstance(source, (str, Path)) else "ndarray",
                    source_path=(
                        str(Path(source).expanduser().resolve())
                        if isinstance(source, (str, Path))
                        else None
                    ),
                    width=width,
                    height=height,
                    sha256=_hash_image(image),
                )
            )

        count = len(images)
        statuses = [_status_map() for _ in images]
        detections: list[Any | None] = [None] * count
        ocr_results: list[Any | None] = [None] * count
        baselines: list[Any | None] = [None] * count
        vlm_results: list[Any | None] = [None] * count
        detector_ms = [0.0] * count
        ocr_ms = [0.0] * count
        baseline_ms = [0.0] * count
        routing_ms = [0.0] * count
        context_ms = [0.0] * count
        vlm_ms = [0.0] * count
        fusion_ms = [0.0] * count

        if self.pipeline.config.enable_detector:
            started = perf_counter()
            try:
                predictor = getattr(self.pipeline.detector, "predict_batch", None)
                if predictor is None:
                    output = [self.pipeline.detector.predict(image) for image in images]
                else:
                    output = predictor(images)
                elapsed = (perf_counter() - started) * 1000 / count
                for index, value in enumerate(output):
                    detections[index] = value
                    detector_ms[index] = elapsed
                    statuses[index]["detector"] = _success(elapsed)
            except Exception as exc:
                elapsed = (perf_counter() - started) * 1000 / count
                for index in range(count):
                    detector_ms[index] = elapsed
                    statuses[index]["detector"] = _failed(exc, elapsed)

        if self.pipeline.config.enable_ocr:
            for index, image in enumerate(images):
                started = perf_counter()
                try:
                    ocr_results[index] = self.pipeline.ocr_engine.recognize(image)
                    ocr_ms[index] = (perf_counter() - started) * 1000
                    statuses[index]["ocr"] = _success(ocr_ms[index])
                except Exception as exc:
                    ocr_ms[index] = (perf_counter() - started) * 1000
                    statuses[index]["ocr"] = _failed(exc, ocr_ms[index])

        if self.pipeline.config.enable_text_baseline:
            eligible = [
                index
                for index, value in enumerate(ocr_results)
                if value is not None and value.full_text.strip()
            ]
            for index in range(count):
                if ocr_results[index] is None:
                    statuses[index]["baseline"] = ReviewModuleStatus(
                        status=ModuleState.SKIPPED, error_message="OCR result unavailable"
                    )
                elif not ocr_results[index].full_text.strip():
                    statuses[index]["baseline"] = ReviewModuleStatus(
                        status=ModuleState.SKIPPED, error_message="empty OCR text"
                    )
            if eligible:
                texts = [
                    ocr_results[index].full_text[: self.pipeline.config.max_ocr_chars_for_baseline]
                    for index in eligible
                ]
                started = perf_counter()
                try:
                    predictor = getattr(self.pipeline.text_baseline, "predict_batch", None)
                    output = (
                        predictor(texts)
                        if predictor is not None
                        else [self.pipeline.text_baseline.predict(text) for text in texts]
                    )
                    elapsed = (perf_counter() - started) * 1000 / len(eligible)
                    for index, value in zip(eligible, output, strict=True):
                        baselines[index] = value
                        baseline_ms[index] = elapsed
                        statuses[index]["baseline"] = _success(elapsed)
                except Exception as exc:
                    elapsed = (perf_counter() - started) * 1000 / len(eligible)
                    for index in eligible:
                        baseline_ms[index] = elapsed
                        statuses[index]["baseline"] = _failed(exc, elapsed)

        routings = []
        routing_signals = []
        for index in range(count):
            started = perf_counter()
            signals = self.pipeline._build_routing_signals(
                detections[index], ocr_results[index], baselines[index], statuses[index]
            )
            routing = self.pipeline._decide_route(signals)
            if routing.route == Route.FAST_PATH:
                guard_started = perf_counter()
                guard_signals = build_fusion_signals(
                    detections[index],
                    ocr_results[index],
                    baselines[index],
                    None,
                    routing,
                    statuses[index],
                    self.pipeline.fusion_engine.config,
                )
                guard = self.pipeline.fusion_engine.decide(guard_signals)
                fusion_ms[index] += (perf_counter() - guard_started) * 1000
                if guard.risk_level != "low":
                    reasons = [*routing.reason_codes, RoutingReasonCode.FUSION_SAFETY_GUARD]
                    update: dict[str, Any] = {
                        "reason_codes": list(dict.fromkeys(reasons)),
                        "explanation": routing.explanation
                        + " Fusion safety guard rejected the low-risk fast path.",
                        "routing_overridden_by_fusion": True,
                        "original_route": routing.route,
                    }
                    if self.pipeline.config.enable_vlm:
                        update.update({"route": Route.VLM_PATH, "call_vlm": True})
                    routing = routing.model_copy(update=update)
            routing_ms[index] = (perf_counter() - started) * 1000
            routings.append(routing)
            routing_signals.append(signals)

        for index, (image, routing) in enumerate(zip(images, routings, strict=True)):
            if routing.call_vlm and self.pipeline.config.enable_vlm:
                started = perf_counter()
                try:
                    context_started = perf_counter()
                    context = build_context(detections[index], ocr_results[index], baselines[index])
                    context_ms[index] = (perf_counter() - context_started) * 1000
                    vlm_results[index] = self.pipeline.vlm_provider.analyze(
                        image, context, self.pipeline.policy
                    )
                    vlm_ms[index] = (perf_counter() - started) * 1000
                    statuses[index]["vlm"] = _success(vlm_ms[index])
                except Exception as exc:
                    vlm_ms[index] = (perf_counter() - started) * 1000
                    statuses[index]["vlm"] = _failed(exc, vlm_ms[index])
            elif self.pipeline.config.enable_vlm:
                statuses[index]["vlm"] = ReviewModuleStatus(
                    status=ModuleState.SKIPPED, error_message="skipped by routing policy"
                )

        results: list[ReviewResult] = []
        for index in range(count):
            signals = routing_signals[index].model_copy(
                update={
                    "vlm_confidence": (
                        vlm_results[index].confidence_score if vlm_results[index] else None
                    ),
                    "vlm_requires_manual_review": (
                        vlm_results[index].requires_manual_review if vlm_results[index] else None
                    ),
                }
            )
            routing = routings[index].model_copy(update={"signals": signals})
            started = perf_counter()
            fusion_signals = build_fusion_signals(
                detections[index],
                ocr_results[index],
                baselines[index],
                vlm_results[index],
                routing,
                statuses[index],
                self.pipeline.fusion_engine.config,
            )
            fusion = self.pipeline.fusion_engine.decide(fusion_signals)
            fusion_ms[index] += (perf_counter() - started) * 1000
            timing = PipelineTiming(
                image_load_ms=image_load_ms[index],
                detector_ms=detector_ms[index],
                ocr_ms=ocr_ms[index],
                baseline_ms=baseline_ms[index],
                routing_ms=routing_ms[index],
                context_build_ms=context_ms[index],
                vlm_ms=vlm_ms[index],
                fusion_ms=fusion_ms[index],
                aggregation_ms=fusion_ms[index],
                total_ms=0,
            )
            results.append(
                ReviewResult(
                    run_id=uuid4().hex,
                    image=image_info[index],
                    detection=detections[index],
                    ocr=ocr_results[index],
                    baseline=baselines[index],
                    vlm=vlm_results[index],
                    final=fusion,
                    review_status=self.pipeline._review_status(statuses[index]),
                    decision_source=DecisionSource.FUSION,
                    routing=routing,
                    fusion=fusion,
                    module_status=statuses[index],
                    timing=timing,
                    routing_signals=signals,
                    artifacts=ArtifactStatus(
                        status=ArtifactState.SKIPPED,
                        error_message="disabled for stage-wise batch benchmark",
                    ),
                    metadata=ReviewMetadata(
                        pipeline_version=self.pipeline.config.pipeline_version,
                        policy_version=self.pipeline.policy.version,
                        prompt_version=self.pipeline._vlm_config_value("prompt_version"),
                        routing_policy_version=routing.policy_version,
                        fusion_policy_version=self.pipeline.fusion_engine.version,
                        timestamp=_now(),
                        component_versions=self.pipeline._component_versions(
                            detections[index], ocr_results[index]
                        ),
                    ),
                )
            )
        elapsed_per_sample = (perf_counter() - batch_started) * 1000 / count
        for result in results:
            result.timing.total_ms = elapsed_per_sample
        return results


class BenchmarkRunner:
    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        startup_time_ms: float | None = None,
        startup_components_ms: dict[str, float] | None = None,
    ) -> None:
        self.config = config
        self.startup_time_ms = startup_time_ms
        self.startup_components_ms = startup_components_ms or {}

    def benchmark_operation(
        self,
        *,
        target: str,
        mode: str,
        batch_mode: BatchMode,
        batch_size: int,
        samples: Sequence[Any],
        operation: Callable[[Sequence[Any]], Any],
        measured_runs: int | None = None,
    ) -> tuple[list[BenchmarkRecord], float | None]:
        if not samples:
            raise ValueError("benchmark requires at least one sample")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        batch = self._batch(samples, batch_size)
        cold_ms = None
        if self.config.include_cold_start:
            try:
                cold_ms = self._invoke(operation, batch)[0]
            except Exception as exc:
                if not is_cuda_oom(exc):
                    raise
                empty_cuda_cache()
        for _ in range(self.config.warmup_runs):
            try:
                operation(batch)
            except Exception as exc:
                if not is_cuda_oom(exc):
                    raise
                empty_cuda_cache()
                break
        records = []
        for run_index in range(measured_runs or self.config.measured_runs):
            started_at = _now()
            try:
                elapsed_ms, memory, output = self._invoke(operation, batch)
                results = output if isinstance(output, list) else []
                timing = self._module_timing(results)
                vlm_called = sum(
                    bool(getattr(getattr(item, "routing", None), "call_vlm", False))
                    for item in results
                )
                manual = sum(
                    bool(getattr(getattr(item, "final", None), "requires_manual_review", False))
                    for item in results
                )
                failures = sum(
                    str(getattr(item, "review_status", "")) == "failed" for item in results
                )
                fast_latencies = [
                    self._result_stage_latency(item)
                    for item in results
                    if not bool(getattr(getattr(item, "routing", None), "call_vlm", False))
                ]
                vlm_latencies = [
                    self._result_stage_latency(item)
                    for item in results
                    if bool(getattr(getattr(item, "routing", None), "call_vlm", False))
                ]
                records.append(
                    BenchmarkRecord(
                        run_id=f"{target}-{batch_size}-{run_index}-{uuid4().hex[:8]}",
                        benchmark_type="pipeline" if target == "pipeline" else "module",
                        target=target,
                        mode=mode,
                        batch_mode=batch_mode,
                        batch_size=batch_size,
                        sample_count=len(batch),
                        total_latency_ms=elapsed_ms,
                        per_sample_latency_ms=elapsed_ms / len(batch),
                        throughput_images_per_second=throughput(len(batch), elapsed_ms),
                        memory=memory,
                        vlm_called=vlm_called,
                        selected_vlm_count=vlm_called,
                        vlm_call_rate=vlm_called / len(batch),
                        fast_path_sample_count=len(fast_latencies),
                        vlm_path_sample_count=len(vlm_latencies),
                        fast_path_mean_latency_ms=(
                            float(np.mean(fast_latencies)) if fast_latencies else None
                        ),
                        vlm_path_mean_latency_ms=(
                            float(np.mean(vlm_latencies)) if vlm_latencies else None
                        ),
                        manual_review_count=manual,
                        failure_count=failures,
                        module_timing=timing,
                        status=BenchmarkStatus.SUCCESS,
                        started_at=started_at,
                    )
                )
            except Exception as exc:
                oom = is_cuda_oom(exc)
                if oom:
                    empty_cuda_cache()
                records.append(
                    BenchmarkRecord(
                        run_id=f"{target}-{batch_size}-{run_index}-{uuid4().hex[:8]}",
                        benchmark_type="pipeline" if target == "pipeline" else "module",
                        target=target,
                        mode=mode,
                        batch_mode=batch_mode,
                        batch_size=batch_size,
                        sample_count=len(batch),
                        total_latency_ms=0,
                        per_sample_latency_ms=0,
                        throughput_images_per_second=0,
                        status=BenchmarkStatus.OOM if oom else BenchmarkStatus.ERROR,
                        error=f"{type(exc).__name__}: {exc}",
                        started_at=started_at,
                    )
                )
                if not oom:
                    raise
        return records, cold_ms

    def summarize(
        self, records: list[BenchmarkRecord], *, cold_inference_ms: float | None = None
    ) -> BenchmarkSummary:
        if not records:
            raise ValueError("cannot summarize empty records")
        successful = [record for record in records if record.status == BenchmarkStatus.SUCCESS]
        first = records[0]
        batch_values = [record.total_latency_ms for record in successful]
        sample_values = [record.per_sample_latency_ms for record in successful]
        sample_count = sum(record.sample_count for record in successful)
        elapsed = sum(batch_values)
        module_fields = tuple(ModuleTimingBreakdown.model_fields)
        module_means = {
            field: float(np.mean([getattr(item.module_timing, field) for item in successful]))
            if successful
            else 0.0
            for field in module_fields
        }
        module_total = sum(module_means.values())
        shares = {
            field.removesuffix("_ms"): value / module_total * 100 if module_total else 0.0
            for field, value in module_means.items()
        }
        peak_values = [
            item.memory.peak_allocated_mb
            for item in successful
            if item.memory.peak_allocated_mb is not None
        ]
        total_vlm = sum(item.vlm_called for item in successful)
        total_manual = sum(item.manual_review_count for item in successful)
        total_failures = sum(item.failure_count for item in successful)
        return BenchmarkSummary(
            experiment_name=self.config.experiment_name,
            target=first.target,
            mode=first.mode,
            batch_mode=first.batch_mode,
            batch_size=first.batch_size,
            sample_count=sample_count,
            successful_runs=len(successful),
            oom_runs=sum(item.status == BenchmarkStatus.OOM for item in records),
            failed_runs=sum(item.status == BenchmarkStatus.ERROR for item in records),
            batch_latency=latency_statistics(batch_values, self.config.percentiles),
            per_sample_latency=latency_statistics(sample_values, self.config.percentiles),
            throughput_images_per_second=throughput(sample_count, elapsed),
            peak_gpu_memory_mb=max(peak_values, default=None),
            vlm_call_rate=total_vlm / max(sample_count, 1),
            manual_review_rate=total_manual / max(sample_count, 1),
            failure_rate=total_failures / max(sample_count, 1),
            fast_path_mean_latency_ms=self._path_latency(successful, called=False),
            vlm_path_mean_latency_ms=self._path_latency(successful, called=True),
            module_mean_ms=ModuleTimingBreakdown(**module_means),
            module_share_percent=shares,
            startup_time_ms=self.startup_time_ms,
            startup_components_ms=self.startup_components_ms,
            cold_inference_ms=cold_inference_ms,
            environment=environment_snapshot(),
            dataset_kind=self.config.dataset_kind,
            limitations=[
                "OCR and VLM execute sequentially in the mixed pipeline batch.",
                "Results apply only to this hardware, software stack, and engineering dataset.",
            ],
        )

    def save(
        self,
        output: str | Path,
        records: list[BenchmarkRecord],
        summary: BenchmarkSummary,
    ) -> Path:
        output = Path(output).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=False)
        if self.config.save_raw_records:
            with (output / "records.jsonl").open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(record.model_dump_json() + "\n")
        (output / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        self._save_csv(output / "summary.csv", summary)
        return output

    def _invoke(self, operation, batch):
        with profile_operation(
            synchronize=self.config.synchronize_cuda,
            measure_gpu=self.config.measure_gpu_memory,
            measure_cpu=self.config.measure_cpu_memory,
        ) as profile:
            output = operation(batch)
        return profile.elapsed_ms, profile.memory, output

    def _batch(self, samples: Sequence[Any], batch_size: int) -> list[Any]:
        ordered = list(samples)
        if self.config.shuffle_samples:
            random.Random(self.config.seed).shuffle(ordered)
        return [ordered[index % len(ordered)] for index in range(batch_size)]

    @staticmethod
    def _module_timing(results: list[Any]) -> ModuleTimingBreakdown:
        if not results or not hasattr(getattr(results[0], "timing", None), "detector_ms"):
            return ModuleTimingBreakdown()
        return ModuleTimingBreakdown(
            **{
                field: float(np.mean([getattr(item.timing, source) for item in results]))
                for field, source in {
                    "image_load_ms": "image_load_ms",
                    "detector_ms": "detector_ms",
                    "ocr_ms": "ocr_ms",
                    "baseline_ms": "baseline_ms",
                    "routing_ms": "routing_ms",
                    "context_build_ms": "context_build_ms",
                    "vlm_ms": "vlm_ms",
                    "fusion_ms": "fusion_ms",
                    "artifact_ms": "artifact_save_ms",
                }.items()
            }
        )

    @staticmethod
    def _path_latency(records: list[BenchmarkRecord], *, called: bool) -> float | None:
        value_name = "vlm_path_mean_latency_ms" if called else "fast_path_mean_latency_ms"
        count_name = "vlm_path_sample_count" if called else "fast_path_sample_count"
        weighted = [
            (getattr(item, value_name), getattr(item, count_name))
            for item in records
            if getattr(item, value_name) is not None and getattr(item, count_name) > 0
        ]
        total = sum(count for _, count in weighted)
        if not total:
            return None
        return sum(float(value) * count for value, count in weighted) / total

    @staticmethod
    def _result_stage_latency(result: Any) -> float:
        timing = result.timing
        return sum(
            getattr(timing, field)
            for field in (
                "image_load_ms",
                "detector_ms",
                "ocr_ms",
                "baseline_ms",
                "routing_ms",
                "context_build_ms",
                "vlm_ms",
                "fusion_ms",
                "artifact_save_ms",
            )
        )

    @staticmethod
    def _save_csv(path: Path, summary: BenchmarkSummary) -> None:
        import csv

        row = {
            "experiment_name": summary.experiment_name,
            "target": summary.target,
            "mode": summary.mode,
            "batch_mode": summary.batch_mode,
            "batch_size": summary.batch_size,
            "mean_ms": summary.batch_latency.mean_ms,
            **summary.batch_latency.percentiles_ms,
            "throughput_images_per_second": summary.throughput_images_per_second,
            "peak_gpu_memory_mb": summary.peak_gpu_memory_mb,
            "vlm_call_rate": summary.vlm_call_rate,
            "manual_review_rate": summary.manual_review_rate,
            "failure_rate": summary.failure_rate,
        }
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)


def load_manifest(path: str | Path) -> list[Path]:
    source = Path(path).expanduser().resolve()
    images: list[Path] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        raw_path = value.get("image")
        if not raw_path:
            raise ValueError(f"manifest line {line_number} has no image")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = source.parent / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"manifest image does not exist: {candidate}")
        images.append(candidate)
    if not images:
        raise ValueError(f"manifest contains no samples: {source}")
    return images
