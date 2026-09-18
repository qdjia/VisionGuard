"""Non-mutating error-case overlays reusing detector and OCR renderers."""

from pathlib import Path

import cv2

from visionguard.detection.visualization import draw_detections
from visionguard.error_analysis.schemas import ErrorCase
from visionguard.ocr.visualization import draw_ocr_blocks
from visionguard.schemas import DetectionResult, OCRResult


def save_error_visualization(case: ErrorCase, output: str | Path) -> Path | None:
    image = cv2.imread(case.image, cv2.IMREAD_COLOR)
    if image is None:
        return None
    detection = case.module_outputs.get("detection")
    if detection:
        image = draw_detections(image, DetectionResult.model_validate(detection).detections)
    ocr = case.module_outputs.get("ocr")
    if ocr:
        image = draw_ocr_blocks(image, OCRResult.model_validate(ocr).blocks)
    for item in case.ground_truth.objects or []:
        box = item.bbox
        cv2.rectangle(
            image, (round(box.x1), round(box.y1)), (round(box.x2), round(box.y2)), (0, 255, 0), 2
        )
        cv2.putText(
            image,
            f"GT:{item.category}",
            (round(box.x1), max(15, round(box.y1))),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), image):
        raise OSError(f"failed to write error visualization: {target}")
    return target
