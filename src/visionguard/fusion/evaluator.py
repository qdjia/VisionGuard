"""Live and offline metrics for FusionDecision."""

import json
from datetime import UTC, datetime
from pathlib import Path

from visionguard.fusion.replay import ablate_signals, signals_from_record
from visionguard.pipeline.exceptions import PipelineError, safe_error


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _decision(record: dict) -> dict:
    if "decision" in record:
        return record["decision"]
    result = record["result"]
    return result.get("fusion") or result["final"]


def calculate_fusion_metrics(records: list[dict], failures: list[dict] | None = None) -> dict:
    failures = failures or []
    total = len(records) + len(failures)
    risk_correct = tp = fp = fn = manual = conflicts = near = overrides = unsafe = 0
    for record in records:
        decision = _decision(record)
        ground_truth = record["ground_truth"]
        expected_categories = set(ground_truth["categories"])
        actual_categories = {item["name"] for item in decision["categories"]}
        risk_correct += int(decision["risk_level"] == ground_truth["risk_level"])
        tp += len(actual_categories & expected_categories)
        fp += len(actual_categories - expected_categories)
        fn += len(expected_categories - actual_categories)
        reasons = set(decision["reason_codes"])
        manual += int(decision["requires_manual_review"])
        conflicts += int("evidence_conflict" in reasons)
        near += int("near_decision_boundary" in reasons)
        overrides += int(decision["metadata"]["routing_overridden_by_fusion"])
        unsafe += int(
            ground_truth["risk_level"] in {"medium", "high"} and decision["risk_level"] == "low"
        )
    for failure in failures:
        fn += len(failure.get("ground_truth", {}).get("categories", []))
    return {
        "total_samples": total,
        "risk_level_accuracy": _rate(risk_correct, total),
        "category_precision": _rate(tp, tp + fp),
        "category_recall": _rate(tp, tp + fn),
        "category_f1": _rate(2 * tp, 2 * tp + fp + fn),
        "manual_review_rate": _rate(manual, total),
        "conflict_rate": _rate(conflicts, total),
        "near_boundary_rate": _rate(near, total),
        "fusion_failure_rate": _rate(len(failures), total),
        "routing_override_rate": _rate(overrides, total),
        "unsafe_fused_low_count": unsafe,
        "unsafe_fused_low_rate": _rate(unsafe, total),
    }


def replay_records(records: list[dict], engine, *, profile: str = "full") -> list[dict]:
    replayed = []
    for record in records:
        signals = ablate_signals(signals_from_record(record), profile)
        decision = engine.decide(signals)
        replayed.append(
            {
                "image": record.get("image"),
                "image_path": record.get("image_path"),
                "ground_truth": record["ground_truth"],
                "signals": signals.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
            }
        )
    return replayed


def evaluate_fusion(pipeline, manifest: str | Path, output_dir: str | Path) -> dict:
    manifest = Path(manifest).resolve()
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("empty fusion evaluation manifest")
    for row in rows:
        if row.get("risk_level") not in {"low", "medium", "high"}:
            raise ValueError("manifest contains an invalid risk_level")
        if not isinstance(row.get("categories"), list):
            raise ValueError("manifest categories must be a list")
        if not set(row["categories"]).issubset(pipeline.policy.categories):
            raise ValueError("manifest contains an invalid moderation category")
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"fusion evaluation output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    failures: list[dict] = []
    for row in rows:
        image_path = (manifest.parent / row["image"]).resolve()
        ground_truth = {"risk_level": row["risk_level"], "categories": row["categories"]}
        try:
            result = pipeline.run(image_path)
            records.append(
                {
                    "image": row["image"],
                    "image_path": str(image_path),
                    "ground_truth": ground_truth,
                    "signals": result.fusion.signals.model_dump(mode="json"),
                    "decision": result.fusion.model_dump(mode="json"),
                    "result": result.model_dump(mode="json"),
                }
            )
        except (PipelineError, OSError, ValueError) as exc:
            error_type, error_message = safe_error(exc)
            failures.append(
                {
                    "image": row.get("image"),
                    "ground_truth": ground_truth,
                    "error_type": error_type,
                    "error": error_message,
                }
            )
    metrics = calculate_fusion_metrics(records, failures)
    summary = {
        "sample_count": len(rows),
        "fusion_policy_version": pipeline.fusion_engine.version,
        "routing_policy_version": (
            records[-1]["result"]["metadata"].get("routing_policy_version") if records else None
        ),
        "strategy": pipeline.fusion_engine.config.strategy,
        "metrics": metrics,
        "timestamp": datetime.now(UTC).isoformat(),
        "score_note": "risk_score is an engineering fusion score, not a calibrated probability.",
        "scope_note": (
            "Small or synthetic datasets validate engineering behavior only; they do not "
            "establish real-world moderation quality."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for filename, values in (("records.jsonl", records), ("errors.jsonl", failures)):
        (output / filename).write_text(
            "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
            encoding="utf-8",
        )
    return summary
