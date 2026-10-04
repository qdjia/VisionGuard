from pathlib import Path

import yaml
from pydantic import Field, model_validator

from visionguard.config.models import StrictConfigModel


class PolicyDescription(StrictConfigModel):
    description: str = Field(min_length=1)
    semantic_cues: tuple[str, ...] = ()
    negative_cues: tuple[str, ...] = ()

    @model_validator(mode="after")
    def check_cues(self) -> "PolicyDescription":
        normalized = [cue.strip().casefold() for cue in (*self.semantic_cues, *self.negative_cues)]
        if any(not cue for cue in normalized):
            raise ValueError("policy cues must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("policy cues must be unique within a category")
        return self


class ModerationPolicy(StrictConfigModel):
    version: str = Field(min_length=1)
    categories: dict[str, PolicyDescription] = Field(min_length=1)
    risk_levels: dict[str, PolicyDescription]

    @model_validator(mode="after")
    def check_levels(self) -> "ModerationPolicy":
        if set(self.risk_levels) != {"low", "medium", "high"}:
            raise ValueError("policy must define low/medium/high")
        return self


def load_policy(path: str | Path) -> ModerationPolicy:
    result = ModerationPolicy.model_validate(
        yaml.safe_load(Path(path).read_text(encoding="utf-8"))["policy"]
    )
    if set(result.risk_levels) != {"low", "medium", "high"}:
        raise ValueError("policy must define low/medium/high")
    return result
