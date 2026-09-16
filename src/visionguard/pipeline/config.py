"""Validated configuration for the Phase 7 synchronous review pipeline."""

from pathlib import Path

import yaml
from pydantic import Field, ValidationError

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class TraceConfig(StrictConfigModel):
    enabled: bool = True


class PipelineConfig(StrictConfigModel):
    save_artifacts: bool = True
    artifact_root: Path = Path("artifacts/pipeline")
    save_input_copy: bool = False
    enable_detector: bool = True
    enable_ocr: bool = True
    enable_text_baseline: bool = True
    enable_vlm: bool = True
    fail_fast: bool = False
    save_intermediate_json: bool = True
    save_visualizations: bool = True
    pipeline_version: str = Field(default="v1", pattern=r"^v\d+$")
    max_ocr_chars_for_baseline: int = Field(default=4000, gt=0)
    trace: TraceConfig = Field(default_factory=TraceConfig)


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        values = raw["pipeline"]
        if "artifact_root" in values:
            values["artifact_root"] = (source.parent / values["artifact_root"]).resolve()
        return PipelineConfig.model_validate(values)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid pipeline configuration: {source}") from exc
