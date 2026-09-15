import json
from pathlib import Path
from time import perf_counter

import yaml

from visionguard.core.exceptions import VisionGuardError
from visionguard.training.experiment import ExperimentManager
from visionguard.vlm.exceptions import VLMParseError
from visionguard.vlm.schemas import VLMContext


def evaluate_vlm(provider, policy, manifest: Path) -> dict:
    config = provider.config
    experiment = ExperimentManager(config)
    directory = experiment.prepare()
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("empty VLM evaluation manifest")
    counts = {
        "first_try_valid": 0,
        "valid_after_retry": 0,
        "final_failure": 0,
        "failed_parsing": 0,
        "manual_review": 0,
        "risk_correct": 0,
        "bbox_normalized_samples": 0,
    }
    tp = fp = fn = 0
    latencies = []
    predictions, errors = [], []
    for row in rows:
        if row["risk_level"] not in {"low", "medium", "high"}:
            raise ValueError("invalid ground-truth risk level")
        if not set(row["categories"]).issubset(policy.categories):
            raise ValueError("invalid ground-truth category")
        start = perf_counter()
        try:
            result = provider.analyze(manifest.parent / row["image"], VLMContext(), policy)
            counts[
                "valid_after_retry" if result.metadata["retry_count"] else "first_try_valid"
            ] += 1
            counts["manual_review"] += int(result.requires_manual_review)
            counts["bbox_normalized_samples"] += int(
                result.metadata.get("bbox_format_normalized", 0) > 0
            )
            counts["risk_correct"] += int(result.risk_level == row["risk_level"])
            actual, expected = {c.name for c in result.categories}, set(row["categories"])
            tp += len(actual & expected)
            fp += len(actual - expected)
            fn += len(expected - actual)
            predictions.append(
                {"image": row["image"], "prediction": result.model_dump(mode="json")}
            )
        except VisionGuardError as exc:
            counts["final_failure"] += 1
            counts["failed_parsing"] += int(isinstance(exc, VLMParseError))
            # Missing predictions count as category false negatives, never as low risk.
            fn += len(set(row["categories"]))
            errors.append({"image": row["image"], "error_type": type(exc).__name__})
        latencies.append((perf_counter() - start) * 1000)
    total = len(rows)
    valid = total - counts["final_failure"]
    metrics = {
        **counts,
        "total_samples": total,
        "risk_level_accuracy": counts["risk_correct"] / total,
        "category_precision": tp / (tp + fp) if tp + fp else 0,
        "category_recall": tp / (tp + fn) if tp + fn else 0,
        "category_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "manual_review_rate_valid": counts["manual_review"] / valid if valid else None,
        "first_try_valid_rate": counts["first_try_valid"] / total,
        "retry_recovery_rate": counts["valid_after_retry"] / total,
        "final_failure_rate": counts["final_failure"] / total,
        "invalid_output_rate": counts["failed_parsing"] / total,
        "structured_output_success_rate": valid / total,
        "bbox_normalized_rate_valid": counts["bbox_normalized_samples"] / valid if valid else None,
        "average_latency_ms": sum(latencies) / total,
        "prompt_version": config.prompt_version,
        "policy_version": policy.version,
        "category_metric_average": "micro",
    }
    for filename, value in (("metrics.json", metrics), ("summary.json", metrics)):
        experiment.save_json(filename, value)
    for filename, records in (("predictions.jsonl", predictions), ("errors.jsonl", errors)):
        (directory / filename).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
        )
    for filename, value in (
        ("config.yaml", {"vlm": config.model_dump(mode="json")}),
        ("policy.yaml", {"policy": policy.model_dump(mode="json")}),
    ):
        (directory / filename).write_text(
            yaml.safe_dump(value, allow_unicode=True), encoding="utf-8"
        )
    (directory / "prompt_snapshot.txt").write_text(
        provider.builder.system + "\n" + provider.builder.build(VLMContext(), policy)[0],
        encoding="utf-8",
    )
    return metrics
