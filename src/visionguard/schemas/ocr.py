"""Full-image and region OCR contracts."""

from enum import StrEnum

from pydantic import Field

from visionguard.schemas.common import BoundingBox, SchemaModel


class OCRScope(StrEnum):
    FULL_IMAGE = "full_image"
    ROI = "roi"


class OCRTextBlock(SchemaModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    polygon: list[tuple[float, float]] = Field(min_length=4)
    bbox: BoundingBox
    scope: OCRScope = OCRScope.FULL_IMAGE


class OCRTiming(SchemaModel):
    preprocess_ms: float = Field(default=0.0, ge=0.0)
    ocr_ms: float = Field(default=0.0, ge=0.0)
    postprocess_ms: float = Field(default=0.0, ge=0.0)
    total_ms: float = Field(default=0.0, ge=0.0)


class OCRResult(SchemaModel):
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    blocks: list[OCRTextBlock] = Field(default_factory=list)
    full_text: str = ""
    timing: OCRTiming
    device: str
    engine_name: str
    raw_block_count: int = Field(default=0, ge=0)
    filtered_block_count: int = Field(default=0, ge=0)
