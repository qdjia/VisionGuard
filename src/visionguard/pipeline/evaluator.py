"""Small engineering evaluation for the complete Phase 7 pipeline."""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import numpy as np

from visionguard.pipeline.exceptions import PipelineError, safe_error


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_pipeline(pipeline, manifest: str | Path, output_dir: str | Path) -> dict:
    manifest = Path(manifest).resolve()
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("empty pipeline evaluation manifest")
    allowed_risks = {"low", "medium", "high"}
    for row in rows:
        if row.get("risk_level") not in allowed_risks:
            raise ValueError("manifest contains an invalid risk_level")
        if not isinstance(row.get("categories"), list):
            raise ValueError("manifest categories must be a list")
        if not set(row["categories"]).issubset(pipeline.policy.categories):
            raise ValueError("manifest contains an invalid moderation category")

    risk_correct = manual_reviews = failures = partials = artifact_failures = 0
    tp = fp = fn = 0
    total_latencies: list[float] = []
    vlm_latencies: list[float] = []
    predictions: list[dict] = []
    errors: list[dict] = []
    last_metadata = None
    for row in rows:
        try:
            result = pipeline.run(manifest.parent / row["image"])
            actual_risk = result.final.risk_level
            actual_categories = {item.name for item in result.final.categories}
            expected_categories = set(row["categories"])
            risk_correct += int(actual_risk == row["risk_level"])
            tp += len(actual_categories & expected_categories)
            fp += len(actual_categories - expected_categories)
            fn += len(expected_categories - actual_categories)
            manual_reviews += int(result.final.requires_manual_review)
            failures += int(result.review_status == "failed")
            partials += int(result.review_status == "partial")
            artifact_failures += int(result.artifacts.status == "failed")
            total_latencies.append(result.timing.total_ms)
            vlm_latencies.append(result.timing.vlm_ms)
            last_metadata = result.metadata
            predictions.append(
                {
                    "image": row["image"],
                    "ground_truth": {
                        "risk_level": row["risk_level"],
                        "categories": row["categories"],
                    },
                    "prediction": result.model_dump(mode="json"),
                }
            )
        except (PipelineError, OSError, ValueError) as exc:
            failures += 1
            fn += len(set(row["categories"]))
            error_type, error_message = safe_error(exc)
            errors.append(
                {"image": row.get("image"), "error_type": error_type, "error": error_message}
            )

    total = len(rows)
    metrics = {
        "risk_level_accuracy": _rate(risk_correct, total),
        "category_precision": _rate(tp, tp + fp),
        "category_recall": _rate(tp, tp + fn),
        "category_f1": _rate(2 * tp, 2 * tp + fp + fn),
        "manual_review_rate": _rate(manual_reviews, total),
        "pipeline_failure_rate": _rate(failures, total),
        "partial_result_rate": _rate(partials, total),
        "artifact_failure_rate": _rate(artifact_failures, total),
        "average_total_latency_ms": mean(total_latencies) if total_latencies else None,
        "p50_total_latency_ms": float(np.percentile(total_latencies, 50))
        if total_latencies
        else None,
        "p95_total_latency_ms": float(np.percentile(total_latencies, 95))
        if total_latencies
        else None,
        "average_vlm_latency_ms": mean(vlm_latencies) if vlm_latencies else None,
    }
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"evaluation output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "pipeline_version": pipeline.config.pipeline_version,
        "model_versions": last_metadata.component_versions if last_metadata else {},
        "policy_version": pipeline.policy.version,
        "prompt_version": last_metadata.prompt_version if last_metadata else None,
        "fusion_policy_version": (last_metadata.fusion_policy_version if last_metadata else None),
        "sample_count": total,
        "metrics": metrics,
        "failure_count": failures,
        "partial_count": partials,
        "artifact_failure_count": artifact_failures,
        "timestamp": datetime.now(UTC).isoformat(),
        "scope_note": (
            "Engineering-chain evaluation only; synthetic or small samples do not establish "
            "real-world moderation accuracy."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for filename, values in (("predictions.jsonl", predictions), ("errors.jsonl", errors)):
        (output / filename).write_text(
            "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
            encoding="utf-8",
        )
    return summary
