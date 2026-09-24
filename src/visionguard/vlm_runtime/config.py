from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from visionguard.config.models import StrictConfigModel


class VLMRuntimeConfig(StrictConfigModel):
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=0, ge=0, le=65535)
    model_path: Path
    cache_root: Path
    log_root: Path
    prompts_dir: Path
    prompt_version: str = "v1"
    model_bundle_version: str = "vlm-models-v1"
    model_revision: str | None = None
    device: str = "auto"
    dtype: str = "auto"
    timeout_seconds: float = Field(default=120, gt=0)
    load_timeout_seconds: float = Field(default=300, gt=0)
    max_new_tokens: int = Field(default=512, gt=0)

    @model_validator(mode="after")
    def paths_are_absolute(self):
        for name in ("model_path", "cache_root", "log_root", "prompts_dir"):
            if not getattr(self, name).is_absolute():
                raise ValueError(f"{name} must be absolute")
        return self


def load_vlm_runtime_config(path: str | Path) -> VLMRuntimeConfig:
    source = Path(path).resolve()
    return VLMRuntimeConfig.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))
