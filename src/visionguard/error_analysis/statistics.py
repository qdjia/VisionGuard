"""Aggregate failure, confidence-bin, boundary, and value-add statistics."""

from collections import Counter
from typing import Any

from visionguard.error_analysis.config import ErrorAnalysisConfig
from visionguard.error_analysis.schemas import ErrorCase
from visionguard.error_analysis.taxonomy import FailureStage, FailureType


def _decision(record: dict) -> dict:
    result = record.get("result", {})
    return record.get("decision") or result.get("fusion") or result.get("final") or {}


def _bin(value: float, bins: tuple[float, ...]) -> str:
    for left, right in zip(bins, bins[1:], strict=True):
        if left <= value <= right and (value < right or right == 1):
            return f"[{left:.1f},{right:.1f}{']' if right == 1 else ')'}"
    return "unknown"


def calculate_statistics(
    records: list[dict], cases: list[ErrorCase], config: ErrorAnalysisConfig
) -> dict[str, Any]:
    taxonomy = Counter(failure.value for case in cases for failure in case.observed_failures)
    stages = Counter(case.failure_stage.value for case in cases)
    severities = Counter(case.severity.value for case in cases)
    prediction_failures = {
        FailureType.FALSE_LOW,
        FailureType.FALSE_HIGH,
        FailureType.WRONG_RISK_LEVEL,
        FailureType.WRONG_CATEGORY,
        FailureType.MISSED_CATEGORY,
        FailureType.EXTRA_CATEGORY,
        FailureType.PARTIAL_RESULT,
        FailureType.PIPELINE_FAILURE,
        FailureType.UNSAFE_FAST_PASS,
        FailureType.MODULE_FAILURE,
    }
    error_cases = [case for case in cases if prediction_failures & set(case.observed_failures)]
    error_runs = {case.run_id for case in error_cases}
    false_low_runs = {
        case.run_id for case in cases if FailureType.FALSE_LOW in case.observed_failures
    }
    confidence: dict[str, dict[str, Counter]] = {
        name: {} for name in ("detector", "ocr", "baseline", "vlm", "fusion")
    }
    routing_boundaries: list[dict] = []
    fusion_boundaries: list[dict] = []
    high_confidence_wrong: list[dict] = []
    path_rows: dict[str, list[tuple[dict, bool, bool]]] = {}
    category_stats: dict[str, Counter] = {}
    vlm_corrected = vlm_harmed = 0
    for record in records:
        result, decision = record.get("result", {}), _decision(record)
        run_id = result.get("run_id") or record.get("run_id")
        is_error, is_false_low = run_id in error_runs, run_id in false_low_runs
        signals = decision.get("signals", {})
        values = {
            "detector": signals.get("max_detection_confidence"),
            "ocr": signals.get("mean_ocr_confidence"),
            "baseline": signals.get("baseline_probability"),
            "vlm": signals.get("vlm_confidence_score"),
            "fusion": decision.get("risk_score"),
        }
        for name, value in values.items():
            if isinstance(value, (int, float)):
                label = _bin(float(value), config.confidence_bins)
                bucket = confidence[name].setdefault(label, Counter())
                bucket["sample_count"] += 1
                bucket["error_count"] += int(is_error)
                bucket["false_low_count"] += int(is_false_low)
        high_values = {
            name: value
            for name, value in values.items()
            if isinstance(value, (int, float)) and value >= config.high_confidence_threshold
        }
        if is_error and high_values:
            high_confidence_wrong.append({"image": record.get("image"), "signals": high_values})
        risk_score = decision.get("risk_score")
        if isinstance(risk_score, (int, float)) and any(
            abs(risk_score - edge) <= config.boundary_margin for edge in config.fusion_boundaries
        ):
            fusion_boundaries.append(
                {
                    "image": record.get("image"),
                    "risk_score": risk_score,
                    "predicted": decision.get("risk_level"),
                    "ground_truth": record.get("ground_truth", {}).get("risk_level"),
                }
            )
        probability = signals.get("baseline_probability")
        if isinstance(probability, (int, float)) and any(
            abs(probability - edge) <= config.boundary_margin for edge in config.routing_boundaries
        ):
            routing_boundaries.append(
                {"image": record.get("image"), "baseline_probability": probability}
            )
        expected = record.get("ground_truth", {}).get("risk_level")
        vlm = (result.get("vlm") or {}).get("risk_level")
        final = decision.get("risk_level")
        if expected and vlm and final:
            vlm_corrected += int(vlm != expected and final == expected)
            vlm_harmed += int(vlm == expected and final != expected)
        route = (result.get("routing") or {}).get("route", "full_pipeline")
        path_rows.setdefault(route, []).append((record, is_error, is_false_low))
        expected_categories = set(record.get("ground_truth", {}).get("categories") or [])
        actual_categories = {
            item.get("name") if isinstance(item, dict) else item
            for item in decision.get("categories", [])
        }
        for category in expected_categories | actual_categories:
            values_for_category = category_stats.setdefault(category, Counter())
            values_for_category["sample_count"] += 1
            values_for_category["tp"] += int(
                category in expected_categories and category in actual_categories
            )
            values_for_category["fp"] += int(
                category not in expected_categories and category in actual_categories
            )
            values_for_category["fn"] += int(
                category in expected_categories and category not in actual_categories
            )
            values_for_category["error_count"] += int(is_error)
            values_for_category["false_low_count"] += int(is_false_low)

    path_statistics = {}
    for route, rows in path_rows.items():
        count = len(rows)
        timings = [item[0].get("result", {}).get("timing", {}).get("total_ms", 0) for item in rows]
        path_statistics[route] = {
            "sample_count": count,
            "error_rate": sum(item[1] for item in rows) / count,
            "false_low_count": sum(item[2] for item in rows),
            "average_latency_ms": sum(timings) / count,
            "manual_review_rate": sum(
                bool(_decision(item[0]).get("requires_manual_review")) for item in rows
            )
            / count,
        }
    category_breakdown = {}
    for category, values in category_stats.items():
        denominator = 2 * values["tp"] + values["fp"] + values["fn"]
        category_breakdown[category] = {
            "sample_count": values["sample_count"],
            "error_count": values["error_count"],
            "false_low_count": values["false_low_count"],
            "category_f1": 2 * values["tp"] / denominator if denominator else 0.0,
            "low_sample_size": values["sample_count"] < config.report.low_sample_warning_threshold,
        }
    evaluable = sum(bool(record.get("ground_truth", {}).get("risk_level")) for record in records)
    false_low = taxonomy[FailureType.FALSE_LOW.value]
    false_high = taxonomy[FailureType.FALSE_HIGH.value]
    return {
        "total_samples": len(records),
        "evaluable_samples": evaluable,
        "total_errors": len(error_cases),
        "error_rate": len(error_cases) / evaluable if evaluable else 0.0,
        "diagnostic_case_count": len(cases),
        "false_low_count": false_low,
        "false_low_rate": false_low / evaluable if evaluable else 0.0,
        "false_high_count": false_high,
        "false_high_rate": false_high / evaluable if evaluable else 0.0,
        "unsafe_fast_pass_count": taxonomy[FailureType.UNSAFE_FAST_PASS.value],
        "routing_error_count": sum(case.failure_stage == FailureStage.ROUTING for case in cases),
        "vlm_error_count": sum(case.failure_stage == FailureStage.VLM for case in cases),
        "fusion_error_count": sum(case.failure_stage == FailureStage.FUSION for case in cases),
        "ocr_issue_count": sum(case.failure_stage == FailureStage.OCR for case in cases),
        "detection_issue_count": sum(
            case.failure_stage == FailureStage.DETECTION for case in cases
        ),
        "baseline_error_count": sum(case.failure_stage == FailureStage.BASELINE for case in cases),
        "system_failure_count": sum(case.failure_stage == FailureStage.SYSTEM for case in cases),
        "annotation_review_count": sum(case.requires_annotation_review for case in cases),
        "gt_coverage": {
            "risk_level": sum(
                bool(record.get("ground_truth", {}).get("risk_level")) for record in records
            ),
            "categories": sum("categories" in record.get("ground_truth", {}) for record in records),
            "text": sum(
                record.get("ground_truth", {}).get("text") is not None for record in records
            ),
            "objects": sum(
                record.get("ground_truth", {}).get("objects") is not None for record in records
            ),
        },
        "counts_by_failure": dict(sorted(taxonomy.items())),
        "counts_by_failure_stage": dict(sorted(stages.items())),
        "counts_by_severity": dict(sorted(severities.items())),
        "category_breakdown": category_breakdown,
        "path_breakdown": path_statistics,
        "confidence_bins": {
            name: {label: dict(bucket) for label, bucket in values.items()}
            for name, values in confidence.items()
        },
        "boundary_analysis": {
            "margin": config.boundary_margin,
            "routing": {"count": len(routing_boundaries), "cases": routing_boundaries},
            "fusion": {"count": len(fusion_boundaries), "cases": fusion_boundaries},
        },
        "fusion_value_analysis": {
            "wrong_vlm_corrected_by_fusion": vlm_corrected,
            "correct_vlm_harmed_by_fusion": vlm_harmed,
        },
        "high_confidence_wrong_cases": high_confidence_wrong,
        "routing_analysis": {
            "unsafe_fast_pass": taxonomy[FailureType.UNSAFE_FAST_PASS.value],
            "unsafe_route_attempt": taxonomy[FailureType.UNSAFE_ROUTE_ATTEMPT.value],
            "potential_unnecessary_vlm": taxonomy[FailureType.POTENTIAL_UNNECESSARY_VLM.value],
            "routing_override": taxonomy[FailureType.ROUTING_OVERRIDE.value],
            "module_failure_route": taxonomy[FailureType.MODULE_FAILURE_ROUTE.value],
            "insufficient_evidence_route": taxonomy[FailureType.INSUFFICIENT_EVIDENCE_ROUTE.value],
            "conflict_route": taxonomy[FailureType.EVIDENCE_CONFLICT_ROUTE.value],
        },
        "score_note": (
            "Confidence and fusion scores are engineering signals, not calibrated probabilities."
        ),
    }
