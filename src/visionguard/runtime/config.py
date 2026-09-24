"""Validated runtime config and materialized service configuration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.api.config import APIConfig, load_api_config
from visionguard.config.models import StrictConfigModel


class RuntimeConfig(StrictConfigModel):
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=0, ge=0, le=65535)
    model_bundle_path: Path
    user_data_dir: Path
    artifact_root: Path
    log_root: Path
    cache_root: Path
    max_concurrent_inference: int = Field(default=1, ge=1, le=8)
    save_artifacts: bool = False
    # Component constructors already load the models once.  Keep the expensive
    # end-to-end VLM warmup opt-in for the desktop runtime so readiness is not
    # coupled to a synthetic generation request.
    warmup_on_startup: bool = False
    log_level: str = "INFO"
    log_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    log_backup_count: int = Field(default=3, ge=1, le=20)
    model_validation: Literal["quick", "full"] = "quick"
    readiness_timeout_seconds: float = Field(default=120, gt=0, le=900)
    runtime_edition: Literal["gpu", "cpu"] = "gpu"
    minimum_free_disk_bytes: int = Field(default=512 * 1024 * 1024, ge=0)

    @model_validator(mode="after")
    def absolute_paths(self) -> RuntimeConfig:
        for field in (
            "model_bundle_path",
            "user_data_dir",
            "artifact_root",
            "log_root",
            "cache_root",
        ):
            if not getattr(self, field).is_absolute():
                raise ValueError(f"{field} must be an absolute path")
        return self


def load_runtime_config(path: str | Path) -> RuntimeConfig:
    source = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("runtime config root must be a mapping")
        return RuntimeConfig.model_validate(payload)
    except (OSError, TypeError, yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"invalid runtime config: {source}") from exc


def _read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")
    return value


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def materialize_api_config(
    runtime: RuntimeConfig,
    *,
    resource_root: Path,
    run_dir: Path,
    bundle_version: str,
    model_paths: dict[str, Path],
) -> APIConfig:
    """Create per-run configs without mutating packaged read-only resources."""

    source_configs = resource_root / "configs"
    generated = run_dir / "configs"
    generated.mkdir(parents=True, exist_ok=True)

    classes = source_configs / "classes.yaml"
    (generated / "classes.yaml").write_text(classes.read_text(encoding="utf-8"), encoding="utf-8")

    detector = deepcopy(_read_yaml(source_configs / "detector.yaml"))
    detector["project"]["artifacts_dir"] = str(runtime.artifact_root)
    detector["project"]["checkpoints_dir"] = str(model_paths["detector"].parent)
    detector["detection"]["classes_file"] = "classes.yaml"
    detector["detection"]["model_path"] = str(model_paths["detector"])
    if model_paths["detector"].suffix.lower() == ".onnx":
        detector["detection"]["provider"] = "onnx"
        detector["detection"]["onnx_execution_provider"] = (
            "cpu" if runtime.runtime_edition == "cpu" else "auto"
        )
    _write_yaml(generated / "detector.yaml", detector)

    ocr = deepcopy(_read_yaml(source_configs / "ocr.yaml"))
    ocr["ocr"].update(
        {
            "text_detection_model_dir": str(model_paths["ocr_detection"]),
            "text_recognition_model_dir": str(model_paths["ocr_recognition"]),
            "textline_orientation_model_dir": str(model_paths["ocr_orientation"]),
            "local_models_only": True,
            "device": "cpu" if runtime.runtime_edition == "cpu" else "auto",
        }
    )
    _write_yaml(generated / "ocr.yaml", ocr)

    baseline = deepcopy(_read_yaml(model_paths["baseline"] / "config.yaml"))
    baseline["baseline"]["artifacts_dir"] = str(model_paths["baseline"].parent)
    # Dataset paths are a training-only part of the stable schema. Keep them local
    # and inert for packaged inference.
    for key in ("train", "val", "test"):
        baseline["baseline"][key] = str(model_paths["baseline"] / f"unused-{key}.csv")
    _write_yaml(generated / "baseline.yaml", baseline)

    vlm = deepcopy(_read_yaml(source_configs / "local_vlm.yaml"))
    vlm["vlm"].update(
        {
            "provider": "remote",
            "model_name_or_path": "optional-advanced-ai",
            "endpoint": None,
            "session_token": None,
            "api_version": 1,
            "local_files_only": True,
            "cache_dir": str(runtime.cache_root / "huggingface"),
            "prompts_dir": str(resource_root / "prompts" / "vlm"),
            "artifacts_dir": str(runtime.artifact_root / "vlm"),
        }
    )
    _write_yaml(generated / "vlm.yaml", vlm)

    for name in ("pipeline.yaml", "pipeline_cascaded.yaml"):
        pipeline = deepcopy(_read_yaml(source_configs / name))
        pipeline["pipeline"].update(
            {
                "save_artifacts": runtime.save_artifacts,
                "artifact_root": str(runtime.artifact_root / "pipeline"),
                "save_input_copy": False,
                "save_intermediate_json": runtime.save_artifacts,
                "save_visualizations": runtime.save_artifacts,
                # A lightweight remote registry is always present. Availability
                # changes at runtime without rebuilding either pipeline.
                "enable_vlm": True,
            }
        )
        _write_yaml(generated / name, pipeline)

    api = deepcopy(_read_yaml(source_configs / "api.yaml"))
    api["api"].update(
        {
            "host": runtime.host,
            "port": runtime.port,
            "max_concurrent_inference": runtime.max_concurrent_inference,
            "save_artifacts": runtime.save_artifacts,
            "warmup_on_startup": runtime.warmup_on_startup,
            "docs_enabled": False,
            "deferred_startup": True,
            "runtime_version": "0.1.0",
            "model_bundle_version": bundle_version,
        }
    )
    api["services"] = {
        "detector_config": str(generated / "detector.yaml"),
        "ocr_config": str(generated / "ocr.yaml"),
        "baseline_config": str(generated / "baseline.yaml"),
        "vlm_config": str(generated / "vlm.yaml"),
        "moderation_policy": str(source_configs / "moderation_policy.yaml"),
        "fusion_config": str(source_configs / "fusion.yaml"),
        "routing_config": str(source_configs / "routing.yaml"),
        "full_pipeline_config": str(generated / "pipeline.yaml"),
        "cascaded_pipeline_config": str(generated / "pipeline_cascaded.yaml"),
    }
    api_path = generated / "api.yaml"
    _write_yaml(api_path, api)
    return load_api_config(api_path)
