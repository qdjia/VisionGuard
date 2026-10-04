import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

from scripts import build_model_bundle
from scripts.build_release import derive_final_rc_gates, replace_directory
from scripts.prepare_gate1_core_models import write_isolated_training_configs
from scripts.validate_release import (
    _validate_release_evidence,
    _validate_sbom,
    release_gate_passed,
    validate_release,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release(root: Path) -> Path:
    target = root / "v0.1.0-rc.1"
    target.mkdir()
    installer = target / "VisionGuard-Setup-GPU-0.1.0-rc.1.exe"
    installer.write_bytes(b"installer")
    digest = _hash(installer)
    manifest = {
        "schema_version": 1,
        "release_version": "0.1.0-rc.1",
        "app_version": "0.1.0",
        "distribution": {"public_release_ready": False},
        "assets": [
            {
                "name": installer.name,
                "kind": "windows_gpu_installer",
                "size_bytes": installer.stat().st_size,
                "sha256": digest,
                "github_asset_compatible": True,
                "publishable": True,
            }
        ],
    }
    (target / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (target / "SHA256SUMS.txt").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    (target / "RELEASE_NOTES.md").write_text("# Candidate\n", encoding="utf-8")
    return target


def test_release_validation_accepts_local_candidate(tmp_path: Path) -> None:
    target = _release(tmp_path)
    assert validate_release(target) == []


def test_public_validation_honors_manifest_gate(tmp_path: Path) -> None:
    target = _release(tmp_path)
    assert "release manifest explicitly blocks public distribution" in validate_release(
        target, public=True
    )


def test_release_validation_detects_tampering(tmp_path: Path) -> None:
    target = _release(tmp_path)
    next(target.glob("*.exe")).write_bytes(b"tampered")
    errors = validate_release(target)
    assert any("SHA-256 mismatch" in error for error in errors)


def test_schema_three_requires_metadata_checksums(tmp_path: Path) -> None:
    target = _release(tmp_path)
    manifest_path = target / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 3
    manifest["metadata_files"] = ["SHA256SUMS.txt", "RELEASE_NOTES.md"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    errors = validate_release(target)
    assert "metadata file is not checksummed: RELEASE_NOTES.md" in errors
    assert "release manifest is not checksummed" in errors


def test_runtime_sbom_rejects_dev_only_packages(tmp_path: Path) -> None:
    sbom = tmp_path / "vlm-runtime.cdx.json"
    sbom.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "metadata": {"component": {"licenses": [{"license": {"id": "AGPL-3.0-only"}}]}},
                "components": [{"name": "pytest", "version": "8.4.2"}],
            }
        ),
        encoding="utf-8",
    )
    errors: list[str] = []
    _validate_sbom(sbom, errors, enforce_runtime_hygiene=True)
    assert errors == ["dev-only packages found in vlm-runtime.cdx.json: pytest"]


