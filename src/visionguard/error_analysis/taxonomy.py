"""Versioned failure taxonomy shared by analysis, reports, and regression."""

from enum import StrEnum


class FailureStage(StrEnum):
    END_TO_END = "end_to_end"
    DETECTION = "detection"
    OCR = "ocr"
    BASELINE = "baseline"
    ROUTING = "routing"
    VLM = "vlm"
    FUSION = "fusion"
    SYSTEM = "system"
    DATA = "data"


class FailureType(StrEnum):
    FALSE_LOW = "false_low"
    FALSE_HIGH = "false_high"
    WRONG_RISK_LEVEL = "wrong_risk_level"
    WRONG_CATEGORY = "wrong_category"
    MISSED_CATEGORY = "missed_category"
    EXTRA_CATEGORY = "extra_category"
    UNNECESSARY_MANUAL_REVIEW = "unnecessary_manual_review"
    MISSED_MANUAL_REVIEW = "missed_manual_review"
    PARTIAL_RESULT = "partial_result"
    PIPELINE_FAILURE = "pipeline_failure"
    FALSE_POSITIVE_DETECTION = "false_positive_detection"
    FALSE_NEGATIVE_DETECTION = "false_negative_detection"
    DETECTION_CLASS_MISMATCH = "class_mismatch"
    POOR_LOCALIZATION = "poor_localization"
    DUPLICATE_DETECTION = "duplicate_detection"
    LOW_CONFIDENCE_TRUE_POSITIVE = "low_confidence_true_positive"
    HIGH_CONFIDENCE_FALSE_POSITIVE = "high_confidence_false_positive"
    SUSPECTED_DETECTION_ISSUE = "suspected_detection_issue"
    OCR_SUBSTITUTION = "character_substitution"
    OCR_DELETION = "character_deletion"
    OCR_INSERTION = "character_insertion"
    MISSED_TEXT = "missed_text"
    HALLUCINATED_TEXT = "hallucinated_text"
    READING_ORDER_ERROR = "reading_order_error"
    EMPTY_OCR = "empty_ocr"
    LOW_CONFIDENCE_OCR = "low_confidence_ocr"
    SUSPICIOUS_OCR_OUTPUT = "suspicious_ocr_output"
    BASELINE_FALSE_POSITIVE = "baseline_false_positive"
    BASELINE_FALSE_NEGATIVE = "baseline_false_negative"
    BASELINE_UNCERTAIN = "baseline_uncertain"
    BASELINE_THRESHOLD_ERROR = "baseline_threshold_error"
    OCR_INDUCED_BASELINE_ERROR = "ocr_induced_baseline_error"
    UNSAFE_FAST_PASS = "unsafe_fast_pass"
    UNSAFE_ROUTE_ATTEMPT = "unsafe_route_attempt"
    POTENTIAL_UNNECESSARY_VLM = "potential_unnecessary_vlm"
    ROUTING_OVERRIDE = "routing_override"
    MODULE_FAILURE_ROUTE = "module_failure_route"
    EVIDENCE_CONFLICT_ROUTE = "evidence_conflict_route"
    INSUFFICIENT_EVIDENCE_ROUTE = "insufficient_evidence_route"
    THRESHOLD_BOUNDARY_ROUTE = "threshold_boundary_route"
    SAFE_SAMPLE_SENT_TO_VLM = "safe_sample_sent_to_vlm"
    VLM_FALSE_LOW = "vlm_false_low"
    VLM_FALSE_HIGH = "vlm_false_high"
    VLM_WRONG_CATEGORY = "vlm_wrong_category"
    VLM_MISSED_CATEGORY = "vlm_missed_category"
    VLM_EXTRA_CATEGORY = "vlm_extra_category"
    UNSUPPORTED_REASON = "unsupported_reason"
    VLM_EVIDENCE_MISMATCH = "evidence_mismatch"
    VLM_HALLUCINATION = "hallucinated_evidence"
    SUSPECTED_VLM_HALLUCINATION = "suspected_hallucinated_evidence"
    VLM_FORMAT_FAILURE = "format_failure"
    VLM_RETRY_EXHAUSTED = "retry_failure"
    PROMPT_INJECTION_SUSPECTED = "prompt_injection_suspected"
    VLM_BBOX_MISMATCH = "bbox_grounding_error"
    VLM_MANUAL_REVIEW_DISAGREEMENT = "manual_review_disagreement"
    FUSION_FALSE_LOW = "fusion_false_low"
    FUSION_FALSE_HIGH = "fusion_false_high"
    BAD_WEIGHTING = "bad_weighting"
    BAD_THRESHOLD = "bad_threshold_mapping"
    CONFLICT_RESOLUTION_ERROR = "conflict_resolution_failure"
    FUSION_CATEGORY_ERROR = "category_fusion_error"
    NEAR_BOUNDARY_ERROR = "near_boundary_error"
    ROUTING_GUARD_FAILURE = "routing_guard_failure"
    FUSION_EVIDENCE_CONFLICT = "fusion_evidence_conflict"
    NEAR_DECISION_BOUNDARY = "near_decision_boundary"
    MODEL_LOAD_FAILURE = "model_load_failure"
    CUDA_OOM = "cuda_oom"
    TIMEOUT = "timeout"
    ARTIFACT_WRITE_FAILURE = "artifact_failure"
    INVALID_INPUT = "invalid_input"
    DEPENDENCY_FAILURE = "dependency_error"
    SCHEMA_FAILURE = "schema_validation_failure"
    PROVIDER_FAILURE = "provider_failure"
    CONFIGURATION_FAILURE = "config_error"
    IO_FAILURE = "io_error"
    MODULE_FAILURE = "module_failure"
    WRONG_LABEL = "wrong_label"
    AMBIGUOUS_LABEL = "ambiguous_label"
    INSUFFICIENT_LABEL = "insufficient_label"
    DUPLICATE_SAMPLE = "duplicate_sample"
    SPLIT_LEAKAGE = "split_leakage"
    CORRUPT_SAMPLE = "corrupted_image"
    OUT_OF_DISTRIBUTION = "out_of_distribution"
    ANNOTATION_REVIEW_REQUIRED = "annotation_review_required"


_VALUES = list(FailureType)
_DETECTION = set(_VALUES[10:18])
_OCR = set(_VALUES[18:27])
_BASELINE = set(_VALUES[27:32])
_ROUTING = set(_VALUES[32:41])
_VLM = set(_VALUES[41:55])
_FUSION = set(_VALUES[55:65])
_SYSTEM = set(_VALUES[65:76])


def stage_for(failure: FailureType) -> FailureStage:
    for failures, stage in (
        (_DETECTION, FailureStage.DETECTION),
        (_OCR, FailureStage.OCR),
        (_BASELINE, FailureStage.BASELINE),
        (_ROUTING, FailureStage.ROUTING),
        (_VLM, FailureStage.VLM),
        (_FUSION, FailureStage.FUSION),
        (_SYSTEM, FailureStage.SYSTEM),
    ):
        if failure in failures:
            return stage
    if failure in set(_VALUES[76:]):
        return FailureStage.DATA
    return FailureStage.END_TO_END


PRIMARY_PRIORITY = (
    FailureStage.SYSTEM,
    FailureStage.END_TO_END,
    FailureStage.ROUTING,
    FailureStage.FUSION,
    FailureStage.VLM,
    FailureStage.DETECTION,
    FailureStage.OCR,
    FailureStage.BASELINE,
    FailureStage.DATA,
)
