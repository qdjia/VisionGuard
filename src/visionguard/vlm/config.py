from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from visionguard.config.models import StrictConfigModel


class VLMConfig(StrictConfigModel):
    provider: Literal["local", "mock", "remote"] = "local"
    model_name_or_path: str = "Qwen/Qwen3-VL-2B-Instruct"
    model_revision: str | None = None
    device: str = "auto"
    dtype: Literal["auto", "float32", "float16", "bfloat16"] = "auto"
    max_new_tokens: int = Field(default=512, gt=0)
    temperature: float = Field(default=0, ge=0, le=1)
    timeout_seconds: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    image_max_side: int = Field(default=1008, gt=0)
    structured_output: Literal[True] = True
    prompt_version: str = Field(default="v1", pattern=r"^v\d+$")
    max_detections: int = Field(default=20, ge=0)
    max_ocr_blocks: int = Field(default=50, ge=0)
    max_ocr_chars: int = Field(default=4000, ge=0)
    warmup_enabled: bool = False
    local_files_only: bool = False
    cache_dir: Path = Path("artifacts/huggingface_cache")
    prompts_dir: Path = Path("prompts/vlm")
    artifacts_dir: Path = Path("artifacts/vlm")
    experiment_name: str = Field(default="qwen3_vl_2b_v1", pattern=r"^[a-z0-9][a-z0-9_-]{4,79}$")
    mock_mode: Literal["normal", "sensitive", "malformed", "timeout"] = "normal"
    endpoint: str | None = None
    session_token: str | None = None
    api_version: int = 1


def load_vlm_config(path: str | Path) -> VLMConfig:
    source = Path(path).resolve()
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))["vlm"]
    model_path = str(raw.get("model_name_or_path", ""))
    if model_path.startswith(".") or Path(model_path).is_absolute():
        raw["model_name_or_path"] = str((source.parent / model_path).resolve())
    for key in ("cache_dir", "prompts_dir", "artifacts_dir"):
        if key in raw:
            raw[key] = (source.parent / raw[key]).resolve()
    return VLMConfig.model_validate(raw)
