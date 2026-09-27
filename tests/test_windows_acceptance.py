from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.prepare_gate1_core_models import BASE_CHECKPOINT, OCR_MODELS, verify_file
from scripts.run_windows_acceptance import GATE_FILES, aggregate
from scripts.run_windows_core_acceptance import forbidden_core_files, parse_smoke
from scripts.smoke_test_packaged_runtime import _validate_review_result
from scripts.validate_release import _validate_windows_acceptance


def _gate_files(root: Path, statuses: dict[str, str]) -> None:
    for gate, filename in GATE_FILES.items():
        (root / filename).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "gate": gate,
                    "status": statuses[gate],
                    "reason": "test",
                }
            ),
            encoding="utf-8",
        )


def test_aggregate_pass_requires_all_three_gates(tmp_path: Path) -> None:
    _gate_files(tmp_path, {gate: "PASS" for gate in GATE_FILES})
    assert aggregate(tmp_path)["overall_clean_environment"] == "PASS"


def test_aggregate_fails_closed_for_network_block(tmp_path: Path) -> None:
    statuses = {gate: "PASS" for gate in GATE_FILES}
    statuses["advanced_ai_gpu"] = "BLOCKED_NETWORK"
    _gate_files(tmp_path, statuses)
    report = aggregate(tmp_path)
    assert report["overall_clean_environment"] == "BLOCKED"
    assert report["gates"]["advanced_ai_gpu"]["status"] == "BLOCKED_NETWORK"


def test_validator_rejects_forged_overall_pass(tmp_path: Path) -> None:
    statuses = {gate: "PASS" for gate in GATE_FILES}
    statuses["fresh_user_gui"] = "BLOCKED"
    _gate_files(tmp_path, statuses)
    summary = aggregate(tmp_path)
    summary["overall_clean_environment"] = "PASS"
    (tmp_path / "windows-acceptance-summary.json").write_text(json.dumps(summary), encoding="utf-8")
    errors: list[str] = []
    _validate_windows_acceptance(tmp_path, errors)
    assert "Windows acceptance gate not passed: fresh_user_gui=BLOCKED" in errors
    assert any("overall status is inconsistent" in error for error in errors)


def test_core_scan_rejects_cuda_payload(tmp_path: Path) -> None:
    target = tmp_path / "components/core-runtime/_internal/torch/lib/cublas64_12.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"native")
    assert forbidden_core_files(tmp_path) == [
        "components/core-runtime/_internal/torch/lib/cublas64_12.dll"
    ]


def test_parse_core_smoke_requires_contract_payload() -> None:
    payload = {
        "live": {"status": "ok"},
        "ready": {"status": "ready"},
        "meta": {"core_ready": True},
        "review": {"schema_valid": True},
    }
    assert parse_smoke(f"noise\n{json.dumps(payload)}\n") == payload


def test_packaged_review_requires_the_structured_contract() -> None:
    _validate_review_result(
        {
            "risk_level": "low",
            "categories": [],
            "reason": "No risk detected.",
            "evidence": [],
            "confidence_score": 0.9,
            "requires_manual_review": False,
        }
    )


def test_packaged_review_rejects_free_text_only_payload() -> None:
    try:
        _validate_review_result({"reason": "free text"})
    except RuntimeError as exc:
        assert "risk_level" in str(exc)
    else:
        raise AssertionError("an incomplete review contract must fail closed")


def test_gate1_workflow_self_builds_and_uses_a_separate_smoke_job() -> None:
    workflow = Path(".github/workflows/windows-release-smoke.yml").read_text(encoding="utf-8")
    assert "candidate_url" not in workflow
    assert "build-candidate:" in workflow
    assert "clean-core-smoke:" in workflow
    assert "needs: build-candidate" in workflow
    assert "name: visionguard-gate1-candidate" in workflow
    assert "name: visionguard-gate1-evidence" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "create release" not in workflow.casefold()


def test_gate1_model_sources_are_immutable_and_hash_checked(tmp_path: Path) -> None:
    assert BASE_CHECKPOINT["url"].startswith("https://github.com/ultralytics/")
    assert len(str(BASE_CHECKPOINT["sha256"])) == 64
    assert all(len(str(model["revision"])) == 40 for model in OCR_MODELS.values())
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"verified")
    verify_file(artifact, expected_sha256=hashlib.sha256(b"verified").hexdigest())
