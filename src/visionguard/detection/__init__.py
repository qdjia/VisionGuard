"""Configurable object detection inference."""

from visionguard.detection.exceptions import (
    DetectorError,
    DetectorLoadError,
    ImageLoadError,
    InferenceError,
)
from visionguard.detection.onnx_detector import OnnxYoloDetector
from visionguard.detection.provider import DetectorProvider
from visionguard.detection.visualization import draw_detections, save_visualization

__all__ = [
    "DetectorError",
    "DetectorLoadError",
    "ImageLoadError",
    "InferenceError",
    "DetectorProvider",
    "OnnxYoloDetector",
    "YOLODetector",
    "draw_detections",
    "resolve_device",
    "save_visualization",
]


def __getattr__(name: str):
    """Keep the training-only Ultralytics dependency out of ONNX runtimes."""

    if name in {"YOLODetector", "resolve_device"}:
        from visionguard.detection.detector import YOLODetector, resolve_device

        return {"YOLODetector": YOLODetector, "resolve_device": resolve_device}[name]
    raise AttributeError(name)
