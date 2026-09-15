import math
from typing import Literal

from pydantic import Field, field_validator, model_validator

from visionguard.schemas.common import BoundingBox, SchemaModel
from visionguard.schemas.moderation import Evidence as LegacyEvidence
from visionguard.schemas.moderation import ModerationResult as LegacyModerationResult


class ModerationCategory(SchemaModel):
    name: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)


class ModerationEvidence(SchemaModel):
    type: Literal["visual", "ocr", "detector", "semantic", "baseline"]
    description: str = Field(min_length=1)
    bbox: BoundingBox | None = None
    text: str | None = None

    @field_validator("bbox", mode="before")
    @classmethod
    def canonical_bbox(cls, value):
        if isinstance(value, list):
            if len(value) != 4 or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
            ):
                raise ValueError("bbox array must contain exactly four numeric coordinates")
            return dict(zip(("x1", "y1", "x2", "y2"), value, strict=True))
        return value

    @field_validator("bbox")
    @classmethod
    def finite_bbox(cls, value):
        if value is not None and not all(math.isfinite(v) for v in value.model_dump().values()):
            raise ValueError("evidence bbox coordinates must be finite")
        return value


class ModerationResult(LegacyModerationResult):
    """New VLM contract; legacy phase-1 contracts remain unchanged."""

    categories: list[ModerationCategory] = Field(default_factory=list)
    evidence: list[ModerationEvidence] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    confidence: float = Field(default=0, ge=0, le=1, exclude=True)
    confidence_score: float = Field(ge=0, le=1)
    requires_manual_review: bool
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_evidence(self) -> "ModerationResult":
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if self.risk_level == "high" and not self.evidence:
            raise ValueError("high risk requires evidence")
        if len({c.name for c in self.categories}) != len(self.categories):
            raise ValueError("duplicate category")
        self.confidence = self.confidence_score
        return self

    def to_legacy(self) -> LegacyModerationResult:
        """Explicit compatibility conversion; never rely on parent subtype serialization."""
        return LegacyModerationResult(
            risk_level=self.risk_level,
            categories=[category.name for category in self.categories],
            reason=self.reason,
            confidence=self.confidence_score,
            evidence=[
                LegacyEvidence(source=item.type, description=item.description, bbox=item.bbox)
                for item in self.evidence
            ],
        )
