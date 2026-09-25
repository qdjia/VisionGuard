from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_sbom import (
    distribution_components,
    frozen_python_components,
    model_components,
    python_components,
    write_sbom,
)


def test_python_sbom_uses_pinned_release_profile(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("torch==2.9.1+cu128\n# comment\nfastapi>=0.115,<1\n", encoding="utf-8")
    result = python_components(requirements, "vlm")
    assert [(item["name"], item["version"]) for item in result] == [
        ("torch", "2.9.1+cu128"),
        ("fastapi", "unspecified"),
    ]
    assert result[1]["properties"][1]["value"] == ">=0.115,<1"


def test_sbom_is_cyclonedx_and_deterministically_sorted(tmp_path: Path) -> None:
    target = write_sbom(
        tmp_path,
        "core-runtime",
        "1.0.0-rc.1",
        [
            {"type": "library", "name": "z", "version": "1", "bom-ref": "z"},
            {"type": "library", "name": "a", "version": "1", "bom-ref": "a"},
        ],
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["bomFormat"] == "CycloneDX"
    assert [item["bom-ref"] for item in payload["components"]] == ["a", "z"]


def test_frozen_python_inventory_uses_exact_dist_info_version(tmp_path: Path) -> None:
    metadata = tmp_path / "_internal" / "torch-2.11.0+cu128.dist-info" / "METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("Name: torch\nVersion: 2.11.0+cu128\n", encoding="utf-8")
    result = frozen_python_components(tmp_path, "vlm")
    assert [(item["name"], item["version"]) for item in result] == [("torch", "2.11.0+cu128")]
    assert result[0]["properties"][0]["value"] == "frozen_dist_info"


def test_model_inventory_uses_frozen_manifest_hashes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "bundle_version": "models-v1",
                "models": {
                    "detector": {
                        "path": "detector/model.onnx",
                        "size_bytes": 7,
                        "sha256": "a" * 64,
                        "files": [],
                    },
                    "ocr": {
                        "path": "ocr/model",
                        "files": [{"path": "weights.bin", "size_bytes": 9, "sha256": "b" * 64}],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    result = model_components(manifest, "core")
    assert [item["name"] for item in result] == ["detector/model.onnx", "ocr/model/weights.bin"]
    assert result[1]["hashes"][0]["content"] == "b" * 64


def test_distribution_inventory_hashes_webview_installer(tmp_path: Path) -> None:
    installer = tmp_path / "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    installer.write_bytes(b"webview")
    result = distribution_components(installer)
    assert result[0]["hashes"][0]["alg"] == "SHA-256"
    assert result[0]["properties"][-1]["value"] == "tauri_build_cache"
