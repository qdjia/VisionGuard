"""Build a reproducible local Windows release candidate without publishing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from scripts.build_advanced_ai_package import build_package
    from scripts.generate_sbom import generate as generate_sbom
else:
    from build_advanced_ai_package import build_package
    from generate_sbom import generate as generate_sbom

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
TAURI = DESKTOP / "src-tauri"
RELEASE_ROOT = ROOT / "release"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
GITHUB_ASSET_LIMIT = 2 * 1024**3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def source_version() -> str:
    return str(json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))["version"])


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def safe_clean(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != RELEASE_ROOT.resolve():
        raise ValueError(f"refusing to clean unexpected release directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def find_installer() -> Path:
    candidates = sorted(
        (TAURI / "target/release/bundle/nsis").glob("*.exe"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Tauri NSIS installer was not produced")
    return candidates[0]


def find_webview_installer() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    candidates = sorted(
        Path(local_app_data).glob("tauri/x64/*/MicrosoftEdgeWebView2RuntimeInstallerX64.exe"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def asset_record(path: Path, output: Path, *, kind: str, publishable: bool) -> dict[str, object]:
    size = path.stat().st_size
    return {
        "name": path.relative_to(output).as_posix(),
        "kind": kind,
        "size_bytes": size,
        "sha256": sha256(path),
        "github_asset_compatible": size < GITHUB_ASSET_LIMIT,
        "publishable": publishable,
    }


def write_checksums(output: Path, paths: list[Path]) -> Path:
    target = output / "SHA256SUMS.txt"
    target.write_text(
        "\n".join(
            f"{sha256(path)}  {path.relative_to(output).as_posix()}"
            for path in sorted(paths, key=lambda item: item.relative_to(output).as_posix())
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def write_release_notes(output: Path, version: str, blockers: list[str]) -> Path:
    target = output / "RELEASE_NOTES.md"
    blocker_text = "\n".join(f"- `{blocker}`" for blocker in blockers)
    target.write_text(
        f"""# VisionGuard {version} Local Release Candidate

这是本地生成的候选产物，不代表已经获准公开发布。

## Highlights

- 安装器内置 Slim CPU Core Runtime 与 Core Models，Fast Review 可离线使用。
- Advanced AI 使用 1 GiB 分卷、SHA-256、磁盘预检、staging 与原子激活。
- VLM Runtime / Models 独立版本，可回滚和卸载；Core 保持可用。

## Installation

安装 Core 后，在应用内选择 `advanced-ai-manifest.json` 导入可选 Advanced AI。
用户不需要手工合并分卷。

## Validated hardware

RTX 4060 Laptop 8 GiB 是开发验证配置，不是最低要求。最低 RAM / VRAM 尚未充分刻画。

## Signing

当前候选未配置 Authenticode，Windows SmartScreen 可能显示警告。

## Blocking gates

{blocker_text}

