"""Explainable multimodal risk fusion."""

from visionguard.fusion.config import FusionConfig, load_fusion_config
from visionguard.fusion.engine import RiskFusionEngine
from visionguard.fusion.normalization import build_fusion_signals, normalize_available_weights
from visionguard.fusion.schemas import FusionDecision, FusionSignals

__all__ = [
    "FusionConfig",
    "FusionDecision",
    "FusionSignals",
    "RiskFusionEngine",
    "build_fusion_signals",
    "load_fusion_config",
    "normalize_available_weights",
]
