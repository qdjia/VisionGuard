"""Versioned configuration for deterministic rule-based routing."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class BaselineRoutingConfig(StrictConfigModel):
    safe_threshold: float = Field(ge=0, le=1)
    risky_threshold: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "BaselineRoutingConfig":
        if self.safe_threshold >= self.risky_threshold:
            raise ValueError("safe_threshold must be lower than risky_threshold")
        return self


class DetectorRoutingConfig(StrictConfigModel):
    high_risk_conf_threshold: float = Field(ge=0, le=1)
    suspicious_conf_threshold: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "DetectorRoutingConfig":
        if self.suspicious_conf_threshold > self.high_risk_conf_threshold:
            raise ValueError("suspicious threshold must not exceed high-risk threshold")
        return self


class OCRRoutingConfig(StrictConfigModel):
    min_mean_confidence: float = Field(ge=0, le=1)
    min_text_length: int = Field(ge=1)


class FailureRoutingConfig(StrictConfigModel):
    # Phase 8 never permits failed Stage 1 modules to fast-pass.
    route_to_vlm: Literal[True] = True


class RoutingConfig(StrictConfigModel):
    version: str = Field(pattern=r"^routing_v\d+$")
    conservative_mode: bool = True
    baseline: BaselineRoutingConfig
    detector: DetectorRoutingConfig
    ocr: OCRRoutingConfig
    high_risk_classes: tuple[str, ...] = Field(min_length=1)
    failure: FailureRoutingConfig = Field(default_factory=FailureRoutingConfig)

    @model_validator(mode="after")
    def unique_classes(self) -> "RoutingConfig":
        if len(set(self.high_risk_classes)) != len(self.high_risk_classes):
            raise ValueError("high_risk_classes must be unique")
        return self


def load_routing_config(path: str | Path) -> RoutingConfig:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        return RoutingConfig.model_validate(raw["routing"])
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid routing configuration: {source}") from exc
