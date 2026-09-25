"""Build a checksummed, split Advanced AI package for local/offline import."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

MIB = 1024**2
DEFAULT_PART_SIZE_MIB = 1024
BUFFER_SIZE = 4 * MIB


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _safe_version(value: str) -> str:
    if not value or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in value
    ):
        raise ValueError(f"unsafe component version: {value!r}")
    return value


def _zip_directory(source: Path, target: Path, root_name: str) -> int:
    if not source.is_dir():
        raise FileNotFoundError(source)
    unpacked = directory_size(source)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for item in sorted(source.rglob("*")):
            if item.is_symlink():
                raise ValueError(f"component source cannot contain symlinks: {item}")
            if item.is_file():
                archive.write(item, Path(root_name) / item.relative_to(source))
    return unpacked


def _copy_stream(source: BinaryIO, target: BinaryIO, limit: int) -> int:
    written = 0
    while written < limit:
        chunk = source.read(min(BUFFER_SIZE, limit - written))
        if not chunk:
            break
        target.write(chunk)
        written += len(chunk)
    return written


def split_archive(
    archive: Path, output: Path, public_name: str, part_size: int
) -> list[dict[str, object]]:
    if part_size <= 0:
        raise ValueError("part size must be positive")
    parts: list[dict[str, object]] = []
    with archive.open("rb") as source:
        index = 1
        while source.tell() < archive.stat().st_size:
            part = output / f"{public_name}.part{index:02d}"
            with part.open("wb") as target:
                size = _copy_stream(source, target, part_size)
            parts.append(
                {
                    "index": index,
                    "file": part.name,
                    "size_bytes": size,
                    "sha256": sha256(part),
                }
            )
            index += 1
    return parts


def build_component(
    *,
    kind: str,
    source: Path,
    version: str,
    output: Path,
    part_size: int,
    prefix: str,
) -> dict[str, object]:
    version = _safe_version(version)
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    public_component = {"vlm_runtime": "VLM-Runtime", "vlm_models": "VLM-Models"}[kind]
    public_name = f"{prefix}-{public_component}-{version}.zip"
    with tempfile.TemporaryDirectory(prefix="visionguard-package-") as temporary:
        archive = Path(temporary) / public_name
        if source.is_dir():
            unpacked_size = _zip_directory(source, archive, f"{kind}-{version}")
        elif source.suffix.lower() == ".zip":
            shutil.copy2(source, archive)
            with zipfile.ZipFile(archive) as payload:
                unpacked_size = sum(
                    item.file_size for item in payload.infolist() if not item.is_dir()
                )
        else:
            raise ValueError(f"{kind} source must be a directory or ZIP: {source}")
        archive_size = archive.stat().st_size
        archive_hash = sha256(archive)
        parts = split_archive(archive, output, public_name, part_size)
    return {
        "version": version,
        "archive_format": "zip",
        "archive_size_bytes": archive_size,
        "unpacked_size_bytes": unpacked_size,
        "archive_sha256": archive_hash,
        "parts": parts,
    }


def build_package(
    *,
    runtime: Path,
    models: Path,
    output: Path,
    package_version: str,
    runtime_version: str,
    model_version: str,
    part_size_mib: int = DEFAULT_PART_SIZE_MIB,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    part_size = part_size_mib * MIB
    components = {
        "vlm_runtime": build_component(
            kind="vlm_runtime",
            source=runtime,
            version=runtime_version,
            output=output,
            part_size=part_size,
            prefix="VisionGuard",
        ),
        "vlm_models": build_component(
            kind="vlm_models",
            source=models,
            version=model_version,
            output=output,
            part_size=part_size,
            prefix="VisionGuard",
        ),
    }
    source_bytes = sum(
        int(part["size_bytes"])
        for component in components.values()
        for part in component["parts"]  # type: ignore[index]
    )
    installed_bytes = sum(
        int(component["unpacked_size_bytes"]) for component in components.values()
    )
    # Parts remain in the user's selected folder. Installation streams ZIP data into staging,
    # so it does not require a second reconstructed archive.
    staging_bytes = installed_bytes
    safety_bytes = max(512 * MIB, installed_bytes // 10)
    manifest = {
        "schema_version": 1,
        "component": "advanced_ai",
        "package_version": _safe_version(package_version),
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": "windows",
        "architecture": "x86_64",
        "install_strategy": "verified_parts_stream_to_staging_then_atomic_activate",
        "components": components,
        "disk_requirements": {
            "source_parts_bytes": source_bytes,
            "staging_bytes": staging_bytes,
            "safety_margin_bytes": safety_bytes,
            "additional_free_bytes_required": staging_bytes + safety_bytes,
            "peak_bytes_including_source_parts": source_bytes + staging_bytes + safety_bytes,
        },
    }
    target = output / "advanced-ai-manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Verify the emitted files before reporting success.
    for component in components.values():
        for part in component["parts"]:  # type: ignore[index]
            path = output / str(part["file"])
            if path.stat().st_size != part["size_bytes"] or sha256(path) != part["sha256"]:
                raise RuntimeError(f"part verification failed: {path.name}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True, help="VLM runtime directory or ZIP")
    parser.add_argument("--models", type=Path, required=True, help="VLM model directory or ZIP")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True, help="Advanced AI package version")
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--part-size-mib", type=int, default=DEFAULT_PART_SIZE_MIB)
    args = parser.parse_args()
    manifest = build_package(
        runtime=args.runtime,
        models=args.models,
        output=args.output,
        package_version=args.version,
        runtime_version=args.runtime_version,
        model_version=args.model_version,
        part_size_mib=args.part_size_mib,
    )
    print(manifest)


if __name__ == "__main__":
    main()
