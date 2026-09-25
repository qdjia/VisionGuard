"""Validate VisionGuard release assets and enforce local, RC, or stable gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB_ASSET_LIMIT = 2 * 1024**3
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
)
RC_REQUIRED_GATES = {
    "advanced_ai_install",
    "clean_machine",
    "offline",
    "upgrade",
    "uninstall",
    "historical_regression",
    "license_distribution",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str, errors: list[str]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid {label}: {exc}")
        return {}


def _checksums(path: Path, errors: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            errors.append(f"invalid checksum line: {line}")
        else:
            result[parts[1]] = parts[0]
    return result


def _validate_advanced_manifest(root: Path, relative: str, errors: list[str]) -> None:
    path = root / relative
    if not path.is_file():
        errors.append(f"advanced AI manifest does not exist: {relative}")
        return
    manifest = _load_json(path, "advanced AI manifest", errors)
    if manifest.get("schema_version") != 1 or manifest.get("component") != "advanced_ai":
        errors.append("unsupported advanced AI manifest")
        return
    names: set[str] = set()
    for component_name, component in manifest.get("components", {}).items():
        archive_size = 0
        digest = hashlib.sha256()
        for expected_index, part in enumerate(component.get("parts", []), 1):
            name = str(part.get("file", ""))
            if part.get("index") != expected_index or Path(name).name != name or name in names:
                errors.append(f"invalid or duplicate {component_name} part: {name}")
                continue
            names.add(name)
            target = path.parent / name
            if not target.is_file():
                errors.append(f"advanced AI part does not exist: {name}")
                continue
            size = target.stat().st_size
            archive_size += size
            actual = sha256(target)
            if size != part.get("size_bytes") or actual != part.get("sha256"):
                errors.append(f"advanced AI part mismatch: {name}")
            with target.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
        if archive_size != component.get("archive_size_bytes"):
            errors.append(f"advanced AI archive size mismatch: {component_name}")
        if digest.hexdigest() != component.get("archive_sha256"):
            errors.append(f"advanced AI archive hash mismatch: {component_name}")


def validate_release(
    root: Path,
    *,
    public: bool = False,
    gate: str = "local",
) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "release-manifest.json"
    checksum_path = root / "SHA256SUMS.txt"
    notes_path = root / "RELEASE_NOTES.md"
    for required in (manifest_path, checksum_path, notes_path):
        if not required.is_file():
            errors.append(f"missing required release file: {required.name}")
    if errors:
        return errors
    manifest = _load_json(manifest_path, "release manifest", errors)
    if not manifest:
        return errors
    if manifest.get("schema_version") not in {1, 2, 3}:
        errors.append("unsupported release manifest schema")
    release_version = str(manifest.get("release_version", ""))
    app_version = str(manifest.get("app_version", ""))
    if release_version.split("-", maxsplit=1)[0] != app_version:
        errors.append("release/app versions are inconsistent")
    checksums = _checksums(checksum_path, errors)
    binary_assets = [asset for asset in manifest.get("assets", []) if "sha256" in asset]
    kinds = {asset.get("kind") for asset in binary_assets}
    if not ({"windows_installer", "windows_gpu_installer"} & kinds):
        errors.append("installer asset is missing")
    for asset in binary_assets:
        name = str(asset.get("name", ""))
        if Path(name).name != name:
            errors.append(f"unsafe asset name: {name}")
            continue
        target = root / name
        if not target.is_file():
            errors.append(f"asset does not exist: {name}")
            continue
        actual = sha256(target)
        if actual != asset.get("sha256") or actual != checksums.get(name):
            errors.append(f"SHA-256 mismatch: {name}")
        if target.stat().st_size != asset.get("size_bytes"):
            errors.append(f"size mismatch: {name}")
        compatible = target.stat().st_size < GITHUB_ASSET_LIMIT
        if compatible != asset.get("github_asset_compatible"):
            errors.append(f"GitHub size flag mismatch: {name}")
        if (public or gate in {"rc", "stable"}) and (
            not compatible or not asset.get("publishable", False)
        ):
            errors.append(f"asset is not eligible for public distribution: {name}")
    advanced_manifest = manifest.get("distribution", {}).get("advanced_ai_manifest")
    if advanced_manifest:
        _validate_advanced_manifest(root, str(advanced_manifest), errors)
    for text_file in (manifest_path, notes_path):
        content = text_file.read_text(encoding="utf-8")
        if ABSOLUTE_PATH.search(content):
            errors.append(f"absolute private path found: {text_file.name}")
        if SECRET_PATTERN.search(content):
            errors.append(f"possible secret found: {text_file.name}")
    distribution = manifest.get("distribution", {})
    if public and not distribution.get("public_release_ready", False):
        errors.append("release manifest explicitly blocks public distribution")
    if gate in {"rc", "stable"}:
        if gate == "rc" and not re.fullmatch(r"1\.0\.0-rc\.[1-9][0-9]*", release_version):
            errors.append("RC release version must match 1.0.0-rc.N")
        if gate == "stable" and release_version != "1.0.0":
            errors.append("stable release version must be 1.0.0")
        blockers = distribution.get("blockers", [])
        if blockers:
            errors.append(f"release has unresolved blockers: {', '.join(map(str, blockers))}")
        gates = manifest.get("gates", {})
        for name in sorted(RC_REQUIRED_GATES):
            if gates.get(name) != "passed":
                errors.append(f"RC gate not passed: {name}")
        for sbom in ("desktop.cdx.json", "core-runtime.cdx.json", "vlm-runtime.cdx.json"):
            if not (root / "sbom" / sbom).is_file():
                errors.append(f"missing release SBOM: sbom/{sbom}")
        if not distribution.get("public_release_ready", False):
            errors.append("RC distribution is not marked public_release_ready")
    if gate == "stable":
        if distribution.get("code_signing") != "authenticode_trusted":
            errors.append("stable installer is not Authenticode signed")
    return errors


def _latest_release() -> Path:
    candidates = sorted(
        (ROOT / "release").glob("v*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("no local release directory found")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_dir", type=Path, nargs="?")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--rc", action="store_true", help="Enforce the v1.0 RC gate")
    mode.add_argument("--stable", action="store_true", help="Enforce the stable gate")
    parser.add_argument(
        "--public", action="store_true", help="Compatibility alias for public asset gates"
    )
    args = parser.parse_args()
    root = (args.release_dir or _latest_release()).expanduser().resolve()
    gate = "stable" if args.stable else "rc" if args.rc else "local"
    errors = validate_release(root, public=args.public, gate=gate)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"release validation passed: {root.name} (gate={gate})")


if __name__ == "__main__":
    main()
