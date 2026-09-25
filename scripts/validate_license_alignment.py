"""Fail closed when VisionGuard-owned license metadata or product claims drift."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PROJECT_LICENSE = "AGPL-3.0-only"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_alignment(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text or "Version 3" not in license_text:
        errors.append("root LICENSE is not the GNU Affero General Public License v3")
    notice = (root / "NOTICE").read_text(encoding="utf-8")
    if "Copyright (c) 2026 qdjia" not in notice or PROJECT_LICENSE not in notice:
        errors.append("NOTICE does not preserve copyright and AGPL identifier")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject.get("project", {}).get("license") != PROJECT_LICENSE:
        errors.append("pyproject project license is inconsistent")
    package = _json(root / "desktop/package.json")
    package_lock = _json(root / "desktop/package-lock.json")
    if package.get("license") != PROJECT_LICENSE:
        errors.append("desktop package license is inconsistent")
    if package_lock.get("packages", {}).get("", {}).get("license") != PROJECT_LICENSE:
        errors.append("desktop lockfile root package license is inconsistent")
    cargo = tomllib.loads((root / "desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    if cargo.get("package", {}).get("license") != PROJECT_LICENSE:
        errors.append("Tauri Cargo package license is inconsistent")
    tauri = _json(root / "desktop/src-tauri/tauri.release.conf.json")
    if tauri.get("bundle", {}).get("license") != PROJECT_LICENSE:
        errors.append("Tauri bundle license is inconsistent")
    if tauri.get("bundle", {}).get("licenseFile") != "../../LICENSE":
        errors.append("Tauri installer does not reference the root LICENSE")
    resources = tauri.get("bundle", {}).get("resources", {})
    if resources.get("../../NOTICE") != "NOTICE":
        errors.append("Tauri installer does not bundle NOTICE")

    app_source = (root / "desktop/src/App.tsx").read_text(encoding="utf-8")
    if f"<dd>{PROJECT_LICENSE}</dd>" not in app_source:
        errors.append("desktop About dialog license is inconsistent")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for phrase in (PROJECT_LICENSE, "本地推理", "不依赖云端推理 API"):
        if phrase not in readme:
            errors.append(f"README is missing required positioning: {phrase}")
    if re.search(r"VisionGuard 自有(?:源)?代码使用 MIT", readme):
        errors.append("README still claims MIT for VisionGuard-owned code")
    notices = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    if PROJECT_LICENSE not in notices or "第三方" not in notices:
        errors.append("third-party notices do not preserve the license boundary")

    vlm_config = (root / "configs/vlm.yaml").read_text(encoding="utf-8")
    api_config = (root / "configs/api.yaml").read_text(encoding="utf-8")
    local_provider = (root / "src/visionguard/vlm/providers/remote.py").read_text(encoding="utf-8")
    if not re.search(r"(?m)^\s*provider:\s*local\s*$", vlm_config):
        errors.append("VLM provider is not configured for local inference")
    if not re.search(r"(?m)^\s*host:\s*127\.0\.0\.1\s*$", api_config):
        errors.append("API is not configured for loopback")
    if 'endpoint.startswith("http://127.0.0.1:")' not in local_provider:
        errors.append("local VLM sidecar endpoint is not restricted to loopback")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_alignment(args.root.resolve())
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        raise SystemExit(1)
    print(f"license alignment passed: {PROJECT_LICENSE}")


if __name__ == "__main__":
    main()
