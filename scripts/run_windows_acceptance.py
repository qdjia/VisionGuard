"""Aggregate the three split Windows acceptance gates without inventing PASS results."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_FILES = {
    "clean_core": "windows-core-acceptance.json",
    "fresh_user_gui": "fresh-user-gui.json",
    "advanced_ai_gpu": "advanced-ai-gpu-acceptance.json",
}
ALLOWED = {"PASS", "BLOCKED", "BLOCKED_NETWORK", "FAIL"}


def load_gate(path: Path, expected_gate: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("gate") != expected_gate:
        raise ValueError(f"invalid {expected_gate} evidence: {path}")
    status = str(payload.get("status", "")).upper()
    if status not in ALLOWED:
        raise ValueError(f"invalid {expected_gate} status: {status or 'MISSING'}")
    return payload


def aggregate(evidence_dir: Path) -> dict:
    gates: dict[str, dict[str, str]] = {}
    statuses: list[str] = []
    for gate, filename in GATE_FILES.items():
        path = evidence_dir / filename
        if path.is_file():
            payload = load_gate(path, gate)
            status = str(payload["status"]).upper()
            reason = str(payload.get("reason", ""))
        else:
            status, reason = "BLOCKED", "EVIDENCE_MISSING"
        statuses.append(status)
        gates[gate] = {"status": status, "evidence": filename, "reason": reason}
    if all(status == "PASS" for status in statuses):
        overall = "PASS"
    elif any(status == "FAIL" for status in statuses):
        overall = "FAIL"
    else:
        overall = "BLOCKED"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "acceptance_model": "split-windows-acceptance",
        "gates": gates,
        "overall_clean_environment": overall,
        "pass_rule": "clean_core=PASS AND fresh_user_gui=PASS AND advanced_ai_gpu=PASS",
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "release-evidence")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "release-evidence/windows-acceptance-summary.json",
    )
    args = parser.parse_args(argv)
    report = aggregate(args.evidence_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_clean_environment"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(run())
