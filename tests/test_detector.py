from pathlib import Path
from typing import Any

import numpy as np

from visionguard.config.models import DetectionConfig
from visionguard.detection import YOLODetector


class FakeTensor:
    def __init__(self, value: list[Any]) -> None:
        self.value = value

    def detach(self) -> "FakeTensor":
        return self

    def cpu(self) -> "FakeTensor":
        return self

    def tolist(self) -> list[Any]:
        return self.value


class FakeBoxes:
    xyxy = FakeTensor([[1.0, 2.0, 10.0, 12.0]])
    conf = FakeTensor([0.8])
    cls = FakeTensor([0.0])

    def __len__(self) -> int:
        return 1


class FakeResult:
    boxes = FakeBoxes()
    names = {0: "native_weapon"}


class FakeModel:
    def __init__(self) -> None:
        self.predict_calls = 0

    def predict(self, **_: Any) -> list[FakeResult]:
        self.predict_calls += 1
        return [FakeResult()]


def make_config(*, warmup_enabled: bool = False) -> DetectionConfig:
    return DetectionConfig(
        classes_file=Path("classes.yaml"),
        class_names=("weapon",),
        model_path=Path("model.pt"),
        conf_threshold=0.25,
        iou_threshold=0.45,
        max_det=300,
        image_size=32,
        device="cpu",
        half_precision=True,
        warmup_enabled=warmup_enabled,
        warmup_runs=1,
        class_name_mapping={"native_weapon": "weapon"},
    )


def test_model_is_constructed_once_and_reused_for_predictions() -> None:
    created: list[FakeModel] = []

    def factory(_: str) -> FakeModel:
        model = FakeModel()
        created.append(model)
        return model

    detector = YOLODetector(make_config(), model_factory=factory)
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    first = detector.predict(image)
    second = detector.predict(image)

    assert len(created) == 1
    assert created[0].predict_calls == 2
    assert first.detections[0].class_name == "weapon"
    assert second.image_width == 30


def test_warmup_runs_once_even_when_called_again() -> None:
    model = FakeModel()
    detector = YOLODetector(make_config(warmup_enabled=True), model_factory=lambda _: model)

    detector.warmup()

    assert detector.is_warmed_up is True
    assert model.predict_calls == 1

