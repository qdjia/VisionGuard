from types import SimpleNamespace

from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.regression import run_hard_case_regression
from visionguard.error_analysis.schemas import (
    AnnotationStatus,
    FailureSeverity,
    GroundTruth,
    HardCaseRecord,
    RegressionOutcome,
)
from visionguard.error_analysis.taxonomy import FailureType


class _Result:
    def model_dump(self, mode):
        return {
            "run_id": "c" * 32,
            "review_status": "completed",
            "final": {
                "risk_level": "high",
                "categories": [],
                "requires_manual_review": False,
            },
            "module_status": {},
        }


def test_live_regression_marks_fixed_historical_failure() -> None:
    pipeline = SimpleNamespace(run=lambda image: _Result())
    case = HardCaseRecord(
        case_id="1" * 16,
        image="not-read-by-fake.png",
        image_hash="2" * 64,
        primary_failure=FailureType.FALSE_LOW,
        failure_types=[FailureType.FALSE_LOW],
        severity=FailureSeverity.CRITICAL,
        ground_truth=GroundTruth(risk_level="high", categories=[]),
        annotation_status=AnnotationStatus.VERIFIED,
        eligible_for_regression=True,
    )
    result = run_hard_case_regression(
        pipeline, [case], load_error_analysis_config("configs/error_analysis.yaml")
    )
    assert result[0].outcome == RegressionOutcome.FIXED
