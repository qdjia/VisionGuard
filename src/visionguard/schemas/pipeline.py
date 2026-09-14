"""End-to-end and cascaded inference contracts."""

from enum import StrEnum

from pydantic import Field

from visionguard.schemas.common import ImageReference, SchemaModel
from visionguard.schemas.detection import DetectionResult
from visionguard.schemas.moderation import ModerationResult
from visionguard.schemas.ocr import OCRResult


class DecisionSource(StrEnum):
    RULE_ENGINE = "rule_engine"
    VLM = "vlm"
    FUSION = "fusion"


class StageTimings(SchemaModel):
    preprocessing_ms: float = Field(default=0.0, ge=0.0)
    detection_ms: float = Field(default=0.0, ge=0.0)
    ocr_ms: float = Field(default=0.0, ge=0.0)
    rules_ms: float = Field(default=0.0, ge=0.0)
    vlm_ms: float = Field(default=0.0, ge=0.0)
    fusion_ms: float = Field(default=0.0, ge=0.0)
    total_ms: float = Field(default=0.0, ge=0.0)


class PipelineResult(SchemaModel):
    image: ImageReference
    moderation: ModerationResult
    decision_source: DecisionSource
    vlm_called: bool
    detections: DetectionResult
    ocr: OCRResult
    rule_result: ModerationResult | None = None
    vlm_result: ModerationResult | None = None
    timings: StageTimings = Field(default_factory=StageTimings)

