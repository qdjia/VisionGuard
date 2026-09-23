"""Backend boundary for deployment-time object detectors."""

from __future__ import annotations

from typing import Protocol

from visionguard.schemas import DetectionResult
from visionguard.utils.image import ImageInput


class DetectorProvider(Protocol):
    """Stable contract shared by training/reference and release detectors."""

    @property
    def is_warmed_up(self) -> bool: ...

    def warmup(self) -> None: ...

    def predict(self, image: ImageInput) -> DetectionResult: ...

    def predict_batch(self, images: list[ImageInput]) -> list[DetectionResult]: ...
