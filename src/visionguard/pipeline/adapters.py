"""Narrow dependency protocols and the Phase 5 baseline adapter."""

from typing import Protocol

import numpy as np

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.schemas import DetectionResult, OCRResult


class DetectorProtocol(Protocol):
    def predict(self, image: np.ndarray) -> DetectionResult: ...

    def predict_batch(self, images: list[np.ndarray]) -> list[DetectionResult]: ...


class OCRProtocol(Protocol):
    def recognize(self, image: np.ndarray) -> OCRResult: ...


class TextBaselineProtocol(Protocol):
    experiment_name: str

    def predict(self, text: str) -> TextModerationPrediction: ...

    def predict_batch(self, texts: list[str]) -> list[TextModerationPrediction]: ...


class TextBaselineAdapter:
    """Expose a minimal OCR-text interface over the Phase 5 classifier."""

    def __init__(self, baseline) -> None:
        self._baseline = baseline
        self.experiment_name = baseline.config.experiment_name

    def predict(self, text: str) -> TextModerationPrediction:
        result = self._baseline.predict_batch([text], source="ocr")
        return result.predictions[0].model_copy(update={"timing": result.timing})

    def predict_batch(self, texts: list[str]) -> list[TextModerationPrediction]:
        result = self._baseline.predict_batch(texts, source="ocr")
        return [item.model_copy(update={"timing": result.timing}) for item in result.predictions]
