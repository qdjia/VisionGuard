"""Stable end-to-end contracts for review results and observability."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.moderation.schemas import ModerationCategory, ModerationResult
from visionguard.schemas import DetectionResult, OCRResult, RiskLevel
from visionguard.schemas.common import SchemaModel


class ModuleState(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ArtifactState(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewModuleStatus(SchemaModel):
    status: ModuleState
    started_at: datetime | None = None
    latency_ms: float = Field(default=0, ge=0)
    error_type: str | None = None
    error_message: str | None = None


class PipelineTiming(SchemaModel):
    image_load_ms: float = Field(default=0, ge=0)
    detector_ms: float = Field(default=0, ge=0)
    ocr_ms: float = Field(default=0, ge=0)
    baseline_ms: float = Field(default=0, ge=0)
    context_build_ms: float = Field(default=0, ge=0)
    vlm_ms: float = Field(default=0, ge=0)
    aggregation_ms: float = Field(default=0, ge=0)
    artifact_save_ms: float = Field(default=0, ge=0)
    total_ms: float = Field(default=0, ge=0)


class ReviewImage(SchemaModel):
    input_type: Literal["path", "ndarray"]
    source_path: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FinalReview(SchemaModel):
    risk_level: RiskLevel | None = None
    categories: list[ModerationCategory] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    requires_manual_review: bool


class RoutingSignals(SchemaModel):
    detection_count: int = Field(default=0, ge=0)
    max_detection_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_block_count: int = Field(default=0, ge=0)
    mean_ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    baseline_probability: float | None = Field(default=None, ge=0, le=1)
    vlm_confidence: float | None = Field(default=None, ge=0, le=1)
    vlm_requires_manual_review: bool | None = None
    ocr_text_truncated_for_baseline: bool = False
    baseline_input_chars: int = Field(default=0, ge=0)


class ReviewMetadata(SchemaModel):
    pipeline_version: str
    policy_version: str
    prompt_version: str | None = None
    timestamp: datetime
    component_versions: dict[str, str | None] = Field(default_factory=dict)


class ArtifactStatus(SchemaModel):
    status: ArtifactState = ArtifactState.PENDING
    directory: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class ReviewResult(SchemaModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    image: ReviewImage
    detection: DetectionResult | None = None
    ocr: OCRResult | None = None
    baseline: TextModerationPrediction | None = None
    vlm: ModerationResult | None = None
    final: FinalReview
    review_status: ReviewStatus
    module_status: dict[Literal["detector", "ocr", "baseline", "vlm"], ReviewModuleStatus]
    timing: PipelineTiming
    routing_signals: RoutingSignals
    artifacts: ArtifactStatus = Field(default_factory=ArtifactStatus)
    metadata: ReviewMetadata

    @model_validator(mode="after")
    def require_all_module_statuses(self) -> "ReviewResult":
        expected = {"detector", "ocr", "baseline", "vlm"}
        if set(self.module_status) != expected:
            raise ValueError("module_status must contain detector/ocr/baseline/vlm")
        return self
