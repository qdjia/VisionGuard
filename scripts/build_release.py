"""Build a local Windows release candidate and generate verifiable release metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
TAURI = DESKTOP / "src-tauri"
RELEASE_ROOT = ROOT / "release"
MODEL_ROOT = ROOT / "models" / "models-v1"
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
    payload = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    return str(payload["version"])


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
        (TAURI / "target" / "release" / "bundle" / "nsis").glob("*.exe"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Tauri NSIS installer was not produced")
    return candidates[0]


def package_models(output: Path) -> tuple[Path, str, int]:
    manifest_path = MODEL_ROOT / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "models/models-v1 is missing; run scripts/build_model_bundle.py first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_version = str(manifest["bundle_version"])
    public_name = bundle_version.replace("models", "Models", 1)
    archive = output / f"VisionGuard-{public_name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as target:
        for item in sorted(MODEL_ROOT.rglob("*")):
            if item.is_file():
                target.write(item, Path(bundle_version) / item.relative_to(MODEL_ROOT))
    return archive, bundle_version, directory_size(MODEL_ROOT)


def package_runtime(output: Path) -> tuple[Path, str, int]:
    runtime_root = ROOT / "runtime-dist" / "visionguard-runtime"
    manifest_path = runtime_root / "runtime-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("runtime manifest is missing; run scripts/build_runtime.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest["runtime_version"])
    directory_name = f"runtime-v{version}"
    archive = output / f"VisionGuard-Runtime-GPU-{version}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as target:
        for item in sorted(runtime_root.rglob("*")):
            if item.is_file():
                target.write(item, Path(directory_name) / item.relative_to(runtime_root))
    return archive, version, directory_size(runtime_root)


def asset_record(path: Path, *, kind: str, publishable: bool) -> dict[str, object]:
    size = path.stat().st_size
    return {
        "name": path.name,
        "kind": kind,
        "size_bytes": size,
        "sha256": sha256(path),
        "github_asset_compatible": size < GITHUB_ASSET_LIMIT,
        "publishable": publishable,
    }


def write_checksums(output: Path, assets: list[dict[str, object]]) -> Path:
    target = output / "SHA256SUMS.txt"
    lines = [f"{asset['sha256']}  {asset['name']}" for asset in assets]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return target


def write_release_notes(output: Path, version: str, assets: list[dict[str, object]]) -> Path:
    target = output / "RELEASE_NOTES.md"
    table = "\n".join(
        f"| `{asset['name']}` | {asset['size_bytes']} | {'是' if asset['publishable'] else '否'} |"
        for asset in assets
    )
    target.write_text(
        f"""# VisionGuard {version} Release Candidate

这是本地生成的 Windows GPU 版候选发布物，不代表已经获准公开发布。

## 安装

1. 下载并校验安装器与模型包。
2. 运行 `VisionGuard-Setup-GPU-{version}.exe`。
3. 首次启动时先选择 GPU Runtime ZIP 或已解压目录。
4. Runtime 安装完成后选择模型 ZIP 或已解压模型目录。
5. 等待本机 SHA-256 校验与 AI Runtime 就绪。

## 发布物

| 文件 | 字节数 | 当前允许公开上传 |
|---|---:|---|
{table}

## 已知发布门禁

- Ultralytics/YOLO 代码与权重的公开再分发方式尚未解决，模型资产不得上传。
- 超过 2 GiB 的文件不能作为单个 GitHub Release asset 上传。
- 尚需完成代码签名、Windows Sandbox/干净 VM、卸载、重装和升级人工验收。
- GPU 最低显存和整机内存要求尚未形成足量实测结论；不要把当前测试机配置写成最低要求。

