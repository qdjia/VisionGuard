import pytest

from visionguard.fusion import RiskFusionEngine, load_fusion_config, normalize_available_weights
from visionguard.fusion.schemas import FusionDetectionEvidence, FusionSignals


@pytest.fixture
def engine():
    return RiskFusionEngine(load_fusion_config("configs/fusion.yaml"))


def signals(**changes):
    values = {
        "detector_status": "success",
        "ocr_status": "success",
        "baseline_status": "success",
        "vlm_status": "success",
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.9,
        "ocr_text_length": 10,
        "baseline_label": "normal",
        "baseline_probability": 0.05,
        "vlm_available": True,
        "vlm_risk_level": "low",
        "vlm_confidence_score": 0.9,
        "route": "full_pipeline",
        "call_vlm": True,
        "routing_policy_version": "full_pipeline_v1",
    }
    return FusionSignals(**{**values, **changes})


def detection(name="weapon", confidence=0.9, severity=1.0):
    return FusionDetectionEvidence(
        class_name=name,
        confidence=confidence,
        severity=severity,
        adjusted_score=confidence * severity,
    )


def test_all_evidence_safe(engine):
    decision = engine.decide(signals())
    assert decision.risk_level == "low"
    assert decision.risk_score < 0.3
    assert not decision.requires_manual_review
    assert "all_evidence_safe" in decision.reason_codes
    assert not decision.metadata.score_is_calibrated_probability


def test_dynamic_weight_normalization_without_vlm():
    config = load_fusion_config("configs/fusion.yaml")
    weights = normalize_available_weights(config.weights, {"visual", "text"})
    assert weights.visual == pytest.approx(0.25 / 0.45)
    assert weights.text == pytest.approx(0.20 / 0.45)
    assert weights.vlm == 0
    assert weights.visual + weights.text == pytest.approx(1)


def test_visual_text_and_vlm_risk_scores(engine):
    visual = engine.decide(
        signals(
            detection_count=1,
            high_risk_detection_count=1,
            high_risk_classes=["weapon"],
            detection_evidence=[detection()],
            vlm_available=False,
            vlm_risk_level=None,
            vlm_status="skipped",
            call_vlm=False,
            route="fast_path",
        )
    )
    assert visual.risk_level == "medium"
    assert visual.scores.visual == pytest.approx(0.9)
    text = engine.decide(signals(baseline_label="sensitive", baseline_probability=0.9))
    assert text.scores.text == pytest.approx(0.81)
    assert "sensitive_text" in {item.name for item in text.categories}
    vlm = engine.decide(
        signals(
            baseline_label="sensitive",
            baseline_probability=0.9,
            vlm_risk_level="high",
            vlm_categories=["sensitive_text"],
            vlm_has_evidence=True,
        )
    )
    assert vlm.risk_level == "high"
    assert "hard_safety_override" in vlm.reason_codes


def test_threshold_boundaries_and_near_boundary(engine):
    assert engine._map_risk(0.30) == "low"
    assert engine._map_risk(0.70) == "medium"
    assert engine._map_risk(0.700001) == "high"
    near = engine.decide(
        signals(
            detection_count=1,
            detection_evidence=[detection(confidence=0.3, severity=1.0)],
            baseline_status="skipped",
            baseline_probability=None,
            ocr_text_length=0,
            vlm_available=False,
            vlm_risk_level=None,
            vlm_status="skipped",
        )
    )
    assert near.risk_score == pytest.approx(0.3)
    assert near.requires_manual_review
    assert "near_decision_boundary" in near.reason_codes


def test_category_provenance_merges_sources(engine):
    decision = engine.decide(
        signals(
            detection_count=1,
            high_risk_detection_count=1,
            high_risk_classes=["weapon"],
            detection_evidence=[detection()],
            vlm_risk_level="high",
            vlm_categories=["weapon"],
            vlm_has_evidence=True,
        )
    )
    weapon = next(item for item in decision.categories if item.name == "weapon")
    assert weapon.sources == ["detector", "vlm"]
    assert decision.evidence_summary
