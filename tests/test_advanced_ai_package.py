from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_advanced_ai_package import build_package, sha256


def _component(root: Path, marker: str, size: int) -> Path:
    root.mkdir()
    (root / marker).write_bytes(marker.encode() + b"x" * size)
    return root


def test_build_package_emits_ordered_verified_parts(tmp_path: Path) -> None:
    runtime = _component(tmp_path / "runtime", "runtime-manifest.json", 256)
    models = _component(tmp_path / "models", "manifest.json", 512)
    output = tmp_path / "output"
    manifest_path = build_package(
        runtime=runtime,
        models=models,
        output=output,
        package_version="advanced-ai-v1",
        runtime_version="0.1.0",
        model_version="vlm-models-v1",
        part_size_mib=1,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["install_strategy"].startswith("verified_parts_stream")
    for component in manifest["components"].values():
        assert [part["index"] for part in component["parts"]] == list(
            range(1, len(component["parts"]) + 1)
        )
        for part in component["parts"]:
            target = output / part["file"]
            assert target.stat().st_size == part["size_bytes"]
            assert sha256(target) == part["sha256"]
    assert manifest["disk_requirements"]["additional_free_bytes_required"] > 0


def test_build_package_accepts_zip_source(tmp_path: Path) -> None:
    runtime_zip = tmp_path / "runtime.zip"
    with zipfile.ZipFile(runtime_zip, "w") as archive:
        archive.writestr("vlm-runtime/runtime-manifest.json", "{}")
    models = _component(tmp_path / "models", "manifest.json", 8)
    manifest = build_package(
        runtime=runtime_zip,
        models=models,
        output=tmp_path / "output",
        package_version="v1",
        runtime_version="0.1.0",
        model_version="v1",
        part_size_mib=1,
    )
    assert manifest.is_file()


def test_build_package_rejects_unsafe_version(tmp_path: Path) -> None:
    runtime = _component(tmp_path / "runtime", "runtime-manifest.json", 1)
    models = _component(tmp_path / "models", "manifest.json", 1)
    with pytest.raises(ValueError, match="unsafe component version"):
        build_package(
            runtime=runtime,
            models=models,
            output=tmp_path / "output",
            package_version="../escape",
            runtime_version="0.1.0",
            model_version="v1",
        )
