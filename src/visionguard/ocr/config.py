"""Standalone OCR configuration loader."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from visionguard.config import ConfigLoadError
from visionguard.config.models import OCRConfig


def load_ocr_config(path: str | Path) -> OCRConfig:
    config_path = Path(path).expanduser().resolve()
    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"failed to read OCR config: {config_path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("ocr"), dict):
        raise ConfigLoadError(f"OCR config must contain an 'ocr' mapping: {config_path}")
    try:
        return OCRConfig.model_validate(raw["ocr"])
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid OCR configuration: {config_path}\n{exc}") from exc
