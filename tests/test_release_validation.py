import hashlib
import json
from pathlib import Path

from scripts.validate_release import _validate_release_evidence, _validate_sbom, validate_release


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
    errors: list[str] = []
    _validate_release_evidence(tmp_path, errors)
    assert errors == ["NVIDIA redistribution remains unresolved: nvJitLink_120_0.dll"]
