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
    bbox: BoundingBox
    scope: OCRScope = OCRScope.FULL_IMAGE


class OCRResult(SchemaModel):
    blocks: list[OCRTextBlock] = Field(default_factory=list)
    inference_ms: float = Field(ge=0.0)
    engine_version: str | None = None

    @property
    def full_text(self) -> str:
        return "\n".join(block.text for block in self.blocks)
