from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.prepare_gate1_core_models import BASE_CHECKPOINT, OCR_MODELS, verify_file
from scripts.run_windows_acceptance import GATE_FILES, aggregate
from scripts.run_windows_core_acceptance import (
    EXPECTED_MODEL_ROLES,
    console_safe_text,
    forbidden_core_files,
    format_install_tree,
    inspect_installed_layout,
    parse_smoke,
    write_evidence,
)
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


def test_core_scan_rejects_advanced_ai_payloads(tmp_path: Path) -> None:
    qwen = tmp_path / "components/vlm-models/Qwen/model.safetensors"
    runtime = tmp_path / "components/vlm-runtime/visionguard-vlm-runtime.exe"
    qwen.parent.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    qwen.write_bytes(b"model")
    runtime.write_bytes(b"runtime")
    assert forbidden_core_files(tmp_path) == [
        "components/vlm-models/Qwen/model.safetensors",
        "components/vlm-runtime/visionguard-vlm-runtime.exe",
    ]


def _installed_core_layout(root: Path) -> None:
    (root / "visionguard-desktop.exe").write_bytes(b"desktop")
    runtime = root / "components/core-runtime"
    runtime.mkdir(parents=True)
    (runtime / "visionguard-core-runtime.exe").write_bytes(b"runtime")
    (runtime / "runtime-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "component": "core",
                "entrypoint": "visionguard-core-runtime.exe",
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    models_root = root / "components/core-models"
    model_specs = {
        "detector": ("detector/model.onnx", "file"),
        "ocr_detection": ("ocr/text_detection", "directory"),
        "ocr_recognition": ("ocr/text_recognition", "directory"),
        "ocr_orientation": ("ocr/textline_orientation", "directory"),
        "baseline": ("baseline/char_2_4_gbdt_sample_v1", "directory"),
    }
    models = {}
    for role, (relative, kind) in model_specs.items():
        target = models_root / relative
        files = []
        if kind == "file":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(role.encode())
        else:
            target.mkdir(parents=True, exist_ok=True)
            artifact = target / "artifact.bin"
            artifact.write_bytes(role.encode())
            files.append({"path": "artifact.bin"})
        models[role] = {"path": relative, "kind": kind, "required": True, "files": files}
    (models_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle_type": "core",
                "models": models,
            }
        ),
        encoding="utf-8",
    )


def test_installed_layout_accepts_official_desktop_runtime_and_models(tmp_path: Path) -> None:
    _installed_core_layout(tmp_path)
    layout = inspect_installed_layout(tmp_path)
    assert layout["missing_paths"] == []
    assert layout["layout_errors"] == []
    observed_roles = {item["role"] for item in layout["observed_paths"]}
    assert {f"model_{role}" for role in EXPECTED_MODEL_ROLES} <= observed_roles


def test_installed_layout_reports_missing_core_runtime(tmp_path: Path) -> None:
    _installed_core_layout(tmp_path)
    (tmp_path / "components/core-runtime/visionguard-core-runtime.exe").unlink()
    layout = inspect_installed_layout(tmp_path)
    assert "components/core-runtime/visionguard-core-runtime.exe" in {
        item["path"] for item in layout["missing_paths"]
    }


def test_installed_layout_reports_missing_core_models(tmp_path: Path) -> None:
    _installed_core_layout(tmp_path)
    (tmp_path / "components/core-models/manifest.json").unlink()
    layout = inspect_installed_layout(tmp_path)
    assert "components/core-models/manifest.json" in {
        item["path"] for item in layout["missing_paths"]
    }


def test_installed_layout_rejects_legacy_desktop_path_mismatch(tmp_path: Path) -> None:
    _installed_core_layout(tmp_path)
    (tmp_path / "visionguard-desktop.exe").rename(tmp_path / "VisionGuard.exe")
    layout = inspect_installed_layout(tmp_path)
    assert "visionguard-desktop.exe" in {item["path"] for item in layout["missing_paths"]}
    assert "VisionGuard.exe" not in {item["path"] for item in layout["expected_paths"]}


def test_failure_evidence_serialization_preserves_layout_diagnostics(tmp_path: Path) -> None:
    target = tmp_path / "evidence/windows-core-acceptance.json"
    payload = {
        "status": "FAIL",
        "reason": "installed layout validation failed",
        "expected_paths": [{"path": "components/core-runtime"}],
        "observed_paths": [],
        "missing_paths": [{"path": "components/core-runtime"}],
    }
    write_evidence(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_install_tree_is_bounded_and_does_not_expose_absolute_root(tmp_path: Path) -> None:
    _installed_core_layout(tmp_path)
    tree = "\n".join(format_install_tree(tmp_path, max_depth=4, max_entries=25))
    assert tree.startswith("<install-root>/")
    assert str(tmp_path) not in tree
    assert "visionguard-desktop.exe (7 bytes)" in tree
    assert tree.isascii()


def test_console_logging_is_safe_for_legacy_windows_encoding() -> None:
    message = "├── 模型"
    rendered = console_safe_text(message, "cp1252")
    rendered.encode("cp1252")
    assert "\\u251c" in rendered


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
            "risk_score": 0.1,
            "categories": [],
            "reason": "No risk detected.",
            "requires_manual_review": False,
            "decision_source": "fusion",
        }
    )


def test_packaged_review_rejects_free_text_only_payload() -> None:
    try:
        _validate_review_result({"reason": "free text"})
    except RuntimeError as exc:
        assert "risk_level" in str(exc)
    else:
        raise AssertionError("an incomplete review contract must fail closed")


def test_packaged_review_accepts_public_api_categories() -> None:
    _validate_review_result(
        {
            "risk_level": "medium",
            "risk_score": 0.65,
            "categories": [{"name": "watermark", "score": 0.7}],
            "reason": "Review required.",
            "requires_manual_review": True,
            "decision_source": "fusion",
        }
    )


def test_packaged_review_rejects_internal_pipeline_contract() -> None:
    try:
        _validate_review_result(
            {
                "risk_level": "low",
                "categories": [],
                "reason": "Legacy internal result.",
                "evidence": [],
                "confidence_score": 0.9,
                "requires_manual_review": False,
            }
        )
    except RuntimeError as exc:
        assert "risk_score" in str(exc)
    else:
        raise AssertionError("the packaged smoke must validate the public API contract")


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


def test_gate1_summary_is_failure_safe_and_avoids_powershell_here_strings() -> None:
    workflow = Path(".github/workflows/windows-release-smoke.yml").read_text(encoding="utf-8")
    summary_section = workflow.split("- name: Write Gate 1 summary", maxsplit=1)[1].split(
        "- name: Upload small Gate 1 evidence", maxsplit=1
    )[0]
    assert '@"' not in summary_section
    assert "$summary = @(" in summary_section
    assert "Out-File -FilePath $env:GITHUB_STEP_SUMMARY" in summary_section
    assert "Status:" in summary_section
    assert "Installer SHA-256:" in summary_section
    assert "Primary failure:" in summary_section
    assert "Evidence artifact:" in summary_section


def test_gate1_model_sources_are_immutable_and_hash_checked(tmp_path: Path) -> None:
    assert BASE_CHECKPOINT["url"].startswith("https://github.com/ultralytics/")
    assert len(str(BASE_CHECKPOINT["sha256"])) == 64
    assert all(len(str(model["revision"])) == 40 for model in OCR_MODELS.values())
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"verified")
    verify_file(artifact, expected_sha256=hashlib.sha256(b"verified").hexdigest())
