"""Systematic, evidence-preserving error analysis for VisionGuard."""

from visionguard.error_analysis.analyzer import ErrorAnalyzer
from visionguard.error_analysis.attribution import ErrorAttributionEngine
from visionguard.error_analysis.config import ErrorAnalysisConfig, load_error_analysis_config
from visionguard.error_analysis.schemas import ErrorCase, GroundTruth
from visionguard.error_analysis.taxonomy import FailureStage, FailureType

__all__ = [
    "ErrorAnalysisConfig",
    "ErrorAnalyzer",
    "ErrorAttributionEngine",
    "ErrorCase",
    "FailureStage",
    "FailureType",
    "GroundTruth",
    "load_error_analysis_config",
]
