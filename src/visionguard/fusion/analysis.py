"""Classify and export high-value fusion error cases."""

import json
import shutil
from pathlib import Path

from visionguard.fusion.evaluator import _decision


def analyze_fusion_errors(
    records_path: str | Path,
    output_dir: str | Path,
    *,
    copy_images: bool = True,
) -> dict:
    records = [
        json.loads(line)
        for line in Path(records_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"fusion error output is not empty: {output}")
    buckets = {
        "false_low": [],
        "false_high": [],
        "evidence_conflict": [],
        "near_boundary": [],
        "module_failure": [],
        "routing_override": [],
    }
    for record in records:
        decision = _decision(record)
        expected = record["ground_truth"]["risk_level"]
        actual = decision["risk_level"]
        reasons = set(decision["reason_codes"])
        names = []
        if expected in {"medium", "high"} and actual == "low":
            names.append("false_low")
        if expected == "low" and actual == "high":
            names.append("false_high")
        for reason, bucket in (
            ("evidence_conflict", "evidence_conflict"),
            ("near_decision_boundary", "near_boundary"),
            ("module_failure", "module_failure"),
            ("routing_override", "routing_override"),
        ):
            if reason in reasons:
                names.append(bucket)
        item = {
            "image": record.get("image"),
            "ground_truth": record["ground_truth"],
            "risk_level": actual,
            "risk_score": decision["risk_score"],
            "reason_codes": decision["reason_codes"],
            "signals": decision["signals"],
            "decision": decision,
        }
        for name in names:
            buckets[name].append(item)
            image_path = record.get("image_path")
            if copy_images and image_path:
                source = Path(image_path)
                target = output / name / f"{len(buckets[name]):04d}_{source.name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    output.mkdir(parents=True, exist_ok=True)
    flattened = [dict(item, error_type=name) for name, items in buckets.items() for item in items]
    (output / "fusion_errors.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in flattened),
        encoding="utf-8",
    )
    summary = {
        "fusion_policy_versions": sorted(
            {
                _decision(record)["policy_version"]
                for record in records
                if _decision(record).get("policy_version")
            }
        ),
        "unsafe_fused_low": len(buckets["false_low"]),
        **{name: len(items) for name, items in buckets.items()},
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