详情见 `docs/distribution_architecture.md` 与 `docs/model_distribution_licenses.md`。
""",
        encoding="utf-8",
        newline="\n",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release SemVer, for example 0.1.0-rc.1")
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--no-clean", action="store_true")
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

    if not args.skip_runtime:
        run([sys.executable, "scripts/build_runtime.py"])
    if not args.skip_installer:
        run(["npm.cmd", "run", "tauri:build:release"], cwd=DESKTOP)

    assets: list[dict[str, object]] = []
    installer_source = find_installer()
    installer = output / f"VisionGuard-Setup-GPU-{args.version}.exe"
    shutil.copy2(installer_source, installer)
    assets.append(asset_record(installer, kind="windows_gpu_installer", publishable=True))

    runtime_archive, runtime_version, unpacked_runtime_size = package_runtime(output)
    assets.append(
        asset_record(
            runtime_archive,
            kind="windows_gpu_runtime",
            publishable=False,
        )
    )

    model_version: str | None = None
    unpacked_model_size: int | None = None
    if not args.skip_models:
        model_archive, model_version, unpacked_model_size = package_models(output)
        assets.append(
            asset_record(
                model_archive,
                kind="model_bundle",
                # Local packaging is permitted for verification; public redistribution is blocked.
                publishable=False,
            )
        )

    packaged_bytes = sum(int(asset["size_bytes"]) for asset in assets)
    app_binary = TAURI / "target" / "release" / "visionguard-desktop.exe"
    app_binary_bytes = app_binary.stat().st_size if app_binary.is_file() else None
    installed_total_bytes = (
        (app_binary_bytes or 0) + unpacked_runtime_size + (unpacked_model_size or 0)
    )
    recommended_install_disk_bytes = (packaged_bytes + installed_total_bytes) * 115 // 100

    checksums = write_checksums(output, assets)
    notes = write_release_notes(output, args.version, assets)
    manifest = {
        "schema_version": 1,
        "release_version": args.version,
        "release_channel": "release_candidate",
        "generated_at": datetime.now(UTC).isoformat(),
        "app_version": app_version,
        "runtime_version": runtime_version,
        "model_bundle_version": model_version,
        "pipeline_version": "v2",
        "routing_version": "v1",
        "fusion_version": "v1",
        "prompt_version": "v1",
        "platform": "windows",
        "architecture": "x86_64",
        "edition": "gpu",
        "distribution": {
            "installer": "thin_nsis_current_user",
            "runtime": "separate_local_import",
            "models": "separate_local_import",
            "offline_inference": True,
            "public_release_ready": False,
            "blockers": [
                "ULTRALYTICS_REDISTRIBUTION_UNRESOLVED",
                "NVIDIA_CUDA_REDISTRIBUTION_UNVERIFIED",
                "CODE_SIGNING_NOT_CONFIGURED",
                "CLEAN_MACHINE_ACCEPTANCE_PENDING",
            ],
        },
        "minimum_requirements": {
            "os": "64-bit Windows",
            "gpu": "NVIDIA GPU with a driver compatible with bundled CUDA PyTorch",
            "vram_bytes": None,
            "system_memory_bytes": None,
            "disk_free_bytes": recommended_install_disk_bytes,
            "note": (
                "Disk value includes downloaded assets, installed components, and a 15% "
                "safety margin. Minimum RAM/VRAM still requires repeated hardware testing."
            ),
        },
        "sizes": {
            "runtime_bytes": unpacked_runtime_size,
            "model_unpacked_bytes": unpacked_model_size,
            "installer_bytes": installer.stat().st_size,
            "desktop_binary_bytes": app_binary_bytes,
            "installed_total_bytes": installed_total_bytes,
            "packaged_assets_total_bytes": packaged_bytes,
            "recommended_install_disk_bytes": recommended_install_disk_bytes,
        },
        "assets": assets
        + [
            {"name": checksums.name, "kind": "checksums"},
            {"name": notes.name, "kind": "release_notes"},
        ],
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not args.skip_validation:
        run([sys.executable, "scripts/validate_release.py", str(output)])
    print(json.dumps({"release": str(output), "assets": len(assets)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
