"""CWD-independent source, frozen-resource, model, and user-data paths."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from visionguard.runtime.config import RuntimeConfig


@dataclass(frozen=True)
class RuntimeResources:
    resource_root: Path
    executable_dir: Path
    model_bundle_dir: Path
    user_data_dir: Path
    runtime_dir: Path
    artifact_dir: Path
    log_dir: Path
    cache_dir: Path


def packaged_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
        candidate = base / "resources"
        return candidate if candidate.is_dir() else base
    return Path(__file__).resolve().parents[3]


def resolve_resources(config: RuntimeConfig) -> RuntimeResources:
    resource_root = packaged_resource_root()
    executable_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[3]
    )
    resources = RuntimeResources(
        resource_root=resource_root,
        executable_dir=executable_dir,
        model_bundle_dir=config.model_bundle_path.resolve(),
        user_data_dir=config.user_data_dir.resolve(),
        runtime_dir=(config.user_data_dir / "runtime").resolve(),
        artifact_dir=config.artifact_root.resolve(),
        log_dir=config.log_root.resolve(),
        cache_dir=config.cache_root.resolve(),
    )
    for directory in (
        resources.user_data_dir,
        resources.runtime_dir,
        resources.artifact_dir,
        resources.log_dir,
        resources.cache_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    for required in (resource_root / "configs", resource_root / "prompts"):
        if not required.is_dir():
            raise FileNotFoundError(f"packaged runtime resource directory missing: {required.name}")
    return resources
