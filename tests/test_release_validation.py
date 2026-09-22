import hashlib
import json
from pathlib import Path

from scripts.validate_release import validate_release


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
