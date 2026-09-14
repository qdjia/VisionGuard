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


class OCRPreprocessingConfig(StrictConfigModel):
    enabled: bool = False
    grayscale: bool = False
    contrast_enhancement: bool = False
    denoise: bool = False
    sharpen: bool = False


class OCRConfig(StrictConfigModel):
    provider: str = "paddleocr"
    lang: str = "ch"
    device: str = "auto"
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    use_textline_orientation: bool = True
    det_enabled: bool = True
    rec_enabled: bool = True
    max_side_len: int = Field(default=1920, gt=0)
    warmup_enabled: bool = True
    fallback_full_image: bool = True
    preprocessing: OCRPreprocessingConfig = Field(default_factory=OCRPreprocessingConfig)

    @model_validator(mode="after")
    def validate_backend_options(self) -> "OCRConfig":
        if self.provider.lower() != "paddleocr":
            raise ValueError(
                "Phase 4 supports provider='paddleocr'; use an adapter for another backend"
            )
        if not self.device.strip():
            raise ValueError("OCR device must not be empty")
        return self


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
