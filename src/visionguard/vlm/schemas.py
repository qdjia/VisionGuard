from pydantic import Field

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.schemas import Detection, OCRTextBlock
from visionguard.schemas.common import SchemaModel


class VLMContext(SchemaModel):
    detections: list[Detection] = Field(default_factory=list)
    ocr_blocks: list[OCRTextBlock] = Field(default_factory=list)
    ocr_full_text: str = ""
    baseline_prediction: TextModerationPrediction | None = None
    metadata: dict = Field(default_factory=dict)


class VLMTiming(SchemaModel):
    image_prepare_ms: float = Field(default=0, ge=0)
    prompt_build_ms: float = Field(default=0, ge=0)
    inference_ms: float = Field(default=0, ge=0)
    parse_ms: float = Field(default=0, ge=0)
    total_ms: float = Field(default=0, ge=0)
