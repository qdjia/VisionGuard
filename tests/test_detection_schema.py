import pytest
from pydantic import ValidationError

from visionguard.schemas import BoundingBox, Detection, DetectionResult, TimingInfo


def test_detection_result_allows_empty_detections_and_serializes() -> None:
    result = DetectionResult(
        image_width=320,
        image_height=240,
        detections=[],
        timing=TimingInfo(preprocess_ms=1, inference_ms=2, postprocess_ms=1, total_ms=4),
        device="cpu",
        model_name="yolo26.pt",
    )

    assert result.model_dump(mode="json")["detections"] == []
    assert result.timing.total_ms == 4


def test_detection_confidence_must_be_normalized() -> None:
    with pytest.raises(ValidationError):
        Detection(
            class_id=0,
            class_name="object",
            confidence=1.1,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        )
