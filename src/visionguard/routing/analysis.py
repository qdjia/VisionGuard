"""Deterministic classification and export of routing error cases."""

import json
import shutil
from pathlib import Path


def analyze_routing_errors(
    predictions: str | Path,
    output_dir: str | Path,
    *,
    copy_images: bool = True,
) -> dict:
    predictions = Path(predictions).resolve()
    records = [
        json.loads(line)
        for line in predictions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"routing error output is not empty: {output}")
    buckets: dict[str, list[dict]] = {
        "unsafe_fast_pass": [],
        "potential_unnecessary_vlm": [],
        "conflict": [],
        "module_failure_route": [],
    }
    for record in records:
        result = record["result"]
        reasons = set(result["routing"]["reason_codes"])
        route = result["routing"]["route"]
        expected = record["ground_truth"]["risk_level"]
        final_risk = result["final"]["risk_level"]
        categories = []
        if expected in {"medium", "high"} and route == "fast_path":
            categories.append("unsafe_fast_pass")
        if expected == "low" and result["routing"]["call_vlm"] and final_risk == "low":
            categories.append("potential_unnecessary_vlm")
        if "evidence_conflict" in reasons:
            categories.append("conflict")
        if "module_failure" in reasons:
            categories.append("module_failure_route")
        item = {
            "image": record["image"],
            "ground_truth": record["ground_truth"],
            "route": route,
            "reason_codes": result["routing"]["reason_codes"],
            "signals": result["routing"]["signals"],
            "policy_version": result["routing"].get("policy_version"),
            "final_result": result["final"],
        }
        for category in categories:
            buckets[category].append(item)
            if copy_images:
                source = Path(record["image_path"])
                target = output / category / f"{len(buckets[category]):04d}_{source.name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    output.mkdir(parents=True, exist_ok=True)
    flattened = [dict(item, error_type=name) for name, items in buckets.items() for item in items]
    (output / "routing_errors.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in flattened),
        encoding="utf-8",
    )
    summary = {
        "routing_policy_versions": sorted(
            {
                record["result"]["routing"].get("policy_version")
                for record in records
                if record["result"]["routing"].get("policy_version")
            }
        ),
        **{name: len(items) for name, items in buckets.items()},
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
