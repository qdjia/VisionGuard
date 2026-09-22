"""Validate VisionGuard release metadata, hashes, versions, and publication gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

GITHUB_ASSET_LIMIT = 2 * 1024**3
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_release(root: Path, *, public: bool = False) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "release-manifest.json"
    checksum_path = root / "SHA256SUMS.txt"
    notes_path = root / "RELEASE_NOTES.md"
    for required in (manifest_path, checksum_path, notes_path):
        if not required.is_file():
            errors.append(f"missing required release file: {required.name}")
    if errors:
        return errors
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid release manifest: {exc}"]
    if manifest.get("schema_version") != 1:
        errors.append("unsupported release manifest schema")
    release_version = str(manifest.get("release_version", ""))
    app_version = str(manifest.get("app_version", ""))
    if release_version.split("-", maxsplit=1)[0] != app_version:
        errors.append("release/app versions are inconsistent")
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            errors.append(f"invalid checksum line: {line}")
            continue
        checksums[parts[1]] = parts[0]
    binary_assets = [asset for asset in manifest.get("assets", []) if "sha256" in asset]
    kinds = {asset.get("kind") for asset in binary_assets}
    if "windows_gpu_installer" not in kinds:
        errors.append("installer asset is missing")
    for asset in binary_assets:
        name = asset.get("name")
        target = root / str(name)
        if not target.is_file():
            errors.append(f"asset does not exist: {name}")
            continue
        actual = sha256(target)
        if actual != asset.get("sha256") or actual != checksums.get(str(name)):
            errors.append(f"SHA-256 mismatch: {name}")
        if target.stat().st_size != asset.get("size_bytes"):
            errors.append(f"size mismatch: {name}")
        compatible = target.stat().st_size < GITHUB_ASSET_LIMIT
        if compatible != asset.get("github_asset_compatible"):
            errors.append(f"GitHub size flag mismatch: {name}")
        if public and (not compatible or not asset.get("publishable", False)):
            errors.append(f"asset is not eligible for public GitHub upload: {name}")
    for text_file in (manifest_path, notes_path):
        content = text_file.read_text(encoding="utf-8")
        if ABSOLUTE_PATH.search(content):
            errors.append(f"absolute private path found: {text_file.name}")
        if SECRET_PATTERN.search(content):
            errors.append(f"possible secret found: {text_file.name}")
    if public and not manifest.get("distribution", {}).get("public_release_ready", False):
        errors.append("release manifest explicitly blocks public distribution")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_dir", type=Path)
    parser.add_argument("--public", action="store_true", help="Enforce public GitHub gates")
    args = parser.parse_args()
    root = args.release_dir.expanduser().resolve()
    errors = validate_release(root, public=args.public)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"release validation passed: {root.name} (public={args.public})")


if __name__ == "__main__":
    main()