def test_release_evidence_fails_closed_for_unclear_native_file(tmp_path: Path) -> None:
    evidence = tmp_path / "release-evidence"
    license_path = evidence / "licenses" / "APACHE-2.0.txt"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("Apache-2.0", encoding="utf-8")
    models = [
        {
            "role": role,
            "revision": "a" * 40,
            "sha256": "b" * 64,
            "license_evidence": "licenses/APACHE-2.0.txt",
        }
        for role in ("vlm", "ocr_detection", "ocr_recognition", "ocr_orientation")
    ]
    (evidence / "model-provenance.json").write_text(
        json.dumps({"models": models}), encoding="utf-8"
    )
    (evidence / "native-nvidia-inventory.json").write_text(
        json.dumps(
            {
                "candidate_count": 1,
                "unique_sha256_count": 1,
                "status_counts": {"UNCLEAR": 1},
                "unique_status_counts": {"UNCLEAR": 1},
                "files": [
                    {
                        "path": "nvJitLink_120_0.dll",
                        "sha256": "c" * 64,
                        "nvidia_redistribution": {"status": "UNCLEAR"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (evidence / "runtime-provenance.json").write_text(
        json.dumps(
            {
                "components": [
                    {"name": "onnxruntime-gpu", "version": "1.26.0"},
                    {"name": "torch", "version": "2.11.0+cu128"},
                    {"name": "torchvision", "version": "0.26.0+cu128"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (evidence / "detector-provenance.json").write_text(
        json.dumps(
            {
                "redistribution_status": "ALLOWED_WITH_CONDITIONS",
                "conditions": {
                    "project_license_agpl_3_0_only": "IMPLEMENTED",
                    "license_and_notice_in_candidate": "ENFORCED_BY_VALIDATOR",
                    "corresponding_source_available": "ENFORCED_BY_RELEASE_PROCESS",
                    "build_training_export_scripts_available": "IMPLEMENTED",
                    "model_provenance_and_modifications_documented": "IMPLEMENTED",
                    "source_commit_and_expected_tag_recorded": "ENFORCED_BY_VALIDATOR",
                },
                "base_checkpoint": {"sha256": "d" * 64},
                "fine_tuned_checkpoint": {"sha256": "e" * 64},
                "exported_onnx": {"sha256": "f" * 64},
            }
        ),
        encoding="utf-8",
    )
    (evidence / "nvjitlink-analysis.json").write_text(
        json.dumps({"redistribution_status": "ALLOWED_WITH_CONDITIONS"}),
        encoding="utf-8",
    )
    (evidence / "acceptance-status.json").write_text(
        json.dumps(
            {
                "gates": {
                    name: {"status": "PASS"}
                    for name in (
                        "clean_core",
                        "fresh_user_gui",
                        "advanced_ai_gpu",
                        "overall_clean_environment",
                        "upgrade",
                        "rollback",
                        "uninstall",
                        "reinstall",
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    (evidence / "upgrade-rollback-acceptance.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "gate": "installer_lifecycle",
                "status": "PASS",
                "baseline": {
                    "app_version": "0.9.0",
                    "git_sha": "a" * 40,
                    "workflow_run_id": "1",
                    "installer_name": "baseline.exe",
                    "actual_sha256": "b" * 64,
                },
                "candidate": {
                    "app_version": "1.0.0",
                    "git_sha": "c" * 40,
                    "workflow_run_id": "2",
                    "installer_name": "candidate.exe",
                    "actual_sha256": "d" * 64,
                },
                "upgrade": {"status": "PASS", "checks": {}},
                "rollback": {"status": "PASS", "checks": {}},
                "cleanup": {
                    "uninstall_exit_code": 0,
                    "install_directory_removed": True,
                    "orphan_processes": [],
                },
            }
        ),
        encoding="utf-8",
    )
    windows_gates = {
        "clean_core": "windows-core-acceptance.json",
        "fresh_user_gui": "fresh-user-gui.json",
        "advanced_ai_gpu": "advanced-ai-gpu-acceptance.json",
    }
    for gate, filename in windows_gates.items():
        (evidence / filename).write_text(
            json.dumps({"schema_version": 1, "gate": gate, "status": "PASS"}),
            encoding="utf-8",
        )
    (evidence / "windows-acceptance-summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acceptance_model": "split-windows-acceptance",
                "gates": {
                    gate: {"status": "PASS", "evidence": filename}
                    for gate, filename in windows_gates.items()
                },
                "overall_clean_environment": "PASS",
            }
        ),
        encoding="utf-8",
    )
    (evidence / "local-inference-architecture.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "product_boundary": {
                    "local_review_inference": True,
                    "cloud_inference_enabled": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (evidence / "historical-regression.json").write_text(
        json.dumps(
            {
                "historical_image_case_count": 27,
                "verified_real_world_image_provenance_count": 27,
                "ground_truth_image_case_count": 27,
                "packaged_core_runtime_replayed": True,
                "managed_local_vlm_runtime_replayed": True,
                "clean_machine_replay_completed": True,
                "confirmed_regression_count": 0,
                "potential_regression_count": 0,
                "gate_status": "PASS",
            }
        ),
        encoding="utf-8",
    )
    errors: list[str] = []
    _validate_release_evidence(tmp_path, errors)
    assert errors == ["NVIDIA redistribution remains unresolved: nvJitLink_120_0.dll"]


def test_repository_blocker_evidence_fails_closed() -> None:
    errors: list[str] = []
    _validate_release_evidence(Path.cwd(), errors)
    assert not any("detector redistribution" in error for error in errors)
    assert "nvJitLink redistribution is not cleared: UNCLEAR" in errors
    assert not any("clean_core=" in error for error in errors)
    assert not any("advanced_ai_gpu=" in error for error in errors)
    assert not any("overall clean-environment acceptance" in error for error in errors)
    assert not any("20-50 real-image" in error for error in errors)
    assert not any("provenance is incomplete" in error for error in errors)
    assert not any("ground truth is incomplete" in error for error in errors)
    assert not any("did not replay packaged Core" in error for error in errors)
    assert not any("did not replay managed local VLM" in error for error in errors)
    assert "historical regression clean-machine replay is incomplete" not in errors
    assert "historical regression has confirmed regressions or missing count" not in errors
    assert not any("historical real-image regression is not passed" in error for error in errors)


def test_limited_historical_regression_requires_explicit_risk_acceptance(
    tmp_path: Path,
) -> None:
    source = Path("release-evidence")
    evidence = tmp_path / "release-evidence"
    evidence.mkdir()
    for item in source.iterdir():
        if item.is_file():
            (evidence / item.name).write_bytes(item.read_bytes())
    payload_path = evidence / "historical-regression.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["risk_acceptance"]["status"] = "NOT_ACCEPTED"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    errors: list[str] = []
    _validate_release_evidence(tmp_path, errors)

    assert "limited historical regression risk was not accepted" in errors


def test_stable_gate_rejects_historical_regression_limitation(tmp_path: Path) -> None:
    source = Path("release-evidence")
    evidence = tmp_path / "release-evidence"
    evidence.mkdir()
    for item in source.iterdir():
        if item.is_file():
            (evidence / item.name).write_bytes(item.read_bytes())

    errors: list[str] = []
    _validate_release_evidence(tmp_path, errors, allow_historical_limitation=False)

    assert "historical regression clean-machine limitation is not allowed for stable" in errors


def test_final_rc_gates_are_derived_from_repository_evidence() -> None:
    gates, blockers = derive_final_rc_gates(Path("release-evidence"))

    assert blockers == []
    assert gates["historical_regression"] == "passed_with_limitation"
    assert all(value in {"passed", "passed_with_limitation"} for value in gates.values())


def test_historical_limitation_is_rc_only() -> None:
    assert release_gate_passed("historical_regression", "passed_with_limitation", "rc")
    assert not release_gate_passed("historical_regression", "passed_with_limitation", "stable")
    assert not release_gate_passed("clean_core", "passed_with_limitation", "rc")


def test_release_directory_replacement_is_bounded_and_atomic(tmp_path: Path) -> None:
    target = tmp_path / "core-models-v1"
    staged = tmp_path / ".core-models-v1-staged"
    target.mkdir()
    staged.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")
    (staged / "new.txt").write_text("new", encoding="utf-8")

    replace_directory(staged, target, allowed_parent=tmp_path)

    assert not staged.exists()
    assert not (tmp_path / ".core-models-v1.previous").exists()
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"


def test_forced_model_bundle_preserves_existing_output_when_sources_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "core-models-v1"
    output.mkdir()
    marker = output / "existing.txt"
    marker.write_text("keep", encoding="utf-8")
    missing = tmp_path / "missing"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_model_bundle.py",
            "--profile",
            "core",
            "--output",
            str(output),
            "--detector",
            str(missing / "detector.onnx"),
            "--baseline",
            str(missing / "baseline"),
            "--ocr-detection",
            str(missing / "ocr-det"),
            "--ocr-recognition",
            str(missing / "ocr-rec"),
            "--ocr-orientation",
            str(missing / "ocr-ori"),
            "--force",
        ],
    )

    with pytest.raises(FileNotFoundError, match="missing model sources"):
        build_model_bundle.main()

    assert marker.read_text(encoding="utf-8") == "keep"


def test_final_rc_training_configs_are_isolated(tmp_path: Path) -> None:
    detector_config, detector_model, baseline_config, baseline_model = (
        write_isolated_training_configs(tmp_path)
    )
    detector = yaml.safe_load(detector_config.read_text(encoding="utf-8"))
    baseline = yaml.safe_load(baseline_config.read_text(encoding="utf-8"))["baseline"]

    assert detector_model.parent.parent == tmp_path / "experiments" / detector["experiment_name"]
    assert baseline_model == tmp_path / "baseline" / baseline["experiment_name"]
    assert Path(detector["artifacts_dir"]) == (tmp_path / "experiments").resolve()
    assert Path(baseline["artifacts_dir"]) == (tmp_path / "baseline").resolve()
