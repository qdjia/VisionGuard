import json

import pytest

from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.analysis import analyze_fusion_errors
from visionguard.fusion.evaluator import (
    calculate_fusion_metrics,
    replay_records,
)
from visionguard.fusion.schemas import FusionSignals


def record(expected="low", actual="low", *, reasons=None, categories=None, signals=None):
    decision = {
        "risk_level": actual,
        "risk_score": {"low": 0.1, "medium": 0.5, "high": 0.9}[actual],
        "categories": [
            {"name": name, "score": 0.9, "sources": ["vlm"]} for name in (categories or [])
        ],
        "requires_manual_review": bool(reasons),
        "reason_codes": reasons or ["all_evidence_safe"],
        "signals": (signals or safe_signals()).model_dump(mode="json"),
        "metadata": {"routing_overridden_by_fusion": "routing_override" in (reasons or [])},
        "policy_version": "fusion_v1",
    }
    return {
        "image": "sample.png",
        "image_path": "sample.png",
        "ground_truth": {
            "risk_level": expected,
            "categories": categories or [],
        },
        "signals": decision["signals"],
        "decision": decision,
    }


def safe_signals():
    return FusionSignals(
        detector_status="success",
        ocr_status="success",
        baseline_status="success",
        vlm_status="success",
        mean_ocr_confidence=0.9,
        ocr_text_length=5,
        baseline_label="normal",
        baseline_probability=0.05,
        vlm_available=True,
        vlm_risk_level="low",
        vlm_confidence_score=0.9,
    )


def test_fusion_metrics_make_unsafe_low_explicit():
    metrics = calculate_fusion_metrics(
        [
            record(),
            record("high", "low", categories=["violence"]),
            record("high", "high", categories=["violence"]),
            record("low", "medium", reasons=["near_decision_boundary"]),
            record("low", "low", reasons=["routing_override"]),
        ]
    )
    assert metrics["risk_level_accuracy"] == pytest.approx(3 / 5)
    assert metrics["unsafe_fused_low_count"] == 1
    assert metrics["unsafe_fused_low_rate"] == pytest.approx(0.2)
    assert metrics["near_boundary_rate"] == pytest.approx(0.2)
    assert metrics["routing_override_rate"] == pytest.approx(0.2)


def test_offline_ablation_reuses_identical_signals():
    engine = RiskFusionEngine(load_fusion_config("configs/fusion.yaml"))
    rows = [record(signals=safe_signals())]
    vlm_only = replay_records(rows, engine, profile="vlm_only")
    full = replay_records(rows, engine, profile="full")
    assert vlm_only[0]["signals"]["detector_status"] == "skipped"
    assert vlm_only[0]["signals"]["baseline_status"] == "skipped"
    assert full[0]["signals"]["detector_status"] == "success"


def test_error_analysis_exports_false_low_and_policy_version(tmp_path):
    rows = [
        record("high", "low", categories=["violence"]),
        record("low", "medium", reasons=["evidence_conflict", "routing_override"]),
    ]
    path = tmp_path / "records.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8")
    summary = analyze_fusion_errors(path, tmp_path / "errors", copy_images=False)
    assert summary["unsafe_fused_low"] == 1
    assert summary["evidence_conflict"] == 1
    assert summary["routing_override"] == 1
    assert summary["fusion_policy_versions"] == ["fusion_v1"]
    assert (tmp_path / "errors" / "fusion_errors.jsonl").is_file()
