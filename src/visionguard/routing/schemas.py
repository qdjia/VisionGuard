"""Pure routing signals and explainable decision contracts."""

from enum import StrEnum

from pydantic import Field, model_validator

from visionguard.schemas.common import SchemaModel


class Route(StrEnum):
    FAST_PATH = "fast_path"
    VLM_PATH = "vlm_path"
    FULL_PIPELINE = "full_pipeline"


class DecisionSource(StrEnum):
    FAST_PATH = "fast_path"
    VLM = "vlm"
    FULL_PIPELINE = "full_pipeline"


class RoutingReasonCode(StrEnum):
    SAFE_CONSENSUS = "safe_consensus"
    HIGH_RISK_DETECTION = "high_risk_detection"
    BASELINE_HIGH_RISK = "baseline_high_risk"
    BASELINE_UNCERTAIN = "baseline_uncertain"
    OCR_LOW_CONFIDENCE = "ocr_low_confidence"
    EVIDENCE_CONFLICT = "evidence_conflict"
    MODULE_FAILURE = "module_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_TEXT = "no_text"
    NO_DETECTION = "no_detection"
    FULL_PIPELINE = "full_pipeline"


class RoutingSignals(SchemaModel):
    detection_count: int = Field(default=0, ge=0)
    max_detection_confidence: float | None = Field(default=None, ge=0, le=1)
    mean_detection_confidence: float | None = Field(default=None, ge=0, le=1)
    high_risk_detection_count: int = Field(default=0, ge=0)
    suspicious_high_risk_detection_count: int = Field(default=0, ge=0)
    has_high_risk_class: bool = False
    ocr_block_count: int = Field(default=0, ge=0)
    mean_ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_text_length: int = Field(default=0, ge=0)
    baseline_probability: float | None = Field(default=None, ge=0, le=1)
    # ``unknown`` keeps Phase 7 artifact JSON readable after adding Stage 1 status
    # signals. New Phase 8 runs always populate all three values explicitly.
    detector_status: str = "unknown"
    ocr_status: str = "unknown"
    baseline_status: str = "unknown"
    evidence_conflict: bool = False
    insufficient_evidence: bool = False
    vlm_confidence: float | None = Field(default=None, ge=0, le=1)
    vlm_requires_manual_review: bool | None = None
    ocr_text_truncated_for_baseline: bool = False
    baseline_input_chars: int = Field(default=0, ge=0)


class RoutingDecision(SchemaModel):
    route: Route
    call_vlm: bool
    reason_codes: list[RoutingReasonCode] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    signals: RoutingSignals
    policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def route_matches_call(self) -> "RoutingDecision":
        if self.route == Route.FAST_PATH and self.call_vlm:
            raise ValueError("fast_path cannot call VLM")
        if self.route == Route.VLM_PATH and not self.call_vlm:
            raise ValueError("call_vlm is inconsistent with route")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("routing reason codes must be unique")
        return self
