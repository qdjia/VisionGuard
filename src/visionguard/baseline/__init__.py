"""Traditional text moderation baseline, independent from detector/OCR engines."""

from visionguard.baseline.classifier import TextModerationBaseline
from visionguard.baseline.config import load_baseline_config
from visionguard.baseline.trainer import TextBaselineTrainer

__all__ = ["TextModerationBaseline", "TextBaselineTrainer", "load_baseline_config"]
