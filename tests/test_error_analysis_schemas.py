from visionguard.error_analysis.schemas import (
    AnnotationStatus,
    AttributionConfidence,
    ErrorCase,
    FailureSeverity,
    GroundTruth,
    SampleMetadata,
)
from visionguard.error_analysis.taxonomy import FailureStage, FailureType, stage_for


def test_taxonomy_maps_every_failure_to_expected_stage() -> None:
    assert stage_for(FailureType.VLM_FALSE_LOW) == FailureStage.VLM
    assert stage_for(FailureType.FUSION_EVIDENCE_CONFLICT) == FailureStage.FUSION
    assert stage_for(FailureType.MODULE_FAILURE) == FailureStage.SYSTEM
    assert stage_for(FailureType.AMBIGUOUS_LABEL) == FailureStage.DATA


def test_error_case_preserves_observed_and_suspected_failures() -> None:
    case = ErrorCase(
        case_id="a" * 16,
        image="sample.png",
        image_hash="b" * 64,
        ground_truth=GroundTruth(risk_level="high"),
        prediction={"risk_level": "low"},
        primary_failure=FailureType.FALSE_LOW,
        failure_stage=FailureStage.END_TO_END,
        observed_failures=[FailureType.FALSE_LOW],
        suspected_causes=[FailureType.BAD_WEIGHTING],
        severity=FailureSeverity.CRITICAL,
        attribution_confidence=AttributionConfidence.HIGH,
        metadata=SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
    )
    assert case.propagation_trace.causal_claim is False
    assert case.suspected_causes == [FailureType.BAD_WEIGHTING]
