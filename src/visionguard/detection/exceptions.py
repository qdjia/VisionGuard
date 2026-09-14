"""Backward-compatible detector exception exports."""

from visionguard.core.exceptions import (
    DetectorError,
    DetectorLoadError,
    ImageLoadError,
    InferenceError,
)

__all__ = ["DetectorError", "DetectorLoadError", "ImageLoadError", "InferenceError"]
