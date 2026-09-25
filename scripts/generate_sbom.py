"""Generate release-scoped CycloneDX SBOMs without inspecting the development environment."""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)((?:==|~=|>=|<=|>|<)[^;\s]+)")
NATIVE_SUFFIXES = {".dll", ".exe", ".pyd"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def component(
    name: str, version: str, *, group: str, license_id: str | None = None
) -> dict[str, object]:
    value: dict[str, object] = {
        "type": "library",
        "group": group,
        "name": name,
        "version": version,
        "bom-ref": f"pkg:{group}/{name}@{version}",
    }
    if license_id:
        value["licenses"] = [{"license": {"id": license_id}}]
    return value


def python_components(requirements: Path, profile: str) -> list[dict[str, object]]:
    result = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT.match(raw.strip())
        if match:
            specifier = match.group(2)
            version = specifier.removeprefix("==") if specifier.startswith("==") else "unspecified"
            value = component(match.group(1), version, group=f"python-{profile}")
            value["properties"] = [
                {"name": "visionguard:inventory_source", "value": "requirement_profile"},
                {"name": "visionguard:requirement_specifier", "value": specifier},
            ]
            result.append(value)
    return result


def frozen_python_components(runtime_root: Path, profile: str) -> list[dict[str, object]]:
    internal = runtime_root / "_internal"
    if not internal.is_dir():
        return []
    result = []
    seen: set[tuple[str, str]] = set()
    for metadata in sorted(internal.rglob("*.dist-info/METADATA")):
        message = email.message_from_string(metadata.read_text(encoding="utf-8", errors="replace"))
        name = message.get("Name")
        version = message.get("Version")
        if not name or not version or (name.casefold(), version) in seen:
            continue
        seen.add((name.casefold(), version))
        value = component(name, version, group=f"python-{profile}")
        value["properties"] = [
            {"name": "visionguard:inventory_source", "value": "frozen_dist_info"},
            {
                "name": "visionguard:metadata_path",
                "value": metadata.relative_to(runtime_root).as_posix(),
            },
        ]
        result.append(value)
    return result


def node_components(lockfile: Path) -> list[dict[str, object]]:
    payload = json.loads(lockfile.read_text(encoding="utf-8"))
    result = []
    for path, package in payload.get("packages", {}).items():
        if not path or not path.startswith("node_modules/") or "version" not in package:
            continue
        name = package.get("name") or path.removeprefix("node_modules/")
        result.append(
            component(name, str(package["version"]), group="npm", license_id=package.get("license"))
        )
    return result


def rust_components(lockfile: Path) -> list[dict[str, object]]:
    payload = tomllib.loads(lockfile.read_text(encoding="utf-8"))
    return [
        component(str(package["name"]), str(package["version"]), group="cargo")
        for package in payload.get("package", [])
    ]


def native_components(runtime_root: Path, profile: str) -> list[dict[str, object]]:
    if not runtime_root.is_dir():
        return []
    result = []
    for path in sorted(runtime_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in NATIVE_SUFFIXES:
            relative = path.relative_to(runtime_root).as_posix()
            result.append(
                {
                    "type": "file",
                    "group": f"native-{profile}",
                    "name": relative,
                    "version": "bundled",
                    "bom-ref": f"file:{profile}/{relative}",
                    "hashes": [{"alg": "SHA-256", "content": sha256(path)}],
                    "properties": [
                        {"name": "visionguard:size_bytes", "value": str(path.stat().st_size)}
                    ],
                }
            )
    return result


def model_components(manifest_path: Path, profile: str) -> list[dict[str, object]]:
    """Inventory the exact model files recorded by a frozen model-bundle manifest."""
    if not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_version = str(payload.get("bundle_version", "unknown"))
    result: list[dict[str, object]] = []
    for name, model in sorted(payload.get("models", {}).items()):
        base = str(model.get("path", name))
        provenance = model.get("provenance", {})
        provenance_properties = [
            {"name": f"visionguard:model_{key}", "value": str(provenance[key])}
            for key in ("model_id", "revision", "license", "source")
            if provenance.get(key)
        ]
        files = model.get("files", [])
        if files:
            for entry in files:
                relative = f"{base}/{entry['path']}"
                result.append(
                    {
                        "type": "file",
                        "group": f"model-{profile}",
                        "name": relative,
                        "version": bundle_version,
                        "bom-ref": f"model:{profile}/{relative}@{bundle_version}",
                        "hashes": [{"alg": "SHA-256", "content": entry["sha256"]}],
                        "properties": [
                            {
                                "name": "visionguard:size_bytes",
                                "value": str(entry["size_bytes"]),
                            },
                            {"name": "visionguard:model_role", "value": name},
                        ]
                        + provenance_properties,
                    }
                )
        elif model.get("sha256"):
            result.append(
                {
                    "type": "machine-learning-model",
                    "group": f"model-{profile}",
                    "name": base,
                    "version": bundle_version,
                    "bom-ref": f"model:{profile}/{base}@{bundle_version}",
                    "hashes": [{"alg": "SHA-256", "content": model["sha256"]}],
                    "properties": [
                        {"name": "visionguard:size_bytes", "value": str(model["size_bytes"])},
                        {"name": "visionguard:model_role", "value": name},
                    ]
                    + provenance_properties,
                }
            )
    return result


def distribution_components(webview_installer: Path | None) -> list[dict[str, object]]:
    value: dict[str, object] = {
        "type": "application",
        "group": "microsoft",
        "name": "Microsoft Edge WebView2 Evergreen Offline Installer (x64)",
        "version": "bundled",
        "bom-ref": "distribution:microsoft/webview2-evergreen-offline-x64@bundled",
        "properties": [{"name": "visionguard:bundle_mode", "value": "tauri_offline_installer"}],
    }
    if webview_installer and webview_installer.is_file():
        value["hashes"] = [{"alg": "SHA-256", "content": sha256(webview_installer)}]
        value["properties"].extend(
            [
                {"name": "visionguard:size_bytes", "value": str(webview_installer.stat().st_size)},
                {"name": "visionguard:inventory_source", "value": "tauri_build_cache"},
            ]
        )
    else:
        value["properties"].append(
            {"name": "visionguard:inventory_source", "value": "tauri_configuration_only"}
        )
    return [value]


def write_sbom(output: Path, name: str, version: str, components: list[dict[str, object]]) -> Path:
    target = output / f"{name}.cdx.json"
    payload = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{hashlib.sha256((name + version).encode()).hexdigest()[:32]}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": {
                "type": "application",
                "name": f"VisionGuard {name}",
                "version": version,
                "licenses": [{"license": {"id": "AGPL-3.0-only"}}],
            },
            "properties": [{"name": "visionguard:source", "value": "release lock/profile"}],
        },
        "components": sorted(components, key=lambda item: str(item["bom-ref"])),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def generate(output: Path, version: str, webview_installer: Path | None = None) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    desktop = node_components(ROOT / "desktop/package-lock.json") + rust_components(
        ROOT / "desktop/src-tauri/Cargo.lock"
    )
    core_root = ROOT / "runtime-dist-core/visionguard-core-runtime"
    vlm_root = ROOT / "runtime-dist-vlm/visionguard-vlm-runtime"
    core_python = frozen_python_components(core_root, "core") or python_components(
        ROOT / "requirements-runtime-core.txt", "core"
    )
    vlm_python = frozen_python_components(vlm_root, "vlm") or python_components(
        ROOT / "requirements-runtime-vlm.txt", "vlm"
    )
    core = core_python + native_components(core_root, "core")
    vlm = vlm_python + native_components(vlm_root, "vlm")
    models = model_components(
        ROOT / "models/core-models-v1/manifest.json", "core"
    ) + model_components(ROOT / "models/vlm-models-v1/manifest.json", "vlm")
    return [
        write_sbom(output, "desktop", version, desktop),
        write_sbom(output, "core-runtime", version, core),
        write_sbom(output, "vlm-runtime", version, vlm),
        write_sbom(output, "models", version, models),
        write_sbom(
            output,
            "distribution",
            version,
            distribution_components(webview_installer),
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/sbom")
    parser.add_argument("--version", required=True)
    parser.add_argument("--webview-installer", type=Path)
    args = parser.parse_args()
    for path in generate(args.output, args.version, args.webview_installer):
        print(path)


if __name__ == "__main__":
    main()
