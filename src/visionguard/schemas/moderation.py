"""Strict structured moderation output shared by rules and VLM providers."""

from enum import StrEnum

from pydantic import Field

from visionguard.schemas.common import BoundingBox, SchemaModel


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evidence(SchemaModel):
    source: str = Field(min_length=1)
    description: str = Field(min_length=1)
    bbox: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ModerationResult(SchemaModel):
    risk_level: RiskLevel
    categories: list[str] = Field(default_factory=list)
    reason: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

