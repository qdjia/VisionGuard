"""Conservative, deterministic failure attribution over stored pipeline evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from visionguard.error_analysis.config import ErrorAnalysisConfig
from visionguard.error_analysis.schemas import (
    AnnotationStatus,
    AttributionConfidence,
    AttributionResult,
    ErrorCase,
    ErrorPropagationTrace,
    FailureSeverity,
    GroundTruth,
    PropagationStep,
    SampleMetadata,
)
from visionguard.error_analysis.taxonomy import (
    PRIMARY_PRIORITY,
    FailureStage,
    FailureType,
    stage_for,
)
from visionguard.ocr.evaluator import character_error_rate

_RISK = {"low": 0, "medium": 1, "high": 2}


def _categories(value: Any) -> set[str]:
    values = value or []
    return {str(item.get("name")) if isinstance(item, dict) else str(item) for item in values}


def _final(record: dict) -> dict:
    result = record.get("result", {})
    return record.get("decision") or result.get("fusion") or result.get("final") or {}


def _result(record: dict) -> dict:
    return record.get("result", {})


def _image_hash(record: dict, image: str) -> str:
    value = _result(record).get("image", {}).get("sha256")
    if isinstance(value, str) and len(value) == 64:
        return value
    path = Path(image)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(image.encode("utf-8")).hexdigest()


def _primary(failures: list[FailureType]) -> FailureType:
    positions = {stage: index for index, stage in enumerate(PRIMARY_PRIORITY)}
    return min(
        failures, key=lambda failure: (positions[stage_for(failure)], failures.index(failure))
    )


def _append(values: list[FailureType], value: FailureType) -> None:
    if value not in values:
        values.append(value)


def _iou(left: dict, right: dict) -> float:
    x1, y1 = max(left["x1"], right["x1"]), max(left["y1"], right["y1"])
    x2, y2 = min(left["x2"], right["x2"]), min(left["y2"], right["y2"])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left["x2"] - left["x1"]) * (left["y2"] - left["y1"])
    right_area = (right["x2"] - right["x1"]) * (right["y2"] - right["y1"])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def attribute_record(
    record: dict,
    ground_truth: GroundTruth,
    metadata: SampleMetadata,
    config: ErrorAnalysisConfig,
) -> AttributionResult | None:
    """Return observed failures and explicitly separate unsupported causal hypotheses."""
    final = _final(record)
    result = _result(record)
    observed: list[FailureType] = []
    suspected: list[FailureType] = []
    expected, actual = ground_truth.risk_level, final.get("risk_level")

    if expected and actual and expected != actual:
        if expected in {"medium", "high"} and actual == "low":
            _append(observed, FailureType.FALSE_LOW)
        elif expected == "low" and actual in {"medium", "high"}:
            _append(observed, FailureType.FALSE_HIGH)
        else:
            _append(observed, FailureType.WRONG_RISK_LEVEL)
    if ground_truth.categories is not None:
        expected_categories = set(ground_truth.categories)
        actual_categories = _categories(final.get("categories"))
        if expected_categories - actual_categories:
            _append(observed, FailureType.MISSED_CATEGORY)
        if actual_categories - expected_categories:
            _append(observed, FailureType.EXTRA_CATEGORY)
        if (
            expected_categories
            and actual_categories
            and not expected_categories & actual_categories
        ):
            _append(observed, FailureType.WRONG_CATEGORY)
    manual = final.get("requires_manual_review")
    if ground_truth.requires_manual_review is not None and manual is not None:
        if ground_truth.requires_manual_review and not manual:
            _append(observed, FailureType.MISSED_MANUAL_REVIEW)
        elif not ground_truth.requires_manual_review and manual:
            _append(observed, FailureType.UNNECESSARY_MANUAL_REVIEW)

    review_status = result.get("review_status")
    if review_status == "partial":
        _append(observed, FailureType.PARTIAL_RESULT)
    elif review_status == "failed" or (record.get("error") and not result):
        _append(observed, FailureType.PIPELINE_FAILURE)
    for name, status in result.get("module_status", {}).items():
        if status.get("status") == "failed":
            _append(observed, FailureType.MODULE_FAILURE)
            message = f"{status.get('error_type', '')} {status.get('error_message', '')}".lower()
            if "out of memory" in message or "cuda oom" in message:
                _append(observed, FailureType.CUDA_OOM)
            elif "timeout" in message:
                _append(observed, FailureType.TIMEOUT)
            elif "load" in message:
                _append(observed, FailureType.MODEL_LOAD_FAILURE)
            elif "schema" in message or "validation" in message:
                _append(observed, FailureType.SCHEMA_FAILURE)
            elif "provider" in message:
                _append(observed, FailureType.PROVIDER_FAILURE)
            if name == "vlm" and ("parse" in message or "format" in message):
                _append(observed, FailureType.VLM_FORMAT_FAILURE)
            if name == "vlm" and "retr" in message:
                _append(observed, FailureType.VLM_RETRY_EXHAUSTED)
    if result.get("artifacts", {}).get("status") == "failed":
        _append(observed, FailureType.ARTIFACT_WRITE_FAILURE)

    routing = result.get("routing") or {}
    route = routing.get("route") or final.get("signals", {}).get("route")
    if expected in {"medium", "high"} and route == "fast_path":
        _append(
            observed,
            FailureType.UNSAFE_FAST_PASS if actual == "low" else FailureType.UNSAFE_ROUTE_ATTEMPT,
        )
    if routing.get("routing_overridden_by_fusion"):
        _append(observed, FailureType.ROUTING_OVERRIDE)
    reasons = set(routing.get("reason_codes", []))
    if "evidence_conflict" in reasons:
        _append(observed, FailureType.EVIDENCE_CONFLICT_ROUTE)
    if "module_failure" in reasons:
        _append(observed, FailureType.MODULE_FAILURE_ROUTE)
    if "insufficient_evidence" in reasons:
        _append(observed, FailureType.INSUFFICIENT_EVIDENCE_ROUTE)
    if route == "vlm_path" and expected == "low" and actual == "low":
        _append(observed, FailureType.POTENTIAL_UNNECESSARY_VLM)

    fusion_reasons = set(final.get("reason_codes", []))
    if "near_decision_boundary" in fusion_reasons:
        _append(observed, FailureType.NEAR_DECISION_BOUNDARY)
    if "evidence_conflict" in fusion_reasons:
        _append(observed, FailureType.FUSION_EVIDENCE_CONFLICT)
    has_fusion = bool(
        result.get("fusion")
        or final.get("decision_source") == "fusion"
        or ("signals" in final and "weights" in final)
    )
    if FailureType.FALSE_LOW in observed and has_fusion:
        _append(observed, FailureType.FUSION_FALSE_LOW)
    if FailureType.FALSE_HIGH in observed and has_fusion:
        _append(observed, FailureType.FUSION_FALSE_HIGH)

    ocr = result.get("ocr") or {}
    if ground_truth.text is not None:
        prediction = str(ocr.get("full_text", ""))
        cer = character_error_rate(prediction, ground_truth.text)
        if ground_truth.text and not prediction:
            _append(observed, FailureType.EMPTY_OCR)
            _append(observed, FailureType.MISSED_TEXT)
        elif not ground_truth.text and prediction:
            _append(observed, FailureType.HALLUCINATED_TEXT)
        elif cer >= config.cer_threshold:
            _append(observed, FailureType.SUSPICIOUS_OCR_OUTPUT)
            if len(prediction) == len(ground_truth.text):
                _append(observed, FailureType.OCR_SUBSTITUTION)
            elif len(prediction) < len(ground_truth.text):
                _append(observed, FailureType.OCR_DELETION)
            else:
                _append(observed, FailureType.OCR_INSERTION)
    else:
        blocks = ocr.get("blocks", [])
        confidences = [block.get("confidence", 0) for block in blocks]
        if confidences and sum(confidences) / len(confidences) < 0.5:
            _append(suspected, FailureType.LOW_CONFIDENCE_OCR)

    detections = (result.get("detection") or {}).get("detections", [])
    if ground_truth.objects is None:
        if any(
            item.get("confidence", 0) >= config.high_confidence_threshold for item in detections
        ):
            _append(suspected, FailureType.SUSPECTED_DETECTION_ISSUE)
    else:
        matched: set[int] = set()
        for expected_object in ground_truth.objects:
            expected_box = expected_object.bbox.model_dump()
            same_class = [
                (index, item, _iou(item["bbox"], expected_box))
                for index, item in enumerate(detections)
                if item.get("class_name") == expected_object.category
            ]
            best = max(same_class, key=lambda item: item[2], default=None)
            if best is None:
                cross_class = any(
                    _iou(item["bbox"], expected_box) >= config.detection_iou_threshold
                    for item in detections
                )
                _append(
                    observed,
                    FailureType.DETECTION_CLASS_MISMATCH
                    if cross_class
                    else FailureType.FALSE_NEGATIVE_DETECTION,
                )
            elif best[2] < config.detection_iou_threshold:
                _append(observed, FailureType.POOR_LOCALIZATION)
            else:
                matched.add(best[0])
                if best[1].get("confidence", 1) < 0.5:
                    _append(observed, FailureType.LOW_CONFIDENCE_TRUE_POSITIVE)
                overlaps = sum(
                    _iou(item["bbox"], expected_box) >= config.detection_iou_threshold
                    for _, item, _ in same_class
                )
                if overlaps > 1:
                    _append(observed, FailureType.DUPLICATE_DETECTION)
        extras = [item for index, item in enumerate(detections) if index not in matched]
        if extras:
            _append(observed, FailureType.FALSE_POSITIVE_DETECTION)
        if any(item.get("confidence", 0) >= config.high_confidence_threshold for item in extras):
            _append(observed, FailureType.HIGH_CONFIDENCE_FALSE_POSITIVE)

    baseline = result.get("baseline") or {}
    baseline_label = baseline.get("label")
    if expected and baseline_label:
        if expected == "low" and baseline_label == "sensitive":
            _append(observed, FailureType.BASELINE_FALSE_POSITIVE)
        elif expected in {"medium", "high"} and baseline_label == "safe":
            _append(observed, FailureType.BASELINE_FALSE_NEGATIVE)
        elif baseline_label == "uncertain":
            _append(observed, FailureType.BASELINE_UNCERTAIN)

    vlm = result.get("vlm") or {}
    if vlm:
        vlm_risk = vlm.get("risk_level")
        if expected in {"medium", "high"} and vlm_risk == "low":
            _append(observed, FailureType.VLM_FALSE_LOW)
        elif expected == "low" and vlm_risk in {"medium", "high"}:
            _append(observed, FailureType.VLM_FALSE_HIGH)
        vlm_categories = _categories(vlm.get("categories"))
        if ground_truth.categories is not None and set(ground_truth.categories) - vlm_categories:
            _append(observed, FailureType.VLM_MISSED_CATEGORY)
        if ground_truth.categories is not None and vlm_categories - set(ground_truth.categories):
            _append(observed, FailureType.VLM_EXTRA_CATEGORY)
        if vlm.get("reason") and not vlm.get("evidence") and vlm_risk != "low":
            _append(suspected, FailureType.UNSUPPORTED_REASON)
        text = str(ocr.get("full_text", "")).lower()
        if any(token in text for token in ("ignore previous", "system prompt", "忽略以上")):
            _append(suspected, FailureType.PROMPT_INJECTION_SUSPECTED)
        if expected and vlm_risk == expected and actual != expected:
            _append(observed, FailureType.CONFLICT_RESOLUTION_ERROR)
            _append(suspected, FailureType.BAD_WEIGHTING)

    if metadata.annotation_status == AnnotationStatus.AMBIGUOUS:
        _append(observed, FailureType.AMBIGUOUS_LABEL)
    if not observed and suspected:
        _append(observed, FailureType.ANNOTATION_REVIEW_REQUIRED)
    if not observed:
        return None
    primary = _primary(observed)
    confidence = (
        AttributionConfidence.HIGH
        if ground_truth.risk_level is not None
        and metadata.annotation_status == AnnotationStatus.VERIFIED
        else AttributionConfidence.MEDIUM
    )
    return AttributionResult(
        observed_failures=observed,
        suspected_causes=suspected,
        primary_failure=primary,
        secondary_failures=[failure for failure in observed if failure != primary],
        primary_stage=stage_for(primary),
        confidence=confidence,
    )


def build_error_case(
    record: dict,
    ground_truth: GroundTruth,
    metadata: SampleMetadata,
    config: ErrorAnalysisConfig,
) -> ErrorCase | None:
    attribution = attribute_record(record, ground_truth, metadata, config)
    if attribution is None:
        return None
    result = _result(record)
    final = _final(record)
    image = str(
        record.get("image_path")
        or result.get("image", {}).get("source_path")
        or record.get("image", "unknown")
    )
    image_hash = _image_hash(record, image)
    source_run_id = record.get("run_id") or result.get("run_id", "")
    case_id = hashlib.sha256(
        f"{image_hash}:{attribution.primary_failure.value}:{source_run_id}".encode()
    ).hexdigest()[:16]
    severity = config.severity.get(attribution.primary_failure.value, FailureSeverity.MEDIUM)
    steps = []
    for name, status in result.get("module_status", {}).items():
        steps.append(
            PropagationStep(
                stage=FailureStage.SYSTEM,
                observation=f"{name}: {status.get('status')}",
                evidence=status,
            )
        )
    if result.get("routing"):
        steps.append(
            PropagationStep(
                stage=FailureStage.ROUTING,
                observation="routing decision recorded",
                evidence=result["routing"],
            )
        )
    if result.get("fusion"):
        steps.append(
            PropagationStep(
                stage=FailureStage.FUSION,
                observation="fusion decision recorded",
                evidence={
                    "risk_level": final.get("risk_level"),
                    "risk_score": final.get("risk_score"),
                },
            )
        )
    outputs = {
        name: result.get(name)
        for name in ("detection", "ocr", "baseline", "vlm")
        if result.get(name) is not None
    }
    return ErrorCase(
        case_id=case_id,
        run_id=result.get("run_id") or record.get("run_id"),
        image=image,
        image_hash=image_hash,
        ground_truth=ground_truth,
        prediction=final,
        primary_failure=attribution.primary_failure,
        failure_stage=attribution.primary_stage,
        observed_failures=attribution.observed_failures,
        secondary_failures=attribution.secondary_failures,
        suspected_causes=attribution.suspected_causes,
        severity=severity,
        attribution_confidence=attribution.confidence,
        routing=result.get("routing"),
        fusion=result.get("fusion") or record.get("decision"),
        module_outputs=outputs,
        module_status=result.get("module_status", {}),
        timing=result.get("timing", {}),
        thresholds={
            "baseline_prediction_threshold": (result.get("baseline") or {}).get("threshold"),
            "analysis_cer_threshold": config.cer_threshold,
            "analysis_detection_iou_threshold": config.detection_iou_threshold,
            "routing_boundaries": config.routing_boundaries,
            "fusion_boundaries": config.fusion_boundaries,
            "boundary_margin": config.boundary_margin,
        },
        versions=result.get("metadata", {}),
        propagation_trace=ErrorPropagationTrace(steps=steps),
        requires_annotation_review=(
            metadata.annotation_status != AnnotationStatus.VERIFIED
            or attribution.primary_failure == FailureType.ANNOTATION_REVIEW_REQUIRED
        ),
        notes=metadata.notes,
        metadata=metadata,
    )


def load_jsonl(path: str | Path) -> list[dict]:
    source = Path(path).expanduser().resolve()
    return [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class ErrorAttributionEngine:
    """Small stateful facade for callers that keep one validated analysis config."""

    def __init__(self, config: ErrorAnalysisConfig) -> None:
        self.config = config

    def attribute(
        self,
        record: dict,
        ground_truth: GroundTruth,
        metadata: SampleMetadata,
    ) -> AttributionResult | None:
        return attribute_record(record, ground_truth, metadata, self.config)
