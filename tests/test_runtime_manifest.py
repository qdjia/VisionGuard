import hashlib
import json
from pathlib import Path

from visionguard.runtime.manifest import validate_model_bundle


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(root: Path) -> Path:
    bundle = root / "含 空格" / "models-v1"
    paths = {
        "detector": bundle / "detector" / "model.pt",
        "ocr_detection": bundle / "ocr" / "det",
        "ocr_recognition": bundle / "ocr" / "rec",
        "ocr_orientation": bundle / "ocr" / "ori",
        "baseline": bundle / "baseline" / "baseline_v1",
        "vlm": bundle / "vlm",
    }
    for name, path in paths.items():
        if name == "detector":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"detector")
        else:
            path.mkdir(parents=True, exist_ok=True)
            (path / "model.bin").write_bytes(name.encode())
    models = {}
    for name, path in paths.items():
        if path.is_file():
            models[name] = {
                "path": path.relative_to(bundle).as_posix(),
                "kind": "file",
                "size_bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
        else:
            child = path / "model.bin"
            models[name] = {
                "path": path.relative_to(bundle).as_posix(),
                "kind": "directory",
                "size_bytes": child.stat().st_size,
                "files": [
                    {
                        "path": "model.bin",
                        "size_bytes": child.stat().st_size,
                        "sha256": _hash(child),
                    }
                ],
            }
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_version": "models-v1",
                "compatible_runtime": {
                    "min_inclusive": "0.1.0",
                    "max_exclusive": "0.2.0",
                },
                "models": models,
            }
        ),
        encoding="utf-8",
    )
    return bundle


def test_quick_and_full_model_validation_support_unicode_paths(tmp_path):
    bundle = _bundle(tmp_path)
    manifest, result = validate_model_bundle(bundle, runtime_version="0.1.0", full_hash=True)
    assert manifest is not None
    assert result.status == "ready"
    assert all(value == "ready" for value in result.components.values())


def test_validation_detects_missing_and_hash_mismatch(tmp_path):
    missing_manifest, missing = validate_model_bundle(tmp_path / "missing", runtime_version="0.1.0")
    assert missing_manifest is None
    assert missing.status == "missing"

    bundle = _bundle(tmp_path)
    (bundle / "detector" / "model.pt").write_bytes(b"tampered")
    _, invalid = validate_model_bundle(bundle, runtime_version="0.1.0", full_hash=True)
    assert invalid.status == "invalid"
    assert invalid.components["detector"] == "invalid"


def test_validation_rejects_incompatible_runtime(tmp_path):
    bundle = _bundle(tmp_path)
    _, result = validate_model_bundle(bundle, runtime_version="1.0.0")
    assert result.status == "invalid"
    assert "RUNTIME_VERSION_MISMATCH" in result.errors
