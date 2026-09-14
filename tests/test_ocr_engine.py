import numpy as np

from visionguard.config.models import OCRConfig
from visionguard.ocr.engine import OCREngine
from visionguard.ocr.provider import RawOCRBlock
from visionguard.schemas import BoundingBox, Detection


class FakeProvider:
    name = "FakeOCR"
    device = "cpu"
    instances = 0

    def __init__(self, _config: OCRConfig) -> None:
        type(self).instances += 1
        self.calls = 0

    def predict(self, _image: np.ndarray) -> list[RawOCRBlock]:
        self.calls += 1
        return [
            RawOCRBlock("second", 0.90, [(20, 30), (50, 30), (50, 40), (20, 40)]),
            RawOCRBlock("filtered", 0.20, [(1, 1), (9, 1), (9, 5), (1, 5)]),
            RawOCRBlock("first", 0.95, [(5, 10), (30, 10), (30, 20), (5, 20)]),
        ]


def make_engine(*, warmup: bool = False, fallback: bool = False) -> OCREngine:
    return OCREngine(
        OCRConfig(warmup_enabled=warmup, fallback_full_image=fallback),
        provider_factory=FakeProvider,
    )


def test_engine_loads_provider_once_and_filters_and_orders_text() -> None:
    FakeProvider.instances = 0
    engine = make_engine(warmup=True)
    result = engine.recognize(np.zeros((60, 100, 3), dtype=np.uint8))

    assert FakeProvider.instances == 1
    assert engine.is_warmed_up
    assert result.raw_block_count == 3
    assert result.filtered_block_count == 2
    assert result.full_text == "first\nsecond"
    assert result.blocks[0].confidence == 0.95


def test_roi_offsets_all_coordinates_to_original_image() -> None:
    engine = make_engine()
    result = engine.recognize_roi(
        np.zeros((300, 400, 3), dtype=np.uint8),
        BoundingBox(x1=100, y1=200, x2=300, y2=280),
    )

    assert result.image_width == 400
    assert result.image_height == 300
    assert result.blocks[0].bbox == BoundingBox(x1=105, y1=210, x2=130, y2=220)
    assert result.blocks[0].polygon[0] == (105.0, 210.0)


def test_detection_bbox_is_accepted_directly_by_roi_interface() -> None:
    detection = Detection(
        class_id=0,
        class_name="visual_sensitive_region",
        confidence=0.9,
        bbox=BoundingBox(x1=10, y1=20, x2=90, y2=70),
    )

    result = make_engine().recognize_roi(np.zeros((100, 120, 3), dtype=np.uint8), detection.bbox)

    assert result.blocks[0].bbox.x1 == 15
    assert result.blocks[0].bbox.y1 == 30


class EmptyProvider(FakeProvider):
    def predict(self, _image: np.ndarray) -> list[RawOCRBlock]:
        self.calls += 1
        return []


def test_empty_provider_result_is_stable() -> None:
    engine = OCREngine(
        OCRConfig(warmup_enabled=False, fallback_full_image=False),
        provider_factory=EmptyProvider,
    )
    result = engine.recognize(np.zeros((20, 30, 3), dtype=np.uint8))

    assert result.blocks == []
    assert result.full_text == ""
    assert result.raw_block_count == 0
