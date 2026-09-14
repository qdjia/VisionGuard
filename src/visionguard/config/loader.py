"""YAML configuration loader with deterministic relative-path handling."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from visionguard.config.models import AppConfig


class ConfigLoadError(RuntimeError):
    """Raised when configuration files cannot be read or validated."""


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            content = yaml.safe_load(stream) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"failed to read YAML configuration: {path}") from exc
    if not isinstance(content, dict):
        raise ConfigLoadError(f"YAML root must be a mapping: {path}")
    return content


def _resolve_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def load_config(path: str | Path) -> AppConfig:
    """Load the application config and its externally managed detector classes."""

    config_path = Path(path).expanduser().resolve()
    raw = _read_yaml(config_path)
    base_dir = config_path.parent

    try:
        project = raw["project"]
        detection = raw["detection"]
        classes_path = _resolve_path(detection["classes_file"], base_dir)
    except (KeyError, TypeError) as exc:
        raise ConfigLoadError(f"missing or malformed required configuration in {config_path}") from exc

    classes_raw = _read_yaml(classes_path)
    class_names = classes_raw.get("classes")
    if not isinstance(class_names, list) or not all(isinstance(name, str) for name in class_names):
        raise ConfigLoadError(f"'classes' must be a list of strings: {classes_path}")

    normalized = dict(raw)
    normalized["project"] = {
        **project,
        "artifacts_dir": _resolve_path(project["artifacts_dir"], base_dir),
        "checkpoints_dir": _resolve_path(project["checkpoints_dir"], base_dir),
    }
    normalized["detection"] = {
        **detection,
        "classes_file": classes_path,
        "class_names": tuple(class_names),
        "model_path": _resolve_path(detection["model_path"], base_dir),
    }

    try:
        return AppConfig.model_validate(normalized)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid application configuration: {config_path}\n{exc}") from exc

