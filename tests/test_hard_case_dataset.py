from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.hard_cases import build_hard_cases, merge_hard_cases
from visionguard.error_analysis.schemas import (
    AnnotationStatus,
    AttributionConfidence,
    ErrorCase,
    FailureSeverity,
    GroundTruth,
    SampleMetadata,
)
from visionguard.error_analysis.taxonomy import FailureStage, FailureType


def _case(case_id: str, run_id: str) -> ErrorCase:
    return ErrorCase(
        case_id=case_id,
        run_id=run_id,
        image="same.png",
        image_hash="f" * 64,
        ground_truth=GroundTruth(risk_level="high"),
        prediction={"risk_level": "low"},
        primary_failure=FailureType.FALSE_LOW,
        failure_stage=FailureStage.END_TO_END,
        observed_failures=[FailureType.FALSE_LOW],
        severity=FailureSeverity.CRITICAL,
        attribution_confidence=AttributionConfidence.HIGH,
        metadata=SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
    )


def test_hard_cases_deduplicate_by_image_hash_and_failure() -> None:
    result = build_hard_cases(
        [_case("1" * 16, "a" * 32), _case("2" * 16, "b" * 32)],
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert len(result) == 1
    assert result[0].eligible_for_regression is True
    assert result[0].source_run_ids == ["a" * 32, "b" * 32]


def test_hard_case_merge_updates_history_by_hash() -> None:
    config = load_error_analysis_config("configs/error_analysis.yaml")
    first = build_hard_cases([_case("1" * 16, "a" * 32)], config)
    second = build_hard_cases([_case("2" * 16, "b" * 32)], config)
    merged = merge_hard_cases(first, second)
    assert len(merged) == 1
    assert merged[0].source_run_ids == ["a" * 32, "b" * 32]
