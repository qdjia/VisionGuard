from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from visionguard.config.models import DetectionConfig
from visionguard.detection.exceptions import DetectorLoadError
from visionguard.detection.onnx_detector import (
    OnnxYoloDetector,
    _execution_providers,
    _letterbox,
)


class FakeSession:
    def __init__(self, output: np.ndarray, providers: list[str]) -> None:
        self.output = output
        self.providers = providers

    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def get_providers(self):
        return self.providers

    def run(self, _outputs, inputs):
        batch = inputs["images"].shape[0]
        return [np.repeat(self.output, batch, axis=0)]


def config(tmp_path: Path) -> DetectionConfig:
    return DetectionConfig(
        provider="onnx",
        classes_file=tmp_path / "classes.yaml",
        class_names=("risk",),
        model_path=tmp_path / "model.onnx",
        conf_threshold=0.25,
        iou_threshold=0.45,
        max_det=10,
        image_size=640,
        device="cpu",
        half_precision=False,
        warmup_enabled=False,
        onnx_execution_provider="cpu",
    )


def test_execution_provider_selection_is_explicit() -> None:
    assert _execution_providers("auto", ["CPUExecutionProvider"]) == ["CPUExecutionProvider"]
    assert _execution_providers("cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"]) == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    with pytest.raises(DetectorLoadError, match="unavailable"):
        _execution_providers("cuda", ["CPUExecutionProvider"])


def test_letterbox_preserves_shape_and_reverse_mapping() -> None:
    image = np.zeros((320, 160, 3), dtype=np.uint8)
    tensor, scale, padding = _letterbox(image, 640)
    assert tensor.shape == (3, 640, 640)
    assert scale == 2.0
    assert padding == (160, 0)


def test_onnx_detector_returns_stable_schema_and_global_coordinates(tmp_path: Path) -> None:
    output = np.array([[[0, 0, 320, 640, 0.9, 0], [0, 0, 0, 0, 0, 0]]], dtype=np.float32)
    session = FakeSession(output, ["CPUExecutionProvider"])
    detector = OnnxYoloDetector(
        config(tmp_path),
        session_factory=lambda _path, _providers: session,
        available_providers=["CPUExecutionProvider"],
    )
    result = detector.predict(np.zeros((320, 160, 3), dtype=np.uint8))
    assert result.device == "onnx:CPUExecutionProvider"
    assert len(result.detections) == 1
    detection = result.detections[0]
    assert detection.class_name == "risk"
    assert detection.confidence == pytest.approx(0.9)
    assert detection.bbox.model_dump() == {"x1": 0.0, "y1": 0.0, "x2": 160.0, "y2": 320.0}


def test_onnx_detector_filters_low_confidence_and_supports_batch(tmp_path: Path) -> None:
    output = np.array([[[0, 0, 100, 100, 0.1, 0]]], dtype=np.float32)
    session = FakeSession(output, ["CPUExecutionProvider"])
    detector = OnnxYoloDetector(
        config(tmp_path),
        session_factory=lambda _path, _providers: session,
        available_providers=["CPUExecutionProvider"],
    )
    results = detector.predict_batch([np.zeros((10, 10, 3), dtype=np.uint8)] * 2)
    assert len(results) == 2
    assert all(result.detections == [] for result in results)
