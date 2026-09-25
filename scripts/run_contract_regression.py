"""Run the fixed source-level historical regression contract suite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCENARIOS = {
    "safe",
    "risky",
    "no_text",
    "ocr_low_confidence",
    "baseline_ambiguous",
    "detector_high_risk",
    "evidence_conflict",
    "prompt_injection",
    "fast_path",
    "vlm_route",
    "no_vlm",
    "vlm_failure",
    "partial_result",
    "fusion_boundary",
    "routing_boundary",
    "structured_output_recovery",
}
CLASSIFICATIONS = {
    "PASS",
    "EXPECTED_DIFFERENCE",
    "DIAGNOSTIC_ONLY",
    "CONFIRMED_REGRESSION",
    "NOT_COMPARABLE",
}


def load_suite(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def validate_suite(cases: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    ids = [str(item.get("case_id", "")) for item in cases]
    if len(ids) != len(set(ids)):
        errors.append("case_id values must be unique")
    missing = sorted(REQUIRED_SCENARIOS - {str(item.get("scenario", "")) for item in cases})
    if missing:
        errors.append(f"required scenarios missing: {', '.join(missing)}")
    for item in cases:
        for field in ("case_id", "source_phase", "scenario", "pytest_node", "expected_behavior"):
            if not item.get(field):
                errors.append(f"{item.get('case_id', '<unknown>')}: missing {field}")
        node = ROOT / str(item.get("pytest_node", "")).split("::", maxsplit=1)[0]
        if not node.is_file():
            errors.append(f"{item.get('case_id')}: pytest file does not exist")
    return errors


def run_suite(cases: list[dict[str, object]]) -> dict[str, object]:
    results = []
    for case in cases:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(ROOT / "artifacts/regression/pytest-tmp"),
                str(case["pytest_node"]),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        classification = "PASS" if completed.returncode == 0 else "CONFIRMED_REGRESSION"
        results.append(
            {
                "case_id": case["case_id"],
                "source_phase": case["source_phase"],
                "input": {"pytest_node": case["pytest_node"]},
                "expected_behavior": case["expected_behavior"],
                "actual_behavior": "pytest node passed"
                if completed.returncode == 0
                else "pytest node failed",
                "risk": case.get("risk"),
                "categories": case.get("categories", []),
                "routing": case.get("routing"),
                "manual_review": case.get("manual_review"),
                "fusion": case.get("fusion"),
                "vlm_status": case.get("vlm_status"),
                "classification": classification,
            }
        )
    counts = Counter(str(item["classification"]) for item in results)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "suite_kind": "source_level_behavioral_contracts",
        "real_image_model_quality_claim": False,
        "total": len(results),
        "classification_counts": dict(sorted(counts.items())),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/regression/contract_manifest.jsonl"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/regression/contracts.json")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    cases = load_suite(args.manifest)
    errors = validate_suite(cases)
    if errors:
        raise SystemExit("\n".join(errors))
    if args.validate_only:
        print(json.dumps({"total": len(cases), "scenarios": len(REQUIRED_SCENARIOS)}))
        return
    payload = run_suite(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["classification_counts"], ensure_ascii=False))
    if payload["classification_counts"].get("CONFIRMED_REGRESSION"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
