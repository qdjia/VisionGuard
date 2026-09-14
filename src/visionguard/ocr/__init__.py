"""Provider-independent full-image and ROI OCR."""

from visionguard.ocr.config import load_ocr_config
from visionguard.ocr.engine import OCREngine
from visionguard.ocr.evaluator import OCREvaluator, character_error_rate
from visionguard.ocr.visualization import draw_ocr_blocks, save_ocr_visualization

__all__ = [
    "OCREngine",
    "OCREvaluator",
    "character_error_rate",
    "draw_ocr_blocks",
    "load_ocr_config",
    "save_ocr_visualization",
]
