from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.schemas import FusionSignals


def decide(**changes):
    values = {
        "detector_status": "success",
        "ocr_status": "success",
        "baseline_status": "success",
        "vlm_status": "skipped",
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.9,
        "ocr_text_length": 5,
        "baseline_label": "normal",
        "baseline_probability": 0.05,
        "route": "fast_path",
    }
    return RiskFusionEngine(load_fusion_config("configs/fusion.yaml")).decide(
        FusionSignals(**{**values, **changes})
    )


def test_failed_module_never_silently_fast_passes():
    for module in ("detector", "ocr", "baseline", "vlm"):
        result = decide(
            **{
                f"{module}_status": "failed",
                "module_failures": [module],
            }
        )
        assert result.risk_level != "low"
        assert result.requires_manual_review
        assert "module_failure" in result.reason_codes


def test_baseline_skipped_is_not_failure_but_empty_evidence_is_manual():
    result = decide(
        baseline_status="skipped",
        baseline_probability=None,
        ocr_text_length=0,
        mean_ocr_confidence=None,
        insufficient_evidence=True,
    )
    assert "module_failure" not in result.reason_codes
    assert "insufficient_evidence" in result.reason_codes
    assert result.requires_manual_review
    assert result.risk_level == "medium"
