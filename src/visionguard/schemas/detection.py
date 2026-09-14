"""Object detection input/output contracts."""

from pydantic import Field

from visionguard.schemas.common import BoundingBox, SchemaModel


class Detection(SchemaModel):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox


class TimingInfo(SchemaModel):
    preprocess_ms: float = Field(default=0.0, ge=0.0)
    inference_ms: float = Field(default=0.0, ge=0.0)
    postprocess_ms: float = Field(default=0.0, ge=0.0)
    total_ms: float = Field(default=0.0, ge=0.0)


class DetectionResult(SchemaModel):
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    detections: list[Detection] = Field(default_factory=list)
    timing: TimingInfo
    device: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
