"""Metrics for full and cascaded routing experiments."""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import numpy as np

from visionguard.pipeline.exceptions import PipelineError, safe_error


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def load_manifest(manifest: str | Path, policy) -> tuple[Path, list[dict]]:
    path = Path(manifest).resolve()
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError("empty routing evaluation manifest")
    for row in rows:
        if row.get("risk_level") not in {"low", "medium", "high"}:
            raise ValueError("manifest contains an invalid risk_level")
        if not isinstance(row.get("categories"), list):
            raise ValueError("manifest categories must be a list")
        if not set(row["categories"]).issubset(policy.categories):
            raise ValueError("manifest contains an invalid moderation category")
    return path, rows


def calculate_metrics(
    records: list[dict],
    *,
    failures: list[dict] | None = None,
    failure_count: int = 0,
) -> dict:
    """Calculate routing and moderation metrics from serializable records.

    ``failure_count`` is retained for lightweight offline callers.  Evaluation code
    supplies structured failures so their ground-truth categories count as false
    negatives rather than silently inflating category recall.
    """

    failures = failures or []
    total = len(records) + len(failures) + failure_count
    tp = fp = fn = risk_correct = manual = partial = failed_results = 0
    routing_tp = routing_fp = routing_fn = 0
    calls = skips = fast_paths = unsafe = potential_unnecessary = artifact_failures = 0
    total_latencies: list[float] = []
    vlm_latencies: list[float] = []
    for record in records:
        result = record["result"]
        expected_risk = record["ground_truth"]["risk_level"]
        expected_categories = set(record["ground_truth"]["categories"])
        actual_categories = {item["name"] for item in result["final"]["categories"]}
        actual_risk = result["final"]["risk_level"]
        call_vlm = result["routing"]["call_vlm"]
        route = result["routing"]["route"]
        need_vlm = expected_risk in {"medium", "high"}
        calls += int(call_vlm)
        skips += int(not call_vlm)
        fast_paths += int(route == "fast_path")
        unsafe += int(need_vlm and not call_vlm)
        routing_tp += int(need_vlm and call_vlm)
        routing_fp += int(not need_vlm and call_vlm)
        routing_fn += int(need_vlm and not call_vlm)
        potential_unnecessary += int(expected_risk == "low" and call_vlm and actual_risk == "low")
        risk_correct += int(actual_risk == expected_risk)
        tp += len(actual_categories & expected_categories)
        fp += len(actual_categories - expected_categories)
        fn += len(expected_categories - actual_categories)
        manual += int(result["final"]["requires_manual_review"])
        partial += int(result["review_status"] == "partial")
        failed_results += int(result["review_status"] == "failed")
        artifact_failures += int(result["artifacts"]["status"] == "failed")
        total_latencies.append(result["timing"]["total_ms"])
        if call_vlm:
            vlm_latencies.append(result["timing"]["vlm_ms"])
    for failure in failures:
        fn += len(failure.get("ground_truth", {}).get("categories", []))
    total_failures = len(failures) + failure_count + failed_results
    need_vlm_count = routing_tp + routing_fn
    return {
        "total_samples": total,
        "vlm_call_rate": _rate(calls, total),
        "vlm_skip_rate": _rate(skips, total),
        "fast_path_rate": _rate(fast_paths, total),
        "unsafe_fast_pass_count": unsafe,
        "unsafe_fast_pass_rate": _rate(unsafe, total),
        "unsafe_fast_pass_rate_need_vlm": _rate(unsafe, need_vlm_count),
        "potential_unnecessary_vlm_call_count": potential_unnecessary,
        "routing_precision_need_vlm": _rate(routing_tp, routing_tp + routing_fp),
        "routing_recall_need_vlm": _rate(routing_tp, routing_tp + routing_fn),
        "routing_f1_need_vlm": _rate(2 * routing_tp, 2 * routing_tp + routing_fp + routing_fn),
        "risk_level_accuracy": _rate(risk_correct, total),
        "category_precision": _rate(tp, tp + fp),
        "category_recall": _rate(tp, tp + fn),
        "category_f1": _rate(2 * tp, 2 * tp + fp + fn),
        "average_latency_ms": mean(total_latencies) if total_latencies else None,
        "p50_latency_ms": float(np.percentile(total_latencies, 50)) if total_latencies else None,
        "p95_latency_ms": float(np.percentile(total_latencies, 95)) if total_latencies else None,
        "average_vlm_latency_ms": mean(vlm_latencies) if vlm_latencies else None,
        "manual_review_rate": _rate(manual, total),
        "partial_rate": _rate(partial, total),
        "pipeline_failure_rate": _rate(total_failures, total),
        "artifact_failure_rate": _rate(artifact_failures, total),
    }


def evaluate_routing(pipeline, manifest: str | Path, output_dir: str | Path) -> dict:
    manifest_path, rows = load_manifest(manifest, pipeline.policy)
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"routing evaluation output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    errors: list[dict] = []
    for row in rows:
        image_path = (manifest_path.parent / row["image"]).resolve()
        try:
            result = pipeline.run(image_path)
            records.append(
                {
                    "image": row["image"],
                    "image_path": str(image_path),
                    "ground_truth": {
                        "risk_level": row["risk_level"],
                        "categories": row["categories"],
                    },
                    "result": result.model_dump(mode="json"),
                }
            )
        except (PipelineError, OSError, ValueError) as exc:
            error_type, error_message = safe_error(exc)
            errors.append(
                {
                    "image": row.get("image"),
                    "ground_truth": {
                        "risk_level": row.get("risk_level"),
                        "categories": row.get("categories", []),
                    },
                    "error_type": error_type,
                    "error": error_message,
                }
            )
    metrics = calculate_metrics(records, failures=errors)
    result_metadata = records[-1]["result"]["metadata"] if records else {}
    summary = {
        "pipeline_version": pipeline.config.pipeline_version,
        "routing_policy_version": result_metadata.get("routing_policy_version"),
        "policy_version": pipeline.policy.version,
        "prompt_version": result_metadata.get("prompt_version"),
        "model_versions": result_metadata.get("component_versions", {}),
        "sample_count": len(rows),
        "metrics": metrics,
        "timestamp": datetime.now(UTC).isoformat(),
        "routing_proxy_note": (
            "GT low=candidate_skip and GT medium/high=need_vlm is an engineering proxy, "
            "not absolute proof that a VLM call is necessary."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for filename, values in (("predictions.jsonl", records), ("errors.jsonl", errors)):
        (output / filename).write_text(
            "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
            encoding="utf-8",
        )
    return summary
