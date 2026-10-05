import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

from scripts import build_model_bundle
from scripts.build_release import (
    copy_release_evidence,
    derive_final_rc_gates,
    redact_private_paths,
    replace_directory,
    validate_release_mode,
    write_release_notes,
)
from scripts.prepare_gate1_core_models import write_isolated_training_configs
from scripts.validate_release import (
    RC_REQUIRED_GATES,
    _stable_code_signing_accepted,
    _validate_release_evidence,
    _validate_sbom,
    _validate_stable_risk_waiver,
    release_gate_display_status,
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


def test_strict_release_modes_select_the_correct_validator_gate() -> None:
    common = {
        "app_version": "1.0.0",
        "advanced_ai_mode": "online-bootstrap",
        "skip_build": False,
        "no_clean": False,
        "skip_advanced_ai": False,
        "skip_validation": False,
    }

    assert (
        validate_release_mode(version="1.0.0-rc.1", final_rc=True, stable=False, **common) == "rc"
    )
    assert validate_release_mode(version="1.0.0", final_rc=False, stable=True, **common) == "stable"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"version": "1.0.0-rc.1", "stable": True}, "--stable requires version 1.0.0"),
        (
            {"advanced_ai_mode": "bundled", "stable": True},
            "--stable only supports online-bootstrap",
        ),
        ({"skip_build": True, "stable": True}, "--stable forbids"),
        (
            {"final_rc": True, "stable": True},
            "--final-rc and --stable are mutually exclusive",
        ),
    ],
)
def test_strict_release_modes_fail_closed(overrides: dict[str, object], message: str) -> None:
    arguments: dict[str, object] = {
        "version": "1.0.0",
        "app_version": "1.0.0",
        "final_rc": False,
        "stable": False,
        "advanced_ai_mode": "online-bootstrap",
        "skip_build": False,
        "no_clean": False,
        "skip_advanced_ai": False,
        "skip_validation": False,
    }
    arguments.update(overrides)

    with pytest.raises(ValueError, match=message):
        validate_release_mode(**arguments)  # type: ignore[arg-type]


def test_stable_release_notes_disclose_waived_risks(tmp_path: Path) -> None:
    notes = write_release_notes(
        tmp_path,
        "1.0.0",
        [],
        strict_gate="stable",
        limitations=["Independent clean-machine replay remains incomplete."],
    ).read_text(encoding="utf-8")

    assert "Stable Candidate" in notes
    for token in ("clean-machine", "unsigned", "SmartScreen", "SHA-256"):
        assert token in notes


def test_historical_limitation_requires_waiver_for_stable() -> None:
    assert release_gate_passed("historical_regression", "passed_with_limitation", "rc")
    assert not release_gate_passed("historical_regression", "passed_with_limitation", "stable")
    assert release_gate_passed(
        "historical_regression",
        "passed_with_limitation",
        "stable",
        allow_stable_historical_waiver=True,
    )
    assert (
        release_gate_display_status(
            "historical_regression",
            "passed_with_limitation",
            "stable",
            allow_stable_historical_waiver=True,
        )
        == "WAIVED"
    )
    assert not release_gate_passed("clean_core", "passed_with_limitation", "rc")


def test_stable_risk_waiver_accepts_only_declared_v1_requirements(tmp_path: Path) -> None:
    evidence = tmp_path / "release-evidence"
    evidence.mkdir()
    source = Path("release-evidence/stable-release-risk-waiver.json")
    (evidence / source.name).write_bytes(source.read_bytes())

    errors: list[str] = []
    accepted = _validate_stable_risk_waiver(evidence, "1.0.0", errors)

    assert errors == []
    assert accepted == {
        "historical_clean_machine_replay",
        "authenticode_code_signing",
    }
    assert _stable_code_signing_accepted("unsigned", accepted)
    assert _stable_code_signing_accepted("authenticode_trusted", set())
    assert not _stable_code_signing_accepted("unsigned", set())
    assert not _stable_code_signing_accepted("unknown", accepted)


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (("scope", "v1.0.1"), "stable risk waiver scope does not match v1.0.0"),
        (
            ("valid_for_future_versions", True),
            "stable risk waiver must not apply to future versions",
        ),
        (
            ("does_not_claim_pass", False),
            "stable risk waiver must explicitly preserve incomplete gate status",
        ),
    ],
)
def test_stable_risk_waiver_fails_closed_on_invalid_boundary(
    tmp_path: Path,
    mutation: tuple[str, object],
    expected_error: str,
) -> None:
    evidence = tmp_path / "release-evidence"
    evidence.mkdir()
    payload = json.loads(
        Path("release-evidence/stable-release-risk-waiver.json").read_text(encoding="utf-8")
    )
    payload[mutation[0]] = mutation[1]
    (evidence / "stable-release-risk-waiver.json").write_text(json.dumps(payload), encoding="utf-8")

    errors: list[str] = []
    accepted = _validate_stable_risk_waiver(evidence, "1.0.0", errors)

    assert accepted == set()
    assert expected_error in errors


