"""Stable signals, provenance, scores, and decisions for risk fusion."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from visionguard.schemas import RiskLevel
from visionguard.schemas.common import SchemaModel


class FusionReasonCode(StrEnum):
    ALL_EVIDENCE_SAFE = "all_evidence_safe"
    VISUAL_RISK = "visual_risk"
    TEXT_RISK = "text_risk"
    VLM_RISK = "vlm_risk"
    EVIDENCE_CONFLICT = "evidence_conflict"
    MODULE_FAILURE = "module_failure"
    OCR_LOW_RELIABILITY = "ocr_low_reliability"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEAR_DECISION_BOUNDARY = "near_decision_boundary"
    ROUTING_OVERRIDE = "routing_override"
    HARD_SAFETY_OVERRIDE = "hard_safety_override"


class FusionDetectionEvidence(SchemaModel):
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    severity: float = Field(ge=0, le=1)
    adjusted_score: float = Field(ge=0, le=1)


class FusionSignals(SchemaModel):
    detection_count: int = Field(default=0, ge=0)
    max_detection_confidence: float | None = Field(default=None, ge=0, le=1)
    mean_detection_confidence: float | None = Field(default=None, ge=0, le=1)
    high_risk_detection_count: int = Field(default=0, ge=0)
    high_risk_classes: list[str] = Field(default_factory=list)
    detection_evidence: list[FusionDetectionEvidence] = Field(default_factory=list)
    detector_status: str = "unknown"
    ocr_block_count: int = Field(default=0, ge=0)
    mean_ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_text_length: int = Field(default=0, ge=0)
    ocr_status: str = "unknown"
    baseline_label: str | None = None
    baseline_probability: float | None = Field(default=None, ge=0, le=1)
    baseline_status: str = "unknown"
    vlm_available: bool = False
    vlm_risk_level: RiskLevel | None = None
    vlm_categories: list[str] = Field(default_factory=list)
    vlm_confidence_score: float | None = Field(default=None, ge=0, le=1)
    vlm_requires_manual_review: bool | None = None
    vlm_has_evidence: bool = False
    vlm_status: str = "unknown"
    route: str = "unknown"
    call_vlm: bool = False
    routing_reason_codes: list[str] = Field(default_factory=list)
    routing_policy_version: str | None = None
    routing_overridden_by_fusion: bool = False
    module_failures: list[str] = Field(default_factory=list)
    evidence_conflict: bool = False
    insufficient_evidence: bool = False


class FusionScores(SchemaModel):
    visual: float | None = Field(default=None, ge=0, le=1)
    text: float | None = Field(default=None, ge=0, le=1)
    vlm: float | None = Field(default=None, ge=0, le=1)


class FusionWeightsUsed(SchemaModel):
    visual: float = Field(default=0, ge=0, le=1)
    text: float = Field(default=0, ge=0, le=1)
    vlm: float = Field(default=0, ge=0, le=1)


class FusedCategory(SchemaModel):
    name: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    sources: list[Literal["detector", "baseline", "vlm"]] = Field(min_length=1)


class FusedEvidence(SchemaModel):
    source: Literal["detector", "ocr", "baseline", "vlm", "routing", "system"]
    description: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    category: str | None = None


class FusionMetadata(SchemaModel):
    strategy: str
    vlm_used: bool
    available_sources: list[Literal["visual", "text", "vlm"]]
    routing_policy_version: str | None = None
    fusion_policy_version: str
    routing_overridden_by_fusion: bool = False
    score_is_calibrated_probability: Literal[False] = False


class FusionDecision(SchemaModel):
    risk_level: RiskLevel
    risk_score: float = Field(ge=0, le=1)
    categories: list[FusedCategory] = Field(default_factory=list)
    requires_manual_review: bool
    decision_source: Literal["fusion"] = "fusion"
    reason: str = Field(min_length=1)
    reason_codes: list[FusionReasonCode] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    evidence_summary: list[FusedEvidence] = Field(default_factory=list)
    signals: FusionSignals
    scores: FusionScores
    weights: FusionWeightsUsed
    policy_version: str = Field(pattern=r"^fusion_v\d+$")
    metadata: FusionMetadata

    @model_validator(mode="after")
    def unique_contracts(self) -> "FusionDecision":
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("fusion reason codes must be unique")
        if len({category.name for category in self.categories}) != len(self.categories):
            raise ValueError("fused category names must be unique")
        return self
