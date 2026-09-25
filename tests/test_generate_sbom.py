from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_sbom import frozen_python_components, python_components, write_sbom


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
