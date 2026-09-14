"""Common value objects used by multiple model stages."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundingBox(SchemaModel):
    # Coordinates may extend beyond an image before a consumer clamps them.
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def validate_order(self) -> "BoundingBox":
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bbox must have positive width and height")
        return self


class ImageReference(SchemaModel):
    image_id: str = Field(min_length=1)
    source: str | None = None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
