import numpy as np

from visionguard.detection import draw_detections
from visionguard.schemas import BoundingBox, Detection


def test_drawing_does_not_mutate_source_and_clips_box() -> None:
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    original = image.copy()
    detection = Detection(
        class_id=0,
        class_name="risk",
        confidence=0.9,
        bbox=BoundingBox(x1=1, y1=1, x2=100, y2=100),
    )

    rendered = draw_detections(image, [detection])

    assert np.array_equal(image, original)
    assert not np.array_equal(rendered, original)


def test_empty_detection_list_returns_equal_copy() -> None:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    rendered = draw_detections(image, [])

    assert rendered is not image
    assert np.array_equal(rendered, image)

