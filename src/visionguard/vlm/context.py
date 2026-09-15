from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.schemas import DetectionResult, OCRResult
from visionguard.vlm.schemas import VLMContext


def build_context(
    detections: DetectionResult | None = None,
    ocr: OCRResult | None = None,
    baseline: TextModerationPrediction | None = None,
) -> VLMContext:
    return VLMContext(
        detections=detections.detections if detections else [],
        ocr_blocks=ocr.blocks if ocr else [],
        ocr_full_text=ocr.full_text if ocr else "",
        baseline_prediction=baseline,
    )
