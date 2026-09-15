"""Single and batch inference; no fitting and no sparse-to-dense conversion."""

from pathlib import Path
from time import perf_counter
from typing import Literal

from visionguard.baseline.config import BaselineConfig, load_baseline_config
from visionguard.baseline.persistence import load_models
from visionguard.baseline.preprocessing import clean_text
from visionguard.baseline.schemas import (
    BatchTextModerationResult,
    TextModerationPrediction,
    TextTiming,
)
from visionguard.schemas import OCRResult


class TextModerationBaseline:
    def __init__(self, vectorizer, model, config: BaselineConfig) -> None:
        self.vectorizer, self.model, self.config = vectorizer, model, config

    @classmethod
    def load(cls, directory: str | Path) -> "TextModerationBaseline":
        directory = Path(directory).resolve()
        vectorizer, model = load_models(directory)
        return cls(vectorizer, model, load_baseline_config(directory / "config.yaml"))

    def predict(self, text: str, *, threshold: float | None = None) -> TextModerationPrediction:
        result = self.predict_batch([text], threshold=threshold)
        return result.predictions[0].model_copy(update={"timing": result.timing})

    def predict_batch(
        self,
        texts: list[str],
        *,
        threshold: float | None = None,
        source: Literal["text", "ocr"] = "text",
    ) -> BatchTextModerationResult:
        threshold = self.config.decision_threshold if threshold is None else threshold
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be within [0,1]")
        start = perf_counter()
        cleaned = [clean_text(t, lowercase=self.config.preprocessing.lowercase) for t in texts]
        prepared = perf_counter()
        if cleaned:
            features = self.vectorizer.transform(cleaned)
            vectorized = perf_counter()
            class_index = list(self.model.classes_).index(1)
            probabilities = self.model.predict_proba(features)[:, class_index]
        else:
            vectorized = perf_counter()
            probabilities = []
        classified = perf_counter()
        predictions = [
            TextModerationPrediction(
                text=text,
                label="sensitive" if probability >= threshold else "normal",
                probability=float(probability),
                threshold=threshold,
                source=source,
            )
            for text, probability in zip(cleaned, probabilities, strict=True)
        ]
        timing = TextTiming(
            preprocess_ms=(prepared - start) * 1000,
            vectorize_ms=(vectorized - prepared) * 1000,
            classification_ms=(classified - vectorized) * 1000,
            total_ms=(perf_counter() - start) * 1000,
        )
        return BatchTextModerationResult(
            predictions=predictions,
            total=len(texts),
            sensitive_count=sum(p.label == "sensitive" for p in predictions),
            timing=timing,
            samples_per_second=len(texts) / max(timing.total_ms / 1000, 1e-9),
        )

    def predict_ocr(self, result: OCRResult) -> TextModerationPrediction:
        prediction = self.predict_batch([result.full_text], source="ocr")
        return prediction.predictions[0].model_copy(update={"timing": prediction.timing})
