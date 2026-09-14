"""OCR polygon and ROI coordinate utilities."""

import math

from visionguard.core.exceptions import InvalidROIError
from visionguard.schemas import BoundingBox


def polygon_to_bbox(points: list[tuple[float, float]]) -> BoundingBox:
    if len(points) < 4:
        raise ValueError("OCR polygon must contain at least four points")
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    return BoundingBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))


def sanitize_bbox(bbox: BoundingBox, width: int, height: int) -> tuple[int, int, int, int]:
    x1 = max(0, min(width, math.floor(bbox.x1)))
    y1 = max(0, min(height, math.floor(bbox.y1)))
    x2 = max(0, min(width, math.ceil(bbox.x2)))
    y2 = max(0, min(height, math.ceil(bbox.y2)))
    if x2 <= x1 or y2 <= y1:
        raise InvalidROIError(
            f"ROI is empty after clamping: ({x1}, {y1}, {x2}, {y2}) in {width}x{height}"
        )
    return x1, y1, x2, y2


def offset_polygon(
    points: list[tuple[float, float]], x_offset: float, y_offset: float
) -> list[tuple[float, float]]:
    return [(x + x_offset, y + y_offset) for x, y in points]
