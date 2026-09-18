from visionguard.error_analysis.attribution import build_error_case
from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.schemas import AnnotationStatus, GroundTruth, SampleMetadata
from visionguard.error_analysis.taxonomy import FailureStage, FailureType


def test_module_failure_trace_preserves_recorded_status_without_causal_claim() -> None:
    record = {
        "image": "missing.png",
        "ground_truth": {"risk_level": "high"},
        "result": {
            "run_id": "1" * 32,
            "review_status": "partial",
            "final": {"risk_level": "medium", "categories": [], "requires_manual_review": True},
            "module_status": {"ocr": {"status": "failed", "error_type": "OCRInferenceError"}},
            "routing": {"route": "vlm_path", "reason_codes": ["module_failure"]},
        },
    }
    case = build_error_case(
        record,
        GroundTruth(risk_level="high"),
        SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert case is not None
    assert FailureType.MODULE_FAILURE in case.observed_failures
    assert case.failure_stage in {FailureStage.SYSTEM, FailureStage.END_TO_END}
    assert case.propagation_trace.causal_claim is False
    assert any("ocr" in step.observation for step in case.propagation_trace.steps)
