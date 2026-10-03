#!/usr/bin/env python
"""Replay verified real images through packaged Core and managed local VLM services."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.run_advanced_ai_gpu_acceptance import (  # noqa: E402
    register_vlm,
    review,
    shutdown,
    start_core,
    start_vlm,
)
from visionguard.evaluation.historical import (  # noqa: E402
    HistoricalImageRecord,
    coverage,
    load_jsonl,
    validate_resolved,
)

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def classify(record: HistoricalImageRecord, response: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    result = response.get("result") or {}
    status = response.get("status")
    actual_risk = result.get("risk_level")
    actual_manual = bool(result.get("requires_manual_review"))
    actual_categories = {
        item.get("name") for item in result.get("categories", []) if isinstance(item, dict)
    }
    expected = record.ground_truth
    expected_risk = str(expected.risk_level)
    expected_categories = set(expected.categories or [])
    expected_manual = bool(expected.requires_manual_review)
    if status != "completed":
        reasons.append(f"review status is {status!r}")
        return "CONFIRMED_REGRESSION", reasons
    if expected_manual and not actual_manual:
        reasons.append("required manual review was lost")
    if RISK_ORDER.get(expected_risk, 0) > 0 and actual_risk == "low":
        reasons.append("non-low ground truth was downgraded to low")
    if reasons:
        return "CONFIRMED_REGRESSION", reasons
    missing_categories = sorted(expected_categories - actual_categories)
    if missing_categories:
        reasons.append(f"expected categories missing: {', '.join(missing_categories)}")
    if RISK_ORDER.get(actual_risk, -1) < RISK_ORDER.get(expected_risk, 0):
        reasons.append(f"risk downgraded from {expected_risk} to {actual_risk}")
    if reasons:
        return "POTENTIAL_REGRESSION", reasons
    if expected_risk == "low" and actual_risk != "low":
        return "EXPECTED_DIFFERENCE", ["conservative over-review of a safe contextual case"]
    if expected_manual != actual_manual:
        return "EXPECTED_DIFFERENCE", ["manual-review policy is more conservative than annotation"]
    return "EQUIVALENT", ["risk, required categories, and manual-review behavior match"]


def compact_result(record: HistoricalImageRecord, response: dict) -> dict[str, object]:
    classification, reasons = classify(record, response)
    result = response.get("result") or {}
    details = response.get("details") or {}
    return {
        "case_id": record.case_id,
        "scenario": record.scenario,
        "image_sha256": record.sha256,
        "expected": record.ground_truth.model_dump(mode="json"),
        "actual": {
            "status": response.get("status"),
            "risk_level": result.get("risk_level"),
            "risk_score": result.get("risk_score"),
            "categories": result.get("categories", []),
            "requires_manual_review": result.get("requires_manual_review"),
            "decision_source": result.get("decision_source"),
            "route": (response.get("routing") or {}).get("route"),
            "vlm_called": (response.get("routing") or {}).get("call_vlm"),
            "vlm_status": (response.get("modules") or {}).get("vlm"),
            "vlm_risk_level": details.get("vlm_risk_level"),
            "fusion_scores": details.get("fusion_scores"),
            "modules": response.get("modules"),
            "timing": response.get("timing"),
        },
        "classification": classification,
        "classification_reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data/regression/real_image_manifest.jsonl",
    )
    parser.add_argument("--advanced-ai-data-dir", type=Path, required=True)
    parser.add_argument(
        "--core-runtime",
        type=Path,
        default=ROOT / "runtime-dist-core/visionguard-core-runtime/visionguard-core-runtime.exe",
    )
    parser.add_argument("--core-models", type=Path, default=ROOT / "models/core-models-v1")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the per-case JSONL checkpoint in the output directory.",
    )
    parser.add_argument(
        "--environment-claim",
        choices=("development_acceptance_machine", "clean_acceptance_machine"),
        default="development_acceptance_machine",
    )
    args = parser.parse_args()
    if platform.system() != "Windows":
        raise SystemExit("packaged historical regression requires Windows")
    records = load_jsonl(args.manifest, HistoricalImageRecord)
    errors = validate_resolved(records, args.asset_dir)
    if any(item.annotation_status != "verified" for item in records):
        errors.append("all annotations must be verified before replay")
    if errors:
        raise SystemExit("\n".join(errors))
    registry_path = args.advanced_ai_data_dir / "components/components.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    managed_python = args.advanced_ai_data_dir / registry["python_executable"]
    managed_models = args.advanced_ai_data_dir / registry["vlm_models_directory"]
    model_revision = registry.get("model_revision") or registry.get("revision")
    if not model_revision:
        bootstrap = json.loads(
            (ROOT / "packaging/bootstrap/advanced-ai-bootstrap-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        model_revision = bootstrap["model"]["revision"]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "historical-real-image-regression.json"
    checkpoint_path = output_dir / "historical-real-image-results.jsonl"
    work = output_dir / "runtime-work"
    started = time.perf_counter()
    core = vlm = None
    core_endpoint = vlm_endpoint = None
    core_token = vlm_token = ""
    results: list[dict[str, object]] = []
    if args.resume and checkpoint_path.is_file():
        results = [
            json.loads(line)
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif checkpoint_path.exists():
        checkpoint_path.unlink()
    completed_ids = {str(item["case_id"]) for item in results}
    try:
        core, core_endpoint, core_token, _ = start_core(
            args.core_runtime.resolve(), args.core_models.resolve(), work / "core"
        )
        vlm, vlm_endpoint, vlm_token, _ = start_vlm(
            managed_python, managed_models, work / "vlm", str(model_revision)
        )
        register_vlm(core_endpoint, core_token, vlm_endpoint, vlm_token)
        for index, record in enumerate(records, start=1):
            if record.case_id in completed_ids:
                print(f"[{index}/{len(records)}] {record.case_id} (checkpoint)", flush=True)
                continue
            print(f"[{index}/{len(records)}] {record.case_id}", flush=True)
            response = review(core_endpoint, args.asset_dir / record.filename, "cascaded")
            case_result = compact_result(record, response)
            results.append(case_result)
            with checkpoint_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(case_result, ensure_ascii=False) + "\n")
    finally:
        shutdown(vlm_endpoint, vlm_token, vlm)
        shutdown(core_endpoint, core_token, core)
    counts = Counter(str(item["classification"]) for item in results)
    confirmed = counts.get("CONFIRMED_REGRESSION", 0)
    potential = counts.get("POTENTIAL_REGRESSION", 0)
    clean = args.environment_claim == "clean_acceptance_machine"
    gate_status = "PASS" if clean and not confirmed and not potential else "BLOCKED"
    blockers = []
    if confirmed:
        blockers.append(f"{confirmed} confirmed regressions require remediation")
    if potential:
        blockers.append(f"{potential} potential regressions require review")
    if not clean:
        blockers.append("clean-machine replay is still required")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "gate": "historical_real_image_regression",
        "gate_status": gate_status,
        "environment_claim": args.environment_claim,
        "packaged_core_runtime": True,
        "managed_local_vlm_runtime": True,
        "dataset": coverage(records),
        "classification_counts": dict(sorted(counts.items())),
        "confirmed_regression_count": confirmed,
        "potential_regression_count": potential,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "results": results,
        "blocker": None if gate_status == "PASS" else "; ".join(blockers) + ".",
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"gate_status": gate_status, **dict(counts)}, ensure_ascii=False))
    return 1 if confirmed else 0


if __name__ == "__main__":
    raise SystemExit(main())
