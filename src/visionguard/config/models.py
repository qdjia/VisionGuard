"""Strongly typed configuration models shared by all pipeline stages."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfigModel(BaseModel):
    """Base class that catches misspelled or obsolete configuration keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(StrictConfigModel):
    name: str = "visionguard"
    environment: str = "development"
    artifacts_dir: Path
    checkpoints_dir: Path


class DetectionConfig(StrictConfigModel):
    classes_file: Path
    class_names: tuple[str, ...] = ()
    model_path: Path
    conf_threshold: float = Field(ge=0.0, le=1.0)
    iou_threshold: float = Field(ge=0.0, le=1.0)
    max_det: int = Field(default=300, gt=0)
    image_size: int = Field(gt=0)
    device: str = "auto"
    half_precision: bool = True
    warmup_enabled: bool = True
    warmup_runs: int = Field(default=1, ge=1, le=2)
    class_name_mapping: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_classes(self) -> "DetectionConfig":
        if not self.class_names:
            raise ValueError("detection class list must not be empty")
        if len(set(self.class_names)) != len(self.class_names):
            raise ValueError("detection class names must be unique")
        return self

    @model_validator(mode="after")
    def validate_device(self) -> "DetectionConfig":
        if not self.device.strip():
            raise ValueError("device must not be empty")
        return self


class OCRConfig(StrictConfigModel):
    language: str = "ch"
    use_angle_cls: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_roi_ocr: bool = True


class VLMConfig(StrictConfigModel):
    provider: str
    model: str
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)


class CascadeConfig(StrictConfigModel):
    enabled: bool = True
    high_confidence_threshold: float = Field(ge=0.0, le=1.0)
    low_confidence_threshold: float = Field(ge=0.0, le=1.0)
    call_vlm_on_conflict: bool = True

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "CascadeConfig":
        if self.low_confidence_threshold >= self.high_confidence_threshold:
            raise ValueError("low threshold must be lower than high threshold")
        return self


class AppConfig(StrictConfigModel):
    project: ProjectConfig
    detection: DetectionConfig
    ocr: OCRConfig
    vlm: VLMConfig
    cascade: CascadeConfig
