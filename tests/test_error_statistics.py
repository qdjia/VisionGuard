from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.schemas import (
    AttributionConfidence,
    ErrorCase,
    FailureSeverity,
    GroundTruth,
)
from visionguard.error_analysis.statistics import calculate_statistics
from visionguard.error_analysis.taxonomy import FailureStage, FailureType


def test_statistics_include_confidence_bins_boundary_and_fusion_value() -> None:
    record = {
        "image": "x.png",
        "ground_truth": {"risk_level": "high"},
        "decision": {
            "risk_level": "medium",
            "risk_score": 0.69,
            "signals": {"max_detection_confidence": 0.95, "vlm_confidence_score": 0.8},
        },
        "result": {"vlm": {"risk_level": "high"}},
    }
    case = ErrorCase(
        case_id="1" * 16,
        image="x.png",
        image_hash="2" * 64,
        ground_truth=GroundTruth(risk_level="high"),
        prediction=record["decision"],
        primary_failure=FailureType.WRONG_RISK_LEVEL,
        failure_stage=FailureStage.END_TO_END,
        observed_failures=[FailureType.WRONG_RISK_LEVEL],
        severity=FailureSeverity.HIGH,
        attribution_confidence=AttributionConfidence.HIGH,
    )
    stats = calculate_statistics(
        [record], [case], load_error_analysis_config("configs/error_analysis.yaml")
    )
    assert stats["boundary_analysis"]["fusion"]["count"] == 1
    assert stats["fusion_value_analysis"]["correct_vlm_harmed_by_fusion"] == 1
    assert stats["confidence_bins"]["detector"]["[0.9,1.0]"]["sample_count"] == 1
