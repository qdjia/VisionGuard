"""Build and stage the PyInstaller one-folder runtime for Tauri Sidecar use."""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    if not args.no_clean:
        safe_clean(BUILD_ROOT)
        safe_clean(DIST_ROOT)
    build_environment = os.environ.copy()
    build_environment["YOLO_AUTOINSTALL"] = "false"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--workpath",
            str(BUILD_ROOT),
            "--distpath",
            str(DIST_ROOT),
            str(ROOT / "packaging" / "runtime" / "visionguard-runtime.spec"),
        ],
        cwd=ROOT,
        env=build_environment,
        check=True,
    )
    source = DIST_ROOT / "visionguard-runtime"
    executable = source / "visionguard-runtime.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller output missing: {executable}")
    triple = target_triple()
    TAURI_BIN.mkdir(parents=True, exist_ok=True)
    support = TAURI_BIN / "_internal"
    if support.exists():
        shutil.rmtree(support)
    internal = source / "_internal"
    if internal.is_dir():
        link_or_copy_tree(internal, support)
    staged_executable = TAURI_BIN / f"visionguard-runtime-{triple}.exe"
    staged_executable.unlink(missing_ok=True)
    link_or_copy(executable, staged_executable)
    metadata = {
        "runtime_version": "0.1.0",
        "python_version": platform.python_version(),
        "build_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "packager": "PyInstaller",
        "platform": platform.system(),
        "architecture": platform.machine(),
        "target_triple": triple,
    }
    (TAURI_BIN / "runtime_build.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    size = sum(item.stat().st_size for item in source.rglob("*") if item.is_file())
    print(
        json.dumps(
            {"runtime": str(source), "staged": str(staged_executable), "size_bytes": size}
        )
    )


if __name__ == "__main__":
    main()
