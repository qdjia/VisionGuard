"""Structured predictions and stable inference timing."""

from typing import Literal

from pydantic import Field

from visionguard.schemas.common import SchemaModel


class TextTiming(SchemaModel):
    preprocess_ms: float = Field(default=0, ge=0)
    vectorize_ms: float = Field(default=0, ge=0)
    classification_ms: float = Field(default=0, ge=0)
    total_ms: float = Field(default=0, ge=0)


class TextModerationPrediction(SchemaModel):
    text: str
    label: Literal["normal", "sensitive"]
    probability: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    source: Literal["text", "ocr"] = "text"
    timing: TextTiming = Field(default_factory=TextTiming)


class BatchTextModerationResult(SchemaModel):
    predictions: list[TextModerationPrediction]
    total: int = Field(ge=0)
    sensitive_count: int = Field(ge=0)
    timing: TextTiming
    samples_per_second: float = Field(ge=0)
