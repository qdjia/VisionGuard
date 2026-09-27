import hashlib
import json
from pathlib import Path

from scripts.build_model_bundle import attach_provenance
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


def test_core_bundle_is_ready_without_optional_vlm(tmp_path):
    bundle = _bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "schema_version": 2,
            "bundle_version": "core-models-v1",
            "bundle_type": "core",
        }
    )
    payload["models"].pop("vlm")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest, result = validate_model_bundle(bundle, runtime_version="0.1.0", full_hash=True)

    assert manifest is not None
    assert manifest.bundle_type == "core"
    assert result.status == "ready"
    assert result.components["vlm"] == "missing"


def test_model_bundle_accepts_release_provenance(tmp_path):
    bundle = _bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    attach_provenance(
        payload["models"],
        {
            "ocr_detection": {
                "model_id": "PaddlePaddle/PP-OCRv6_medium_det",
                "revision": "8e0f56fb2ef86b461d99cfc7ac5c137738985f61",
                "license": "Apache-2.0",
                "source": "https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det",
                "artifact": "inference.pdiparams",
                "sha256": "8" * 64,
            }
        },
    )
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest, result = validate_model_bundle(bundle, runtime_version="0.1.0")

    assert manifest is not None
    assert result.status == "ready"
    assert manifest.models["ocr_detection"].provenance is not None
    assert manifest.models["ocr_detection"].provenance.license == "Apache-2.0"


def test_model_bundle_rejects_malformed_release_provenance(tmp_path):
    bundle = _bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["models"]["ocr_detection"]["provenance"] = {
        "model_id": "PaddlePaddle/PP-OCRv6_medium_det",
        "revision": "revision",
        "license": "Apache-2.0",
        "source": "https://example.invalid/model",
        "artifact": "inference.pdiparams",
        "sha256": "not-a-sha256",
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest, result = validate_model_bundle(bundle, runtime_version="0.1.0")

    assert manifest is None
    assert result.status == "invalid"
    assert result.errors == ("MODEL_BUNDLE_INVALID",)
