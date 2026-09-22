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
        values = raw["ocr"]
        for key in (
            "text_detection_model_dir",
            "text_recognition_model_dir",
            "textline_orientation_model_dir",
        ):
            if values.get(key) is not None:
                candidate = Path(values[key]).expanduser()
                values[key] = (
                    candidate if candidate.is_absolute() else config_path.parent / candidate
                ).resolve()
        return OCRConfig.model_validate(values)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid OCR configuration: {config_path}\n{exc}") from exc
