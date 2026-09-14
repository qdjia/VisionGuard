"""Validated, path-aware detector training configuration."""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError, field_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class AugmentationConfig(StrictConfigModel):
    hsv_h: float = Field(ge=0, le=1)
    hsv_s: float = Field(ge=0, le=1)
    hsv_v: float = Field(ge=0, le=1)
    degrees: float = Field(ge=0, le=180)
    translate: float = Field(ge=0, le=1)
    scale: float = Field(ge=0, le=1)
    shear: float = Field(ge=0, le=180)
    perspective: float = Field(ge=0, le=0.001)
    flipud: float = Field(ge=0, le=1)
    fliplr: float = Field(ge=0, le=1)
    mosaic: float = Field(ge=0, le=1)
    mixup: float = Field(ge=0, le=1)


class TrainConfig(StrictConfigModel):
    experiment_name: str
    model: str = Field(min_length=1)
    data: Path
    artifacts_dir: Path
    config_path: Path | None = None
    epochs: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    image_size: int = Field(gt=0)
    device: str = "auto"
    workers: int = Field(ge=0)
    seed: int = Field(ge=0)
    deterministic: bool = True
    optimizer: str = Field(min_length=1)
    learning_rate: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    warmup_epochs: float = Field(ge=0)
    patience: int = Field(ge=0)
    amp: bool = True
    resume: bool | Path = False
    pretrained: bool = True
    save_period: int = Field(ge=-1)
    validation_sample_count: int = Field(default=20, ge=0)
    augmentation: AugmentationConfig

    @field_validator("experiment_name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{4,79}", value) or re.fullmatch(r"exp\d*", value):
            raise ValueError("experiment_name must be a descriptive lowercase slug")
        if value in {"final", "test"}:
            raise ValueError("experiment_name is too generic")
        return value


def _resolve(value: str | Path, base: Path) -> Path:
    candidate = Path(value).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def load_train_config(path: str | Path) -> TrainConfig:
    config_path = Path(path).expanduser().resolve()
    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"failed to read training config: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigLoadError(f"training config root must be a mapping: {config_path}")
    normalized = {
        **raw,
        "data": _resolve(raw.get("data", ""), config_path.parent),
        "artifacts_dir": _resolve(raw.get("artifacts_dir", ""), config_path.parent),
        "config_path": config_path,
    }
    if isinstance(normalized.get("resume"), str):
        normalized["resume"] = _resolve(normalized["resume"], config_path.parent)
    try:
        return TrainConfig.model_validate(normalized)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid training configuration: {config_path}\n{exc}") from exc
