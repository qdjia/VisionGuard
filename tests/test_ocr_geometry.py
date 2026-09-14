import pytest

from visionguard.core.exceptions import InvalidROIError
from visionguard.ocr.geometry import offset_polygon, polygon_to_bbox, sanitize_bbox
from visionguard.schemas import BoundingBox


def test_polygon_to_axis_aligned_bbox() -> None:
    box = polygon_to_bbox([(10, 12), (30, 8), (32, 20), (12, 25)])

    assert box == BoundingBox(x1=10, y1=8, x2=32, y2=25)


def test_sanitize_bbox_clamps_negative_and_overflow_coordinates() -> None:
    assert sanitize_bbox(BoundingBox(x1=-4.2, y1=-3, x2=101.1, y2=55), 100, 50) == (
        0,
        0,
        100,
        50,
    )


def test_sanitize_bbox_rejects_empty_clamped_roi() -> None:
    with pytest.raises(InvalidROIError, match="empty after clamping"):
        sanitize_bbox(BoundingBox(x1=110, y1=5, x2=120, y2=20), 100, 50)


def test_polygon_offset_maps_roi_coordinates_to_full_image() -> None:
    assert offset_polygon([(20, 30), (40, 50)], 100, 200) == [(120, 230), (140, 250)]
