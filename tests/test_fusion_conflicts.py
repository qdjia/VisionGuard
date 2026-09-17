from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.schemas import FusionDetectionEvidence, FusionSignals


def engine():
    return RiskFusionEngine(load_fusion_config("configs/fusion.yaml"))


def base(**changes):
    values = {
        "detector_status": "success",
        "ocr_status": "success",
        "baseline_status": "success",
        "vlm_status": "success",
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.9,
        "ocr_text_length": 5,
        "baseline_label": "normal",
        "baseline_probability": 0.05,
        "vlm_available": True,
        "vlm_risk_level": "low",
        "vlm_confidence_score": 0.9,
        "route": "vlm_path",
        "call_vlm": True,
        "routing_policy_version": "routing_v1",
    }
    return FusionSignals(**{**values, **changes})


def test_vlm_low_detector_high_conflict_requires_manual_review():
    decision = engine().decide(
        base(
            detection_count=1,
            high_risk_detection_count=1,
            high_risk_classes=["weapon"],
            detection_evidence=[
                FusionDetectionEvidence(
                    class_name="weapon",
                    confidence=0.9,
                    severity=1.0,
                    adjusted_score=0.9,
                )
            ],
            evidence_conflict=True,
        )
    )
    assert decision.requires_manual_review
    assert "evidence_conflict" in decision.reason_codes
    assert decision.risk_level != "low"


def test_baseline_high_vlm_low_and_low_ocr_conflict():
    decision = engine().decide(
        base(
            baseline_label="sensitive",
            baseline_probability=0.9,
            mean_ocr_confidence=0.3,
            evidence_conflict=True,
        )
    )
    assert decision.requires_manual_review
    assert {"evidence_conflict", "ocr_low_reliability"}.issubset(decision.reason_codes)


def test_routing_override_is_visible_and_manual():
    decision = engine().decide(base(routing_overridden_by_fusion=True, route="vlm_path"))
    assert decision.metadata.routing_overridden_by_fusion
    assert decision.requires_manual_review
    assert "routing_override" in decision.reason_codes