公开分发前必须完成 `docs/release_gate.md` 和 clean-machine 验收。
""",
        encoding="utf-8",
        newline="\n",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--skip-build", action="store_true", help="Reuse existing local binaries")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument(
        "--advanced-runtime", type=Path, default=ROOT / "runtime-dist-vlm/visionguard-vlm-runtime"
    )
    parser.add_argument("--advanced-models", type=Path, default=ROOT / "models/vlm-models-v1")
    parser.add_argument("--advanced-version", default="advanced-ai-v1")
    parser.add_argument("--runtime-version", default="0.1.0")
    parser.add_argument("--model-version", default="vlm-models-v1")
    parser.add_argument("--part-size-mib", type=int, default=1024)
    parser.add_argument("--skip-advanced-ai", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    if not SEMVER.fullmatch(args.version):
        raise ValueError("--version must be a SemVer value")
    app_version = source_version()
    if args.version.split("-", maxsplit=1)[0] != app_version:
        raise ValueError(
            f"release base version {args.version} does not match app version {app_version}"
        )

    output = RELEASE_ROOT / f"v{args.version}"
    RELEASE_ROOT.mkdir(exist_ok=True)
    if not args.no_clean:
        safe_clean(output)
    output.mkdir(parents=True, exist_ok=True)

    core_runtime = ROOT / "runtime-dist-core/visionguard-core-runtime"
    core_models = ROOT / "models/core-models-v1"
    if not args.skip_build:
        run([sys.executable, "scripts/build_runtime.py", "--profile", "core"])
        if not core_models.joinpath("manifest.json").is_file():
            run(
                [
                    sys.executable,
                    "scripts/build_model_bundle.py",
                    "--profile",
                    "core",
                    "--bundle-version",
                    "core-models-v1",
                    "--output",
                    str(core_models),
                    "--hardlink",
                ]
            )
        run(["npm.cmd", "run", "tauri:build:release"], cwd=DESKTOP)
    if not core_runtime.joinpath("runtime-manifest.json").is_file():
        raise FileNotFoundError("Core Runtime is missing")
    if not core_models.joinpath("manifest.json").is_file():
        raise FileNotFoundError("Core Models are missing")

    assets: list[dict[str, object]] = []
    installer = output / f"VisionGuard-Setup-{args.version}.exe"
    shutil.copy2(find_installer(), installer)
    # Public flag remains false until detector/native redistribution gates are cleared.
    assets.append(asset_record(installer, output, kind="windows_installer", publishable=False))

    advanced_manifest: str | None = None
    if not args.skip_advanced_ai:
        advanced_path = build_package(
            runtime=args.advanced_runtime,
            models=args.advanced_models,
            output=output,
            package_version=args.advanced_version,
            runtime_version=args.runtime_version,
            model_version=args.model_version,
            part_size_mib=args.part_size_mib,
        )
        advanced_manifest = advanced_path.name
        assets.append(
            asset_record(advanced_path, output, kind="advanced_ai_manifest", publishable=False)
        )
        for part in sorted(output.glob("*.part[0-9][0-9]")):
            kind = "vlm_runtime_part" if "VLM-Runtime" in part.name else "vlm_models_part"
            assets.append(asset_record(part, output, kind=kind, publishable=False))

    webview_installer = find_webview_installer()
    sbom_paths = generate_sbom(output / "sbom", args.version, webview_installer)
    blockers = [
        "DETECTOR_REDISTRIBUTION_UNRESOLVED",
        "NVIDIA_NATIVE_REDISTRIBUTION_UNVERIFIED",
        "CLEAN_MACHINE_ACCEPTANCE_PENDING",
        "HISTORICAL_REGRESSION_PENDING",
    ]
    notes = write_release_notes(output, args.version, blockers)
    notice = output / "THIRD_PARTY_NOTICES.md"
    license_report = output / "release_licenses.md"
    detector_provenance = output / "detector_provenance.md"
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", notice)
    shutil.copy2(ROOT / "docs/release_licenses.md", license_report)
    shutil.copy2(ROOT / "docs/detector_provenance.md", detector_provenance)
    manifest = {
        "schema_version": 3,
        "release_version": args.version,
        "release_channel": "release_candidate",
        "generated_at": datetime.now(UTC).isoformat(),
        "app_version": app_version,
        "platform": "windows",
        "architecture": "x86_64",
        "edition": "bundled_cpu_core_optional_advanced_ai",
        "components": {
            "desktop": {"version": app_version, "required": True},
            "core_runtime": {"version": args.runtime_version, "required": True},
            "core_models": {"version": "core-models-v1", "required": True},
            "vlm_runtime": {"version": args.runtime_version, "required": False},
            "vlm_models": {"version": args.model_version, "required": False},
        },
        "sizes": {
            "installer_bytes": installer.stat().st_size,
            "core_runtime_installed_bytes": directory_size(core_runtime),
            "core_models_installed_bytes": directory_size(core_models),
        },
        "distribution": {
            "installer": "nsis_current_user_bundled_cpu_core",
            "advanced_ai": "local_manifest_import_split_parts",
            "advanced_ai_manifest": advanced_manifest,
            "offline_inference": True,
            "code_signing": "unsigned",
            "public_release_ready": False,
            "blockers": blockers,
        },
        "gates": {
            "advanced_ai_install": "pending_manual",
            "clean_machine": "pending",
            "offline": "pending_clean_machine",
            "upgrade": "pending_manual",
            "uninstall": "pending_manual",
            "historical_regression": "pending",
            "license_distribution": "blocked",
        },
        "assets": assets,
        "metadata_files": [
            "SHA256SUMS.txt",
            notes.name,
            notice.name,
            license_report.name,
            detector_provenance.name,
        ]
        + [path.relative_to(output).as_posix() for path in sbom_paths],
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksum_paths = [output / str(asset["name"]) for asset in assets]
    checksum_paths.extend(
        [notes, notice, license_report, detector_provenance, manifest_path, *sbom_paths]
    )
    write_checksums(output, checksum_paths)
    if not args.skip_validation:
        run([sys.executable, "scripts/validate_release.py", str(output)])
    print(json.dumps({"release": str(output), "assets": len(assets)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
