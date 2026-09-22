"""Strict configuration for the single-process inference service."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from visionguard.config import ConfigLoadError
from visionguard.config.models import StrictConfigModel


class APISettings(StrictConfigModel):
    service_name: str = "VisionGuard API"
    service_version: str = "0.1.0"
    api_version: Literal["v1"] = "v1"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    default_pipeline_mode: Literal["full", "cascaded"] = "cascaded"
    allowed_pipeline_modes: tuple[Literal["full", "cascaded"], ...] = (
        "full",
        "cascaded",
    )
    max_upload_mb: int = Field(default=15, ge=1, le=100)
    upload_chunk_kb: int = Field(default=1024, ge=64, le=4096)
    allowed_image_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )
    max_image_dimension: int = Field(default=12000, ge=64)
    max_image_pixels: int = Field(default=40_000_000, ge=4096)
    request_timeout_seconds: float = Field(default=90, gt=0)
    shutdown_grace_seconds: float = Field(default=120, gt=0)
    max_concurrent_inference: int = Field(default=1, ge=1, le=8)
    save_artifacts: bool = True
    warmup_on_startup: bool = True
    expose_internal_errors: bool = False
    docs_enabled: bool = True
    deferred_startup: bool = False
    runtime_version: str | None = None
    model_bundle_version: str | None = None

    @model_validator(mode="after")
    def validate_modes_and_types(self) -> "APISettings":
        if self.default_pipeline_mode not in self.allowed_pipeline_modes:
            raise ValueError("default_pipeline_mode must be allowed")
        if len(set(self.allowed_pipeline_modes)) != len(self.allowed_pipeline_modes):
            raise ValueError("allowed_pipeline_modes must be unique")
        if not self.allowed_image_types or any(
            not value.startswith("image/") for value in self.allowed_image_types
        ):
            raise ValueError("allowed_image_types must contain image MIME types")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_chunk_bytes(self) -> int:
        return self.upload_chunk_kb * 1024


class ServicePaths(StrictConfigModel):
    detector_config: Path
    ocr_config: Path
    baseline_config: Path
    vlm_config: Path
    moderation_policy: Path
    fusion_config: Path
    routing_config: Path
    full_pipeline_config: Path
    cascaded_pipeline_config: Path


class APIConfig(StrictConfigModel):
    api: APISettings
    services: ServicePaths


def load_api_config(path: str | Path) -> APIConfig:
    source = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        services = raw["services"]
        for key, value in services.items():
            candidate = Path(value).expanduser()
            services[key] = (
                candidate if candidate.is_absolute() else source.parent / candidate
            ).resolve()
        return APIConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid API configuration: {source}") from exc
