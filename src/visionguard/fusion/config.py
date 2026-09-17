"""Validated configuration for explainable rule/weighted risk fusion."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class DetectorFusionConfig(StrictConfigModel):
    high_risk_conf_threshold: float = Field(ge=0, le=1)
    suspicious_conf_threshold: float = Field(ge=0, le=1)
    class_severity: dict[str, float] = Field(min_length=1)
    hard_override_min_count: int = Field(default=2, ge=2)

    @model_validator(mode="after")
    def valid_detector_settings(self) -> "DetectorFusionConfig":
        if self.suspicious_conf_threshold > self.high_risk_conf_threshold:
            raise ValueError("suspicious threshold must not exceed high-risk threshold")
        if any(not 0 <= value <= 1 for value in self.class_severity.values()):
            raise ValueError("class severity values must be within [0, 1]")
        return self


class BaselineFusionConfig(StrictConfigModel):
    safe_threshold: float = Field(ge=0, le=1)
    risky_threshold: float = Field(ge=0, le=1)
    min_ocr_reliability: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered_thresholds(self) -> "BaselineFusionConfig":
        if self.safe_threshold >= self.risky_threshold:
            raise ValueError("safe_threshold must be lower than risky_threshold")
        return self


class VLMFusionConfig(StrictConfigModel):
    trust_enabled: bool = True
    use_confidence_scaling: bool = False
    level_scores: dict[Literal["low", "medium", "high"], float]

    @model_validator(mode="after")
    def valid_level_scores(self) -> "VLMFusionConfig":
        if set(self.level_scores) != {"low", "medium", "high"}:
            raise ValueError("VLM level_scores must define low/medium/high")
        if any(not 0 <= value <= 1 for value in self.level_scores.values()):
            raise ValueError("VLM level scores must be within [0, 1]")
        if not (self.level_scores["low"] < self.level_scores["medium"] < self.level_scores["high"]):
            raise ValueError("VLM level scores must be strictly ordered")
        return self


class FusionWeights(StrictConfigModel):
    visual: float = Field(ge=0)
    text: float = Field(ge=0)
    vlm: float = Field(ge=0)

    @model_validator(mode="after")
    def positive_total(self) -> "FusionWeights":
        if self.visual + self.text + self.vlm <= 0:
            raise ValueError("at least one fusion weight must be positive")
        return self


class ConflictFusionConfig(StrictConfigModel):
    force_manual_review: bool = True


class FailureFusionConfig(StrictConfigModel):
    force_manual_review: bool = True
    minimum_risk_level: Literal["medium"] = "medium"


class RiskMappingConfig(StrictConfigModel):
    low_max: float = Field(ge=0, le=1)
    medium_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered_boundaries(self) -> "RiskMappingConfig":
        if self.low_max >= self.medium_max:
            raise ValueError("low_max must be lower than medium_max")
        return self


class FusionConfig(StrictConfigModel):
    version: str = Field(pattern=r"^fusion_v\d+$")
    strategy: Literal["weighted", "hard_rule", "vlm_only"] = "weighted"
    conservative_mode: bool = True
    detector: DetectorFusionConfig
    baseline: BaselineFusionConfig
    vlm: VLMFusionConfig
    weights: FusionWeights
    conflict: ConflictFusionConfig = Field(default_factory=ConflictFusionConfig)
    failure: FailureFusionConfig = Field(default_factory=FailureFusionConfig)
    risk_mapping: RiskMappingConfig
    uncertainty_margin: float = Field(default=0.05, ge=0, le=0.25)


def load_fusion_config(path: str | Path) -> FusionConfig:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        return FusionConfig.model_validate(raw["fusion"])
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid fusion configuration: {source}") from exc
