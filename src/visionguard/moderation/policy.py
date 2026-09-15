from pathlib import Path

import yaml
from pydantic import Field, model_validator

from visionguard.config.models import StrictConfigModel


class PolicyDescription(StrictConfigModel):
    description: str = Field(min_length=1)


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
