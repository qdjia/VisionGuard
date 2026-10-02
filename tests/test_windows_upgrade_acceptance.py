from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_windows_upgrade_acceptance import (
    LifecycleAcceptanceError,
    install_fingerprint,
    load_candidate,
    validate_candidate_pair,
    version_tuple,
)


def _candidate(tmp_path: Path, name: str, version: str, commit: str) -> dict[str, object]:
    installer = tmp_path / f"{name}.exe"
    installer.write_bytes(name.encode())
    metadata = tmp_path / f"{name}.json"
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "git_sha": commit,
                "workflow_run_id": name,
                "installer_name": installer.name,
                "sha256": hashlib.sha256(name.encode()).hexdigest(),
                "app_version": version,
            }
        ),
        encoding="utf-8",
    )
    return load_candidate(installer, metadata, name)


def test_version_tuple_requires_numeric_semver() -> None:
    assert version_tuple("1.2.3") == (1, 2, 3)
    with pytest.raises(LifecycleAcceptanceError, match="numeric application version"):
        version_tuple("1.0.0-rc.1")
    with pytest.raises(LifecycleAcceptanceError, match="numeric application version"):
        version_tuple("01.0.0")


def test_candidate_pair_requires_newer_distinct_build(tmp_path: Path) -> None:
    baseline = _candidate(tmp_path, "baseline", "1.0.0", "a" * 40)
    candidate = _candidate(tmp_path, "candidate", "1.1.0", "b" * 40)
    validate_candidate_pair(baseline, candidate)

    candidate["app_version"] = "1.0.0"
    with pytest.raises(LifecycleAcceptanceError, match="greater than baseline"):
        validate_candidate_pair(baseline, candidate)


def test_candidate_metadata_rejects_hash_mismatch(tmp_path: Path) -> None:
    installer = tmp_path / "candidate.exe"
    installer.write_bytes(b"candidate")
    metadata = tmp_path / "candidate.json"
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "git_sha": "b" * 40,
                "workflow_run_id": "42",
                "installer_name": installer.name,
                "sha256": "0" * 64,
                "app_version": "1.1.0",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LifecycleAcceptanceError, match="SHA-256"):
        load_candidate(installer, metadata, "candidate")


def test_candidate_metadata_requires_version(tmp_path: Path) -> None:
    installer = tmp_path / "candidate.exe"
    installer.write_bytes(b"candidate")
    metadata = tmp_path / "candidate.json"
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "git_sha": "b" * 40,
                "workflow_run_id": "42",
                "installer_name": installer.name,
                "sha256": hashlib.sha256(b"candidate").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LifecycleAcceptanceError, match="app_version"):
        load_candidate(installer, metadata, "candidate")


def test_install_fingerprint_tracks_critical_payload_and_bootstrap_wheel(
    tmp_path: Path,
) -> None:
    files = (
        "visionguard-desktop.exe",
        "components/core-runtime/visionguard-core-runtime.exe",
        "components/core-runtime/runtime-manifest.json",
        "components/core-models/manifest.json",
        "bootstrap/advanced-ai-bootstrap-manifest.json",
        "bootstrap/packages/visionguard_moderation-1.0.0-py3-none-any.whl",
    )
    for relative in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(relative.encode())
    fingerprint = install_fingerprint(tmp_path)
    assert set(fingerprint) == set(files)
    assert all(len(value) == 64 for value in fingerprint.values())

    (tmp_path / "visionguard-desktop.exe").write_bytes(b"updated")
    assert install_fingerprint(tmp_path) != fingerprint


def test_install_fingerprint_fails_closed_for_ambiguous_wheels(tmp_path: Path) -> None:
    required = (
        "visionguard-desktop.exe",
        "components/core-runtime/visionguard-core-runtime.exe",
        "components/core-runtime/runtime-manifest.json",
        "components/core-models/manifest.json",
        "bootstrap/advanced-ai-bootstrap-manifest.json",
    )
    for relative in required:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"payload")
    with pytest.raises(LifecycleAcceptanceError, match="wheel inventory"):
        install_fingerprint(tmp_path)