def test_stable_risk_waiver_requires_residual_risks(tmp_path: Path) -> None:
    evidence = tmp_path / "release-evidence"
    evidence.mkdir()
    payload = json.loads(
        Path("release-evidence/stable-release-risk-waiver.json").read_text(encoding="utf-8")
    )
    payload["decisions"]["historical_clean_machine_replay"]["residual_risks"] = []
    (evidence / "stable-release-risk-waiver.json").write_text(json.dumps(payload), encoding="utf-8")

    errors: list[str] = []
    accepted = _validate_stable_risk_waiver(evidence, "1.0.0", errors)

    assert accepted == set()
    assert (
        "stable risk waiver residual risks are missing: historical_clean_machine_replay" in errors
    )


def test_stable_risk_waiver_is_missing_by_default(tmp_path: Path) -> None:
    errors: list[str] = []

    accepted = _validate_stable_risk_waiver(tmp_path, "1.0.0", errors)

    assert accepted == set()
    assert len(errors) == 1
    assert errors[0].startswith("invalid stable release risk waiver:")


def test_stable_validator_applies_waiver_to_limited_history_and_unsigned_installer(
    tmp_path: Path,
) -> None:
    target = _release(tmp_path)
    manifest_path = target / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "release_version": "1.0.0",
            "app_version": "1.0.0",
            "project_license": "AGPL-3.0-only",
            "source": {"commit": "a" * 40, "expected_tag": "v1.0.0"},
            "gates": {name: "passed" for name in RC_REQUIRED_GATES},
        }
    )
    manifest["gates"]["historical_regression"] = "passed_with_limitation"
    manifest["distribution"] = {
        "advanced_ai": "online-bootstrap",
        "public_release_ready": True,
        "blockers": [],
        "code_signing": "unsigned",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    write_release_notes(target, "1.0.0", [], strict_gate="stable")
    (target / "LICENSE").write_bytes(Path("LICENSE").read_bytes())
    (target / "NOTICE").write_bytes(Path("NOTICE").read_bytes())
    evidence = target / "release-evidence"
    evidence.mkdir()
    for item in Path("release-evidence").iterdir():
        if item.is_file():
            (evidence / item.name).write_bytes(item.read_bytes())

    waived_errors = validate_release(target, gate="stable")

    assert "release gate not passed: historical_regression" not in waived_errors
    assert "historical regression clean-machine limitation is not allowed for stable" not in (
        waived_errors
    )
    assert "stable installer is not Authenticode signed" not in waived_errors

    (evidence / "stable-release-risk-waiver.json").unlink()
    unwaived_errors = validate_release(target, gate="stable")

    assert "release gate not passed: historical_regression" in unwaived_errors
    assert "historical regression clean-machine limitation is not allowed for stable" in (
        unwaived_errors
    )
    assert "stable installer is not Authenticode signed" in unwaived_errors


def test_release_evidence_redacts_private_paths_without_mutating_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    target = tmp_path / "release-evidence" / "source.json"
    payload = {
        "model": r"D:\VisionGuard-Acceptance\advanced-ai\models\vlm",
        "nested": [r"C:\Users\developer\cache", "https://example.com/model"],
        "status": "PASS",
    }
    source.write_text(json.dumps(payload), encoding="utf-8")

    copy_release_evidence(source, target)

    copied = json.loads(target.read_text(encoding="utf-8"))
    assert copied["model"] == "<redacted-local-path>"
    assert copied["nested"] == ["<redacted-local-path>", "https://example.com/model"]
    assert copied["status"] == "PASS"
    assert json.loads(source.read_text(encoding="utf-8")) == payload


def test_private_path_redaction_handles_nested_values() -> None:
    assert redact_private_paths({"path": "/home/developer/model", "count": 1}) == {
        "path": "<redacted-local-path>",
        "count": 1,
    }


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
