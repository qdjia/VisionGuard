"""Machine-readable training and evaluation outputs."""

from pathlib import Path

from pydantic import Field

from visionguard.schemas.common import SchemaModel


class ClassMetrics(SchemaModel):
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    ap50: float = Field(ge=0, le=1)
    map50_95: float = Field(ge=0, le=1)


class DetectionMetrics(SchemaModel):
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    map50: float = Field(ge=0, le=1)
    map50_95: float = Field(ge=0, le=1)
    per_class: dict[str, ClassMetrics] = Field(default_factory=dict)


class TrainingSummary(SchemaModel):
    experiment_name: str
    model: str
    dataset: Path
    epochs: int
    best_epoch: int | None = None
    best_checkpoint: Path
    last_checkpoint: Path
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    map50: float = Field(ge=0, le=1)
    map50_95: float = Field(ge=0, le=1)
    training_time_seconds: float = Field(ge=0)
    average_epoch_time_seconds: float = Field(ge=0)
    device: str
    seed: int
    config_path: Path | None = None


class TrainingResult(SchemaModel):
    experiment_dir: Path
    metrics_path: Path
    summary_path: Path
    config_snapshot_path: Path
    summary: TrainingSummary
