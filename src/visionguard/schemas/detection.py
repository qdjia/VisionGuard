"""Object detection input/output contracts."""

from pydantic import Field

from visionguard.schemas.common import BoundingBox, SchemaModel


class Detection(SchemaModel):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox


class DetectionResult(SchemaModel):
    detections: list[Detection] = Field(default_factory=list)
    inference_ms: float = Field(ge=0.0)
    model_version: str | None = None

