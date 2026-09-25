"""Build component runtimes; the legacy monolith is explicit opt-in only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "runtime-build"
DIST_ROOT = ROOT / "runtime-dist"
TAURI_BIN = ROOT / "desktop" / "src-tauri" / "binaries"
RUNTIME_VERSION = "0.1.0"
DEV_ONLY_DISTRIBUTIONS = ("pytest", "ruff", "notebook", "jupyter", "tensorboard", "mlflow")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_runtime_manifest(root: Path, *, profile: str = "core") -> Path:
    files = []
    for item in sorted(root.rglob("*")):
        if item.is_file() and item.name != "runtime-manifest.json":
            files.append(
                {
                    "path": item.relative_to(root).as_posix(),
                    "size_bytes": item.stat().st_size,
                    "sha256": sha256(item),
                }
            )
    manifest = {
        "schema_version": 1,
        "runtime_version": RUNTIME_VERSION,
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": f"visionguard-{profile}-runtime.exe",
        "component": "advanced_ai" if profile == "vlm" else "core",
        "profile": profile,
        "files": files,
    }
    target = root / "runtime-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def link_or_copy_tree(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        destination = target / item.relative_to(source)
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            link_or_copy(item, destination)


def target_triple() -> str:
    executable = shutil.which("rustc")
    if executable is None:
        fallback = Path.home() / ".cargo" / "bin" / "rustc.exe"
        executable = str(fallback) if fallback.is_file() else None
    if executable is None:
        raise FileNotFoundError("rustc is required to determine the Tauri target triple")
    return subprocess.check_output(
        [executable, "--print", "host-tuple"], text=True, encoding="utf-8"
    ).strip()


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() or None


def safe_clean(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != ROOT.resolve():
        raise ValueError(f"refusing to clean unexpected path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def remove_dev_only_metadata(runtime_root: Path) -> list[str]:
    """Remove stray dev-only dist-info copied by upstream PyInstaller hooks."""
    internal = runtime_root / "_internal"
    removed = []
    if not internal.is_dir():
        return removed
    for item in internal.iterdir():
        lowered = item.name.casefold().replace("_", "-")
        if (
            item.is_dir()
            and item.name.endswith(".dist-info")
            and any(lowered.startswith(f"{name}-") for name in DEV_ONLY_DISTRIBUTIONS)
        ):
            shutil.rmtree(item)
            removed.append(item.name)
    return sorted(removed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--profile", choices=("core", "vlm", "full"), default="core")
    parser.add_argument(
        "--stage-tauri",
        action="store_true",
        help="Replace the desktop sidecar staging area after a successful build.",
    )
    args = parser.parse_args()
    suffix = "" if args.profile == "full" else f"-{args.profile}"
    build_root = BUILD_ROOT if not suffix else ROOT / f"runtime-build{suffix}"
    dist_root = DIST_ROOT if not suffix else ROOT / f"runtime-dist{suffix}"
    if not args.no_clean:
        safe_clean(build_root)
        safe_clean(dist_root)
    build_environment = os.environ.copy()
    build_environment["YOLO_AUTOINSTALL"] = "false"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--workpath",
            str(build_root),
            "--distpath",
            str(dist_root),
            str(
                ROOT
                / "packaging"
                / "runtime"
                / (
                    "visionguard-core-runtime.spec"
                    if args.profile == "core"
                    else "visionguard-vlm-runtime.spec"
                    if args.profile == "vlm"
                    else "visionguard-runtime.spec"
                )
            ),
        ],
        cwd=ROOT,
        env=build_environment,
        check=True,
    )
    runtime_name = (
        "visionguard-runtime" if args.profile == "full" else f"visionguard-{args.profile}-runtime"
    )
    source = dist_root / runtime_name
    executable = source / f"{runtime_name}.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller output missing: {executable}")
    removed_dev_metadata = remove_dev_only_metadata(source)
    manifest_path = write_runtime_manifest(source, profile=args.profile)
    staged_executable = None
    triple = target_triple()
    if args.stage_tauri:
        TAURI_BIN.mkdir(parents=True, exist_ok=True)
        support = TAURI_BIN / "_internal"
        if support.exists():
            shutil.rmtree(support)
        internal = source / "_internal"
        if internal.is_dir():
            link_or_copy_tree(internal, support)
        staged_executable = TAURI_BIN / f"{runtime_name}-{triple}.exe"
        staged_executable.unlink(missing_ok=True)
        link_or_copy(executable, staged_executable)
    metadata = {
        "runtime_version": RUNTIME_VERSION,
        "python_version": platform.python_version(),
        "build_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "packager": "PyInstaller",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "target_triple": triple,
        "profile": args.profile,
        "removed_dev_only_metadata": removed_dev_metadata,
    }
    if args.stage_tauri:
        (TAURI_BIN / "runtime_build.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
    size = sum(item.stat().st_size for item in source.rglob("*") if item.is_file())
    print(
        json.dumps(
            {
                "runtime": str(source),
                "staged": str(staged_executable) if staged_executable else None,
                "manifest": str(manifest_path),
                "size_bytes": size,
            }
        )
    )


if __name__ == "__main__":
    main()
