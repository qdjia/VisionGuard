from typing import Any, Literal

from pydantic import Field

from visionguard.moderation.schemas import ModerationResult
from visionguard.schemas.common import SchemaModel


class VLMRuntimeMeta(SchemaModel):
    api_version: int = 1
    runtime_version: str
    model_bundle_version: str
    model_identifier: str
    prompt_version: str
    model_loaded: bool
    model_init_count: int = 0
    pid: int


class VLMAnalyzeResponse(SchemaModel):
    api_version: int = 1
    result: ModerationResult
    timing: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VLMHealth(SchemaModel):
    status: Literal["ok", "installed", "loading", "ready", "failed"]
    model_loaded: bool = False
    model_init_count: int = 0
