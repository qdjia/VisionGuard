"""Independent, validated text baseline configuration."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class TextPreprocessingConfig(StrictConfigModel):
    lowercase: bool = False


class TfidfConfig(StrictConfigModel):
    analyzer: Literal["char", "char_wb", "word"] = "char"
    ngram_range: tuple[int, int] = (2, 4)
    min_df: int = Field(default=1, ge=1)
    max_df: float = Field(default=1.0, gt=0, le=1)
    max_features: int = Field(default=20000, gt=0)
    sublinear_tf: bool = True

    @model_validator(mode="after")
    def ordered_ngrams(self) -> "TfidfConfig":
        if not 1 <= self.ngram_range[0] <= self.ngram_range[1]:
            raise ValueError("invalid ngram_range")
        return self


class GBDTConfig(StrictConfigModel):
    n_estimators: int = Field(default=100, gt=0)
    learning_rate: float = Field(default=0.05, gt=0)
    max_depth: int = Field(default=3, gt=0)


class BaselineConfig(StrictConfigModel):
    experiment_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{4,79}$")
    train: Path
    val: Path
    test: Path
    artifacts_dir: Path
    decision_threshold: float = Field(default=0.5, ge=0, le=1)
    seed: int = Field(default=42, ge=0)
    recall_target: float = Field(default=0.9, ge=0, le=1)
    preprocessing: TextPreprocessingConfig = Field(default_factory=TextPreprocessingConfig)
    tfidf: TfidfConfig = Field(default_factory=TfidfConfig)
    model: GBDTConfig = Field(default_factory=GBDTConfig)

    @model_validator(mode="after")
    def meaningful_name(self) -> "BaselineConfig":
        if self.experiment_name in {"final", "final2"} or self.experiment_name.startswith("exp"):
            raise ValueError("use a descriptive experiment name")
        return self


def load_baseline_config(path: str | Path) -> BaselineConfig:
    source = Path(path).resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))["baseline"]
        for key in ("train", "val", "test", "artifacts_dir"):
            raw[key] = (source.parent / Path(raw[key]).expanduser()).resolve()
        return BaselineConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid baseline configuration: {source}") from exc
