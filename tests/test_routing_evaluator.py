import json

import pytest

from visionguard.routing.analysis import analyze_routing_errors
from visionguard.routing.evaluator import calculate_metrics


def record(
    *,
    expected_risk="low",
    actual_risk="low",
    call_vlm=False,
    route="fast_path",
    reasons=None,
    expected_categories=None,
    actual_categories=None,
    latency=10.0,
    vlm_latency=0.0,
):
    return {
        "image": "sample.jpg",
        "image_path": "sample.jpg",
        "ground_truth": {
            "risk_level": expected_risk,
            "categories": expected_categories or [],
        },
        "result": {
            "routing": {
                "route": route,
                "call_vlm": call_vlm,
                "reason_codes": reasons or ["safe_consensus"],
                "signals": {"baseline_probability": 0.05},
                "policy_version": "routing_v1",
            },
            "final": {
                "risk_level": actual_risk,
                "categories": [{"name": name, "score": 0.9} for name in (actual_categories or [])],
                "requires_manual_review": False,
            },
            "review_status": "completed",
            "artifacts": {"status": "success"},
            "timing": {"total_ms": latency, "vlm_ms": vlm_latency},
        },
    }


def test_metrics_expose_call_skip_latency_and_unsafe_fast_pass():
    records = [
        record(latency=10),
        record(
            expected_risk="high",
            actual_risk="low",
            route="fast_path",
            reasons=["safe_consensus"],
            expected_categories=["violence"],
            latency=20,
        ),
        record(
            expected_risk="high",
            actual_risk="high",
            call_vlm=True,
            route="vlm_path",
            reasons=["high_risk_detection"],
            expected_categories=["violence"],
            actual_categories=["violence"],
            latency=30,
            vlm_latency=12,
        ),
    ]
    metrics = calculate_metrics(records)
    assert metrics["vlm_call_rate"] == pytest.approx(1 / 3)
    assert metrics["vlm_skip_rate"] == pytest.approx(2 / 3)
    assert metrics["fast_path_rate"] == pytest.approx(2 / 3)
    assert metrics["unsafe_fast_pass_count"] == 1
    assert metrics["unsafe_fast_pass_rate_need_vlm"] == pytest.approx(0.5)
    assert metrics["average_latency_ms"] == 20
    assert metrics["p50_latency_ms"] == 20
    assert metrics["p95_latency_ms"] == pytest.approx(29)
    assert metrics["average_vlm_latency_ms"] == 12


def test_structured_failures_count_as_category_false_negatives():
    metrics = calculate_metrics(
        [record(expected_categories=["violence"], actual_categories=["violence"])],
        failures=[{"ground_truth": {"risk_level": "high", "categories": ["weapon"]}}],
    )
    assert metrics["total_samples"] == 2
    assert metrics["category_recall"] == pytest.approx(0.5)
    assert metrics["pipeline_failure_rate"] == pytest.approx(0.5)


def test_routing_analysis_exports_each_error_bucket(tmp_path):
    rows = [
        record(expected_risk="high"),
        record(call_vlm=True, route="vlm_path", reasons=["evidence_conflict"]),
        record(call_vlm=True, route="vlm_path", reasons=["module_failure"]),
    ]
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    output = tmp_path / "analysis"
    summary = analyze_routing_errors(predictions, output, copy_images=False)
    assert summary == {
        "routing_policy_versions": ["routing_v1"],
        "unsafe_fast_pass": 1,
        "potential_unnecessary_vlm": 2,
        "conflict": 1,
        "module_failure_route": 1,
    }
    assert len((output / "routing_errors.jsonl").read_text().splitlines()) == 5


def test_routing_analysis_refuses_to_overwrite(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text("", encoding="utf-8")
    output = tmp_path / "analysis"
    output.mkdir()
    (output / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        analyze_routing_errors(predictions, output, copy_images=False)
