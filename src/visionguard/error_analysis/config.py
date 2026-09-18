"""Validated configuration for deterministic error analysis."""

from pathlib import Path

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel
from visionguard.error_analysis.schemas import FailureSeverity


class HardCaseConfig(StrictConfigModel):
    include_severities: tuple[FailureSeverity, ...]
    include_boundary_cases: bool = True
    regression_severities: tuple[FailureSeverity, ...] = (
        FailureSeverity.CRITICAL,
        FailureSeverity.HIGH,
    )
    require_verified_annotation: bool = True


class ReportConfig(StrictConfigModel):
    top_error_count: int = Field(default=20, ge=1)
    low_sample_warning_threshold: int = Field(default=10, ge=1)


class ErrorAnalysisConfig(StrictConfigModel):
    version: str = Field(pattern=r"^error_analysis_v\d+$")
    experiment_name: str = Field(min_length=1)
    output_root: Path
    cer_threshold: float = Field(default=0.3, ge=0)
    detection_iou_threshold: float = Field(default=0.5, ge=0, le=1)
    high_confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    boundary_margin: float = Field(default=0.05, ge=0, le=0.25)
    routing_boundaries: tuple[float, ...] = (0.1, 0.8)
    fusion_boundaries: tuple[float, ...] = (0.3, 0.7)
    confidence_bins: tuple[float, ...] = (0, 0.3, 0.5, 0.7, 0.9, 1.0)
    severity: dict[str, FailureSeverity]
    hard_cases: HardCaseConfig
    report: ReportConfig = Field(default_factory=ReportConfig)

    @model_validator(mode="after")
    def ordered_bins(self) -> "ErrorAnalysisConfig":
        if len(self.confidence_bins) < 2 or self.confidence_bins[0] != 0:
            raise ValueError("confidence_bins must start at zero")
        if (
            self.confidence_bins[-1] != 1
            or tuple(sorted(set(self.confidence_bins))) != self.confidence_bins
        ):
            raise ValueError("confidence_bins must be unique, ordered, and end at one")
        return self


def load_error_analysis_config(path: str | Path) -> ErrorAnalysisConfig:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        return ErrorAnalysisConfig.model_validate(raw["error_analysis"])
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid error-analysis configuration: {source}") from exc
