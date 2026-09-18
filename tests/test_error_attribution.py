from visionguard.error_analysis.attribution import attribute_record
from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.schemas import AnnotationStatus, GroundTruth, SampleMetadata
from visionguard.error_analysis.taxonomy import FailureType


def _metadata() -> SampleMetadata:
    return SampleMetadata(annotation_status=AnnotationStatus.VERIFIED)


def _record(final: dict, **modules) -> dict:
    return {
        "decision": {
            "categories": [],
            "requires_manual_review": False,
            **final,
        },
        "result": {"review_status": "completed", "module_status": {}, **modules},
    }


def test_false_low_and_unsafe_fast_pass_are_observed() -> None:
    record = {
        "decision": {"risk_level": "low", "categories": [], "requires_manual_review": False},
        "result": {
            "review_status": "completed",
            "routing": {"route": "fast_path", "reason_codes": ["safe_consensus"]},
            "module_status": {},
        },
    }
    result = attribute_record(
        record,
        GroundTruth(risk_level="high", categories=["weapon"]),
        SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    assert FailureType.FALSE_LOW in result.observed_failures
    assert FailureType.UNSAFE_FAST_PASS in result.observed_failures
    assert result.confidence == "high"


def test_low_ocr_without_transcription_is_suspected_and_requests_annotation() -> None:
    record = {
        "decision": {"risk_level": "low", "categories": [], "requires_manual_review": False},
        "result": {
            "review_status": "completed",
            "ocr": {"full_text": "uncertain", "blocks": [{"confidence": 0.2}]},
            "module_status": {},
        },
    }
    result = attribute_record(
        record,
        GroundTruth(risk_level="low", categories=[]),
        SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    assert result.observed_failures == [FailureType.ANNOTATION_REVIEW_REQUIRED]
    assert result.suspected_causes == [FailureType.LOW_CONFIDENCE_OCR]


def test_false_high_wrong_category_and_potential_vlm() -> None:
    record = _record(
        {"risk_level": "high", "categories": [{"name": "violence"}]},
        routing={"route": "vlm_path", "reason_codes": []},
    )
    result = attribute_record(
        record,
        GroundTruth(risk_level="low", categories=["weapon"]),
        _metadata(),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    assert FailureType.FALSE_HIGH in result.observed_failures
    assert FailureType.WRONG_CATEGORY in result.observed_failures


def test_vlm_and_fusion_induced_errors_are_distinguished() -> None:
    record = _record(
        {"risk_level": "low"},
        vlm={"risk_level": "high", "categories": [], "reason": "risk", "evidence": [{}]},
    )
    result = attribute_record(
        record,
        GroundTruth(risk_level="high", categories=[]),
        _metadata(),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    assert FailureType.CONFLICT_RESOLUTION_ERROR in result.observed_failures
    assert FailureType.BAD_WEIGHTING in result.suspected_causes


def test_baseline_ocr_detector_and_vlm_failures_use_available_gt_only() -> None:
    record = _record(
        {"risk_level": "low"},
        baseline={"label": "safe", "probability": 0.01},
        ocr={"full_text": "ab", "blocks": []},
        detection={"detections": []},
        vlm={"risk_level": "low", "categories": [], "reason": "safe", "evidence": []},
    )
    result = attribute_record(
        record,
        GroundTruth(
            risk_level="high",
            categories=[],
            text="abcd",
            objects=[{"category": "weapon", "bbox": [0, 0, 10, 10]}],
        ),
        _metadata(),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    expected = {
        FailureType.BASELINE_FALSE_NEGATIVE,
        FailureType.OCR_DELETION,
        FailureType.FALSE_NEGATIVE_DETECTION,
        FailureType.VLM_FALSE_LOW,
    }
    assert expected.issubset(result.observed_failures)


def test_ambiguous_annotation_and_system_failure_are_explicit() -> None:
    record = _record(
        {"risk_level": "medium"},
        module_status={
            "vlm": {
                "status": "failed",
                "error_type": "RuntimeError",
                "error_message": "CUDA out of memory",
            }
        },
    )
    result = attribute_record(
        record,
        GroundTruth(),
        SampleMetadata(annotation_status="ambiguous", difficulty="ambiguous"),
        load_error_analysis_config("configs/error_analysis.yaml"),
    )
    assert result is not None
    assert FailureType.CUDA_OOM in result.observed_failures
    assert FailureType.AMBIGUOUS_LABEL in result.observed_failures
