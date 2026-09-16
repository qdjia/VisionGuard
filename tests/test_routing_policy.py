import pytest
from pydantic import ValidationError

from visionguard.routing import (
    Route,
    RoutingConfig,
    RoutingPolicy,
    RoutingReasonCode,
    RoutingSignals,
    load_routing_config,
)


@pytest.fixture
def policy():
    return RoutingPolicy(load_routing_config("configs/routing.yaml"))


def signals(**changes):
    values = {
        "detection_count": 0,
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.9,
        "ocr_text_length": 10,
        "baseline_probability": 0.05,
        "detector_status": "success",
        "ocr_status": "success",
        "baseline_status": "success",
    }
    return RoutingSignals(**{**values, **changes})


def reasons(decision):
    return set(decision.reason_codes)


def test_safe_consensus_fast_path_and_no_detection_is_not_failure(policy):
    decision = policy.decide(signals())
    assert decision.route == Route.FAST_PATH
    assert not decision.call_vlm
    assert RoutingReasonCode.SAFE_CONSENSUS in reasons(decision)
    assert RoutingReasonCode.NO_DETECTION in reasons(decision)
    assert decision.policy_version == "routing_v1"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"high_risk_detection_count": 1}, RoutingReasonCode.HIGH_RISK_DETECTION),
        ({"baseline_probability": 0.8}, RoutingReasonCode.BASELINE_HIGH_RISK),
        ({"baseline_probability": 0.2}, RoutingReasonCode.BASELINE_UNCERTAIN),
        ({"mean_ocr_confidence": 0.59}, RoutingReasonCode.OCR_LOW_CONFIDENCE),
        ({"evidence_conflict": True}, RoutingReasonCode.EVIDENCE_CONFLICT),
        ({"detector_status": "failed"}, RoutingReasonCode.MODULE_FAILURE),
        (
            {"ocr_text_length": 0, "baseline_probability": None, "baseline_status": "skipped"},
            RoutingReasonCode.INSUFFICIENT_EVIDENCE,
        ),
    ],
)
def test_conservative_vlm_rules(policy, changes, reason):
    decision = policy.decide(signals(**changes))
    assert decision.route == Route.VLM_PATH
    assert decision.call_vlm
    assert reason in reasons(decision)


def test_threshold_boundaries(policy):
    assert policy.decide(signals(baseline_probability=0.10)).route == Route.FAST_PATH
    risky = policy.decide(signals(baseline_probability=0.80))
    assert risky.route == Route.VLM_PATH
    assert RoutingReasonCode.BASELINE_HIGH_RISK in reasons(risky)


def test_config_validation_and_class_configuration():
    config = load_routing_config("configs/routing.yaml")
    assert "weapon" in config.high_risk_classes
    raw = config.model_dump()
    raw["baseline"]["safe_threshold"] = 0.9
    with pytest.raises(ValidationError):
        RoutingConfig.model_validate(raw)
