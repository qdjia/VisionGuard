"""Stable, serializable contracts between algorithm and service modules."""

from visionguard.schemas.common import BoundingBox, ImageReference
from visionguard.schemas.detection import Detection, DetectionResult, TimingInfo
from visionguard.schemas.moderation import Evidence, ModerationResult, RiskLevel
from visionguard.schemas.ocr import OCRResult, OCRTextBlock
from visionguard.schemas.pipeline import DecisionSource, PipelineResult, StageTimings

__all__ = [
    "BoundingBox",
    "DecisionSource",
    "Detection",
    "DetectionResult",
    "Evidence",
    "ImageReference",
    "ModerationResult",
    "OCRResult",
    "OCRTextBlock",
    "PipelineResult",
    "RiskLevel",
    "StageTimings",
    "TimingInfo",
]
