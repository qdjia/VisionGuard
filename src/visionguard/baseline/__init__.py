"""Traditional text moderation baseline with lazy implementation imports."""


def __getattr__(name):
    if name == "TextModerationBaseline":
        from visionguard.baseline.classifier import TextModerationBaseline

        return TextModerationBaseline
    if name == "TextBaselineTrainer":
        from visionguard.baseline.trainer import TextBaselineTrainer

        return TextBaselineTrainer
    if name == "load_baseline_config":
        from visionguard.baseline.config import load_baseline_config

        return load_baseline_config
    raise AttributeError(name)


__all__ = ["TextModerationBaseline", "TextBaselineTrainer", "load_baseline_config"]
