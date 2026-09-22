"""Versioned, path-safe model bundle manifests and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, ValidationError, field_validator

from visionguard.config.models import StrictConfigModel


class ManifestFile(StrictConfigModel):
    path: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("manifest paths must be safe relative POSIX paths")
        return path.as_posix()


class ModelArtifact(StrictConfigModel):
    path: str
    kind: Literal["file", "directory"]
    required: bool = True
    size_bytes: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    files: tuple[ManifestFile, ...] = ()

    _safe_path = field_validator("path")(ManifestFile.safe_relative_path.__func__)


class RuntimeCompatibility(StrictConfigModel):
    min_inclusive: str
    max_exclusive: str


class ModelBundleManifest(StrictConfigModel):
    schema_version: Literal[1] = 1
    bundle_version: str = Field(pattern=r"^models-v[0-9]+(?:\.[0-9]+)*$")
    compatible_runtime: RuntimeCompatibility
    models: dict[str, ModelArtifact]


class ModelValidationResult(StrictConfigModel):
    bundle_version: str | None = None
    status: Literal["ready", "missing", "invalid"]
    components: dict[str, Literal["ready", "missing", "invalid"]]
    errors: tuple[str, ...] = ()


REQUIRED_MODELS = {
    "detector",
    "ocr_detection",
    "ocr_recognition",
    "ocr_orientation",
    "baseline",
    "vlm",
}


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as exc:
        raise ValueError(f"invalid numeric runtime version: {value}") from exc


def load_manifest(bundle_dir: str | Path) -> ModelBundleManifest:
    source = Path(bundle_dir).resolve() / "manifest.json"
    try:
        return ModelBundleManifest.model_validate_json(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid model bundle manifest: {source}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _component(name: str) -> str:
    if name.startswith("ocr_"):
        return "ocr"
    return name


def validate_model_bundle(
    bundle_dir: str | Path,
    *,
    runtime_version: str,
    full_hash: bool = False,
) -> tuple[ModelBundleManifest | None, ModelValidationResult]:
    root = Path(bundle_dir).resolve()
    components = {name: "ready" for name in ("detector", "ocr", "baseline", "vlm")}
    errors: list[str] = []
    if not (root / "manifest.json").is_file():
        return None, ModelValidationResult(
            status="missing",
            components={key: "missing" for key in components},
            errors=("MODEL_BUNDLE_MISSING",),
        )
    try:
        manifest = load_manifest(root)
    except ValueError:
        return None, ModelValidationResult(
            status="invalid",
            components={key: "invalid" for key in components},
            errors=("MODEL_BUNDLE_INVALID",),
        )
    missing_keys = REQUIRED_MODELS.difference(manifest.models)
    if missing_keys:
        errors.append("missing manifest entries: " + ", ".join(sorted(missing_keys)))
        for name in missing_keys:
            components[_component(name)] = "missing"
    current = _version_tuple(runtime_version)
    if not (
        _version_tuple(manifest.compatible_runtime.min_inclusive)
        <= current
        < _version_tuple(manifest.compatible_runtime.max_exclusive)
    ):
        errors.append("RUNTIME_VERSION_MISMATCH")
    for name, artifact in manifest.models.items():
        target = (root / artifact.path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            components[_component(name)] = "invalid"
            errors.append(f"{name}: path escapes model bundle")
            continue
        expected_type = target.is_file() if artifact.kind == "file" else target.is_dir()
        if not expected_type:
            components[_component(name)] = "missing"
            errors.append(f"{name}: required path missing")
            continue
        if artifact.kind == "file":
            if target.stat().st_size != artifact.size_bytes:
                components[_component(name)] = "invalid"
                errors.append(f"{name}: file size mismatch")
            elif full_hash and artifact.sha256 and _sha256(target) != artifact.sha256:
                components[_component(name)] = "invalid"
                errors.append(f"{name}: SHA-256 mismatch")
        else:
            for item in artifact.files:
                child = (target / item.path).resolve()
                try:
                    child.relative_to(target)
                except ValueError:
                    components[_component(name)] = "invalid"
                    errors.append(f"{name}: child path escapes component")
                    continue
                if not child.is_file():
                    components[_component(name)] = "missing"
                    errors.append(f"{name}: missing {item.path}")
                elif child.stat().st_size != item.size_bytes:
                    components[_component(name)] = "invalid"
                    errors.append(f"{name}: size mismatch for {item.path}")
                elif full_hash and _sha256(child) != item.sha256:
                    components[_component(name)] = "invalid"
                    errors.append(f"{name}: SHA-256 mismatch for {item.path}")
    status = "ready"
    if any(value == "missing" for value in components.values()):
        status = "missing"
    elif errors:
        status = "invalid"
    return manifest, ModelValidationResult(
        bundle_version=manifest.bundle_version,
        status=status,
        components=components,
        errors=tuple(errors),
    )


def resolved_model_paths(bundle_dir: Path, manifest: ModelBundleManifest) -> dict[str, Path]:
    return {
        name: (bundle_dir / artifact.path).resolve()
        for name, artifact in manifest.models.items()
    }
