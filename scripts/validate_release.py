"""Validate VisionGuard release assets and enforce local, RC, or stable gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

if __package__:
    from scripts.validate_license_alignment import PROJECT_LICENSE, validate_alignment
else:
    from validate_license_alignment import PROJECT_LICENSE, validate_alignment

ROOT = Path(__file__).resolve().parents[1]
GITHUB_ASSET_LIMIT = 2 * 1024**3
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
)
RC_REQUIRED_GATES = {
    "advanced_ai_install",
    "asset_hosting",
    "clean_machine",
    "detector_license",
    "gui_lifecycle",
    "local_inference",
    "reinstall",
    "rollback",
    "upgrade",
    "uninstall",
    "historical_regression",
    "license_distribution",
    "native_redistribution",
    "paddle_evidence",
    "qwen_evidence",
    "sbom",
}
ONLINE_REQUIRED_SBOMS = (
    "desktop.cdx.json",
    "core-runtime.cdx.json",
    "models.cdx.json",
    "distribution.cdx.json",
)
LEGACY_REQUIRED_SBOMS = (*ONLINE_REQUIRED_SBOMS, "vlm-runtime.cdx.json")
FORBIDDEN_ONLINE_NAMES = (
    "nvjitlink",
    "cublas",
    "cudnn",
    "cusparse",
    "cufft",
    "curand",
    "nvrtc",
    "torch_cuda",
)
DEV_ONLY_PACKAGES = {"pytest", "ruff", "notebook", "jupyter", "tensorboard", "mlflow"}
REQUIRED_MODEL_ROLES = {"vlm", "ocr_detection", "ocr_recognition", "ocr_orientation"}
REQUIRED_ACCEPTANCE_GATES = {
    "clean_machine",
    "gui_lifecycle",
    "upgrade",
    "rollback",
    "uninstall",
    "reinstall",
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


def _validate_sbom(path: Path, errors: list[str], *, enforce_runtime_hygiene: bool = False) -> dict:
    payload = _load_json(path, f"SBOM {path.name}", errors)
    if payload.get("bomFormat") != "CycloneDX" or payload.get("specVersion") != "1.6":
        errors.append(f"unsupported SBOM format: {path.name}")
    project_licenses = payload.get("metadata", {}).get("component", {}).get("licenses", [])
    if {item.get("license", {}).get("id") for item in project_licenses} != {PROJECT_LICENSE}:
        errors.append(f"SBOM project license is not {PROJECT_LICENSE}: {path.name}")
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        errors.append(f"SBOM has no components: {path.name}")
    if (
        enforce_runtime_hygiene
        and path.name in {"core-runtime.cdx.json", "vlm-runtime.cdx.json"}
        and isinstance(components, list)
    ):
        dev_only = sorted(
            {
                str(item.get("name", "")).casefold()
                for item in components
                if str(item.get("name", "")).casefold() in DEV_ONLY_PACKAGES
            }
        )
        if dev_only:
            errors.append(f"dev-only packages found in {path.name}: {', '.join(dev_only)}")
    return payload


def _validate_release_evidence(
    root: Path, errors: list[str], *, online_bootstrap: bool = False
) -> None:
    evidence = root / "release-evidence"
    provenance = _load_json(evidence / "model-provenance.json", "model provenance", errors)
    roles = {str(item.get("role")) for item in provenance.get("models", [])}
    missing_roles = sorted(REQUIRED_MODEL_ROLES - roles)
    if missing_roles:
        errors.append(f"model provenance roles missing: {', '.join(missing_roles)}")
    for item in provenance.get("models", []):
        if not re.fullmatch(r"[0-9a-f]{40}", str(item.get("revision", ""))):
            errors.append(f"model revision is not immutable: {item.get('role')}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            errors.append(f"model SHA-256 is invalid: {item.get('role')}")
        license_path = evidence / str(item.get("license_evidence", ""))
        if not license_path.is_file():
            errors.append(f"model license evidence missing: {item.get('role')}")
    native = _load_json(
        evidence / "native-nvidia-inventory.json", "NVIDIA native inventory", errors
    )
    files = native.get("files", [])
    if native.get("candidate_count") != len(files) or not files:
        errors.append("NVIDIA native inventory count is inconsistent")
    unique_files = {str(item.get("sha256")): item for item in files}.values()
    if native.get("unique_sha256_count") != len(unique_files):
        errors.append("NVIDIA native unique SHA-256 count is inconsistent")
    occurrence_statuses = dict(
        sorted(
            Counter(item.get("nvidia_redistribution", {}).get("status") for item in files).items()
        )
    )
    unique_statuses = dict(
        sorted(
            Counter(
                item.get("nvidia_redistribution", {}).get("status") for item in unique_files
            ).items()
        )
    )
    if native.get("status_counts") != occurrence_statuses:
        errors.append("NVIDIA native occurrence status counts are inconsistent")
    if native.get("unique_status_counts") != unique_statuses:
        errors.append("NVIDIA native unique status counts are inconsistent")
    unresolved = [
        item.get("path")
        for item in files
        if item.get("nvidia_redistribution", {}).get("status")
        not in {"ALLOWED", "ALLOWED_WITH_CONDITIONS"}
    ]
    if unresolved and not online_bootstrap:
        errors.append(
            f"NVIDIA redistribution remains unresolved: {', '.join(map(str, unresolved))}"
        )
    runtime = _load_json(evidence / "runtime-provenance.json", "runtime provenance", errors)
    versions = {
        str(item.get("name")): str(item.get("version")) for item in runtime.get("components", [])
    }
    for name in ("onnxruntime-gpu", "torch", "torchvision"):
        if not versions.get(name):
            errors.append(f"runtime provenance missing: {name}")

    detector = _load_json(evidence / "detector-provenance.json", "detector provenance", errors)
    detector_status = str(detector.get("redistribution_status", "")).upper()
    if detector_status not in {"ALLOWED", "ALLOWED_WITH_CONDITIONS"}:
        errors.append(f"detector redistribution is not cleared: {detector_status or 'MISSING'}")
    for field in ("base_checkpoint", "fine_tuned_checkpoint", "exported_onnx"):
        artifact = detector.get(field, {})
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", ""))):
            errors.append(f"detector provenance SHA-256 is invalid: {field}")
    required_detector_conditions = {
        "project_license_agpl_3_0_only",
        "license_and_notice_in_candidate",
        "corresponding_source_available",
        "build_training_export_scripts_available",
        "model_provenance_and_modifications_documented",
        "source_commit_and_expected_tag_recorded",
    }
    conditions = detector.get("conditions", {})
    missing_conditions = sorted(required_detector_conditions - conditions.keys())
    if detector_status == "ALLOWED_WITH_CONDITIONS" and missing_conditions:
        errors.append(
            f"detector redistribution conditions missing: {', '.join(missing_conditions)}"
        )
    if any(
        str(value).upper()
        not in {"IMPLEMENTED", "ENFORCED_BY_VALIDATOR", "ENFORCED_BY_RELEASE_PROCESS"}
        for value in conditions.values()
    ):
        errors.append("detector redistribution conditions are not fully implemented or enforced")

    local_inference = _load_json(
        evidence / "local-inference-architecture.json", "local inference architecture", errors
    )
    boundary = local_inference.get("product_boundary", {})
    if local_inference.get("status") != "PASS" or not boundary.get("local_review_inference"):
        errors.append("local inference architecture is not passed")
    if boundary.get("cloud_inference_enabled") is not False:
        errors.append("cloud inference must be disabled")

    nvjit = _load_json(evidence / "nvjitlink-analysis.json", "nvJitLink analysis", errors)
    nvjit_status = str(nvjit.get("redistribution_status", "")).upper()
    if not online_bootstrap and nvjit_status not in {"ALLOWED", "ALLOWED_WITH_CONDITIONS"}:
        errors.append(f"nvJitLink redistribution is not cleared: {nvjit_status or 'MISSING'}")

    acceptance = _load_json(evidence / "acceptance-status.json", "acceptance status", errors)
    acceptance_gates = acceptance.get("gates", {})
    for name in sorted(REQUIRED_ACCEPTANCE_GATES):
        status = str(acceptance_gates.get(name, {}).get("status", "MISSING")).upper()
        if status != "PASS":
            errors.append(f"acceptance evidence not passed: {name}={status}")

    regression = _load_json(
        evidence / "historical-regression.json", "historical regression", errors
    )
    if regression.get("confirmed_regression_count") != 0:
        errors.append("historical regression has confirmed regressions or missing count")
    regression_status = str(regression.get("gate_status", "")).upper()
    if regression_status != "PASS":
        errors.append(
            f"historical real-image regression is not passed: {regression_status or 'MISSING'}"
        )


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
    distribution = manifest.get("distribution", {})
    online_bootstrap = distribution.get("advanced_ai") == "online-bootstrap"
    required_sboms = ONLINE_REQUIRED_SBOMS if online_bootstrap else LEGACY_REQUIRED_SBOMS
    if manifest.get("schema_version") not in {1, 2, 3, 4}:
        errors.append("unsupported release manifest schema")
    release_version = str(manifest.get("release_version", ""))
    app_version = str(manifest.get("app_version", ""))
    if release_version.split("-", maxsplit=1)[0] != app_version:
        errors.append("release/app versions are inconsistent")
    checksums = _checksums(checksum_path, errors)
    for name, expected in checksums.items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            errors.append(f"unsafe checksum path: {name}")
            continue
        target = root / name
        if not target.is_file():
            errors.append(f"checksummed file does not exist: {name}")
        elif sha256(target) != expected:
            errors.append(f"checksum file mismatch: {name}")
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
    metadata_files = [str(name) for name in manifest.get("metadata_files", [])]
    if manifest.get("schema_version") in {3, 4}:
        for name in metadata_files:
            if Path(name).is_absolute() or ".." in Path(name).parts:
                errors.append(f"unsafe metadata path: {name}")
                continue
            target = root / name
            if not target.is_file():
                errors.append(f"metadata file does not exist: {name}")
            if name != checksum_path.name and name not in checksums:
                errors.append(f"metadata file is not checksummed: {name}")
        if manifest_path.name not in checksums:
            errors.append("release manifest is not checksummed")
        for name in required_sboms:
            path = root / "sbom" / name
            if path.is_file():
                _validate_sbom(path, errors)
    text_files = [manifest_path, notes_path]
    text_files.extend(
        root / name
        for name in metadata_files
        if Path(name).suffix.lower() in {".json", ".md", ".txt"} and (root / name).is_file()
    )
    for text_file in dict.fromkeys(text_files):
        content = text_file.read_text(encoding="utf-8")
        if ABSOLUTE_PATH.search(content):
            errors.append(f"absolute private path found: {text_file.name}")
        if SECRET_PATTERN.search(content):
            errors.append(f"possible secret found: {text_file.name}")
    if online_bootstrap:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lowered = path.name.casefold()
            if any(
                token in lowered for token in FORBIDDEN_ONLINE_NAMES
            ) or path.suffix.casefold() in {".whl", ".safetensors", ".gguf"}:
                errors.append(f"forbidden online-bootstrap release asset: {path.relative_to(root)}")
    if public and not distribution.get("public_release_ready", False):
        errors.append("release manifest explicitly blocks public distribution")
    if gate in {"rc", "stable"}:
        if manifest.get("project_license") != PROJECT_LICENSE:
            errors.append(f"release manifest project license is not {PROJECT_LICENSE}")
        source = manifest.get("source", {})
        if not re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit", ""))):
            errors.append("release source commit is missing or invalid")
        if source.get("expected_tag") != f"v{release_version}":
            errors.append("release expected tag does not match release version")
        for filename in ("LICENSE", "NOTICE"):
            if not (root / filename).is_file():
                errors.append(f"missing project license file: {filename}")
        for error in validate_alignment(ROOT):
            errors.append(f"source license alignment: {error}")
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
        for sbom in required_sboms:
            sbom_path = root / "sbom" / sbom
            if not sbom_path.is_file():
                errors.append(f"missing release SBOM: sbom/{sbom}")
            else:
                _validate_sbom(sbom_path, errors, enforce_runtime_hygiene=True)
        _validate_release_evidence(root, errors, online_bootstrap=online_bootstrap)
        models_path = root / "sbom/models.cdx.json"
        if models_path.is_file():
            model_names = {
                str(item.get("name"))
                for item in _load_json(models_path, "models SBOM", errors).get("components", [])
            }
            required_models = (
                ("detector/model.onnx",)
                if online_bootstrap
                else (
                    "detector/model.onnx",
                    "vlm/model.safetensors",
                )
            )
            for required_model in required_models:
                if required_model not in model_names:
                    errors.append(f"model is missing from SBOM: {required_model}")
        distribution_path = root / "sbom/distribution.cdx.json"
        if distribution_path.is_file():
            distribution_components = _load_json(
                distribution_path, "distribution SBOM", errors
            ).get("components", [])
            if not any(item.get("hashes") for item in distribution_components):
                errors.append("WebView2 distribution component is not hash-inventoried")
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
    if gate in {"rc", "stable"}:
        manifest = _load_json(root / "release-manifest.json", "release manifest", [])
        for name in sorted(RC_REQUIRED_GATES):
            value = str(manifest.get("gates", {}).get(name, "missing")).casefold()
            status = (
                "PASS"
                if value == "passed"
                else "FAIL"
                if value == "failed"
                else "N/A"
                if value == "n/a"
                else "BLOCKED"
            )
            print(f"GATE {name}: {status}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"release validation passed: {root.name} (gate={gate})")


if __name__ == "__main__":
    main()
