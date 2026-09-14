"""OpenCV rendering kept independent from model inference."""

from pathlib import Path

import cv2
import numpy as np

from visionguard.detection.exceptions import ImageLoadError
from visionguard.schemas import Detection


def draw_detections(
    image: np.ndarray,
    detections: list[Detection],
    *,
    color: tuple[int, int, int] = (0, 200, 255),
    thickness: int = 2,
) -> np.ndarray:
    """Draw clipped boxes and labels on a copy of the source image."""

    if image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
        raise ImageLoadError("visualization requires a non-empty 3-channel BGR image")
    canvas = image.copy()
    height, width = canvas.shape[:2]

    for detection in detections:
        box = detection.bbox
        x1 = min(max(int(round(box.x1)), 0), width - 1)
        y1 = min(max(int(round(box.y1)), 0), height - 1)
        x2 = min(max(int(round(box.x2)), 0), width - 1)
        y2 = min(max(int(round(box.y2)), 0), height - 1)
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness)
        label = f"{detection.class_name} {detection.confidence:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        label_top = max(0, y1 - text_height - baseline - 4)
        label_right = min(width - 1, x1 + text_width + 4)
        cv2.rectangle(canvas, (x1, label_top), (label_right, y1), color, -1)
        cv2.putText(
            canvas,
            label,
            (x1 + 2, max(text_height, y1 - baseline - 2)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
    return canvas


def save_visualization(
    image: np.ndarray,
    detections: list[Detection],
    output_path: str | Path,
) -> Path:
    """Render and save a result image, creating only its parent directory."""

    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = draw_detections(image, detections)
    if not cv2.imwrite(str(target), rendered):
        raise ImageLoadError(f"failed to save visualization: {target}")
    return target.resolve()

