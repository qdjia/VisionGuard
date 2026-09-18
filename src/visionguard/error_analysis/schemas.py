"""Stable data contracts for failures, hard cases, and regressions."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from visionguard.error_analysis.taxonomy import FailureStage, FailureType, stage_for
from visionguard.schemas.common import BoundingBox, SchemaModel


class FailureSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttributionConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnnotationStatus(StrEnum):
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    AMBIGUOUS = "ambiguous"


class CaseDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class ObjectGroundTruth(SchemaModel):
    category: str = Field(min_length=1)
    bbox: BoundingBox

    @field_validator("bbox", mode="before")
    @classmethod
    def accept_xyxy_list(cls, value):
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return dict(zip(("x1", "y1", "x2", "y2"), value, strict=True))
        return value


class GroundTruth(SchemaModel):
    risk_level: Literal["low", "medium", "high"] | None = None
    categories: list[str] | None = None
    text: str | None = None
    objects: list[ObjectGroundTruth] | None = None
    requires_manual_review: bool | None = None


class SampleMetadata(SchemaModel):
    source: str | None = None
    difficulty: CaseDifficulty = CaseDifficulty.UNKNOWN
    annotation_status: AnnotationStatus = AnnotationStatus.NEEDS_REVIEW
    notes: str | None = None
    generation_method: str | None = None


class PropagationStep(SchemaModel):
    stage: FailureStage
    observation: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ErrorPropagationTrace(SchemaModel):
    steps: list[PropagationStep] = Field(default_factory=list)
    causal_claim: Literal[False] = False


class AttributionResult(SchemaModel):
    observed_failures: list[FailureType]
    suspected_causes: list[FailureType] = Field(default_factory=list)
    primary_failure: FailureType
    secondary_failures: list[FailureType] = Field(default_factory=list)
    primary_stage: FailureStage
    confidence: AttributionConfidence


class ErrorCase(SchemaModel):
    case_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    run_id: str | None = None
    image: str
    image_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    ground_truth: GroundTruth
    prediction: dict[str, Any]
    primary_failure: FailureType
    failure_stage: FailureStage
    observed_failures: list[FailureType] = Field(min_length=1)
    secondary_failures: list[FailureType] = Field(default_factory=list)
    suspected_causes: list[FailureType] = Field(default_factory=list)
    severity: FailureSeverity
    attribution_confidence: AttributionConfidence
    routing: dict[str, Any] | None = None
    fusion: dict[str, Any] | None = None
    module_outputs: dict[str, Any] = Field(default_factory=dict)
    module_status: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    versions: dict[str, Any] = Field(default_factory=dict)
    propagation_trace: ErrorPropagationTrace = Field(default_factory=ErrorPropagationTrace)
    requires_annotation_review: bool = False
    notes: str | None = None
    metadata: SampleMetadata = Field(default_factory=SampleMetadata)

    @model_validator(mode="after")
    def consistent_taxonomy(self) -> "ErrorCase":
        if len(set(self.observed_failures)) != len(self.observed_failures):
            raise ValueError("observed_failures must be unique")
        if self.primary_failure not in self.observed_failures:
            raise ValueError("primary_failure must be observed")
        if self.failure_stage != stage_for(self.primary_failure):
            raise ValueError("failure_stage does not match primary_failure")
        if set(self.suspected_causes) & set(self.observed_failures):
            raise ValueError("suspected causes must not duplicate observed failures")
        return self


class HardCaseRecord(SchemaModel):
    case_id: str
    image: str
    image_hash: str
    primary_failure: FailureType
    failure_types: list[FailureType]
    severity: FailureSeverity
    ground_truth: GroundTruth
    annotation_status: AnnotationStatus
    difficulty: CaseDifficulty = CaseDifficulty.UNKNOWN
    notes: str | None = None
    eligible_for_regression: bool
    source_run_ids: list[str] = Field(default_factory=list)


class RegressionOutcome(StrEnum):
    PASSED = "passed"
    STILL_FAILING = "still_failing"
    FIXED = "fixed"
    NEW_FAILURE = "new_failure"
    NOT_EVALUABLE = "not_evaluable"


class RegressionRecord(SchemaModel):
    case_id: str
    image: str
    outcome: RegressionOutcome
    historical_failure: FailureType
    current_failures: list[FailureType] = Field(default_factory=list)
    current_result: dict[str, Any] | None = None
    message: str = ""
