import pytest
from pydantic import ValidationError

from visionguard.schemas import (
    BoundingBox,
    DecisionSource,
    DetectionResult,
    ImageReference,
    ModerationResult,
    OCRResult,
    OCRTiming,
    PipelineResult,
    RiskLevel,
    TimingInfo,
)


def test_moderation_result_serializes_to_strict_json() -> None:
    result = ModerationResult(
        risk_level=RiskLevel.HIGH,
        categories=["weapon"],
        reason="Detected a high-risk visual element.",
        evidence=[],
        confidence=0.91,
    )

    assert result.model_dump(mode="json")["risk_level"] == "high"
    assert '"confidence":0.91' in result.model_dump_json()


def test_invalid_bbox_is_rejected() -> None:
    with pytest.raises(ValidationError, match="positive width"):
        BoundingBox(x1=20, y1=0, x2=10, y2=10)


def test_pipeline_result_preserves_cascade_observability() -> None:
    moderation = ModerationResult(
        risk_level="low", categories=[], reason="No risk found.", confidence=0.95
    )
    result = PipelineResult(
        image=ImageReference(image_id="sample", width=640, height=480),
        moderation=moderation,
        decision_source=DecisionSource.RULE_ENGINE,
        vlm_called=False,
        detections=DetectionResult(
            image_width=640,
            image_height=480,
            detections=[],
            timing=TimingInfo(inference_ms=4.2, total_ms=4.2),
            device="cpu",
            model_name="test.pt",
        ),
        ocr=OCRResult(
            image_width=640,
            image_height=480,
            blocks=[],
            full_text="",
            timing=OCRTiming(ocr_ms=7.1, total_ms=7.1),
            device="cpu",
            engine_name="test",
        ),
        rule_result=moderation,
    )

    payload = result.model_dump(mode="json")
    assert payload["vlm_called"] is False
    assert payload["decision_source"] == "rule_engine"
