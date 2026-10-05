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
import tempfile
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
FORBIDDEN_ONLINE_ASSET_NAMES = (
    "nvjitlink",
    "cublas",
    "cudnn",
    "cusparse",
    "cufft",
    "curand",
    "nvrtc",
    "torch_cuda",
)
FINAL_RC_ACCEPTANCE_GATES = {
    "advanced_ai_gpu",
    "clean_core",
    "fresh_user_gui",
    "overall_clean_environment",
    "reinstall",
    "rollback",
    "uninstall",
    "upgrade",
}
PRIVATE_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")


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


def source_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def assert_clean_source_tree() -> None:
    changed = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    if changed:
        raise RuntimeError("final RC requires a clean tracked source tree")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def redact_private_paths(value: object) -> object:
    """Remove machine-local absolute paths from distributable evidence."""
    if isinstance(value, dict):
        return {key: redact_private_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_private_paths(item) for item in value]
    if isinstance(value, str) and PRIVATE_ABSOLUTE_PATH.search(value):
        return "<redacted-local-path>"
    return value


def copy_release_evidence(source: Path, target: Path) -> None:
    """Copy evidence while keeping private workstation paths out of release assets."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.casefold() != ".json":
        shutil.copy2(source, target)
        return
    payload = json.loads(source.read_text(encoding="utf-8"))
    target.write_text(
        json.dumps(redact_private_paths(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def derive_final_rc_gates(evidence_root: Path) -> tuple[dict[str, str], list[str]]:
    acceptance = load_json(evidence_root / "acceptance-status.json")
    acceptance_gates = acceptance.get("gates", {})
    gates = {
        "asset_hosting": "passed",
        "detector_license": "passed",
        "local_inference": "passed",
        "license_distribution": "passed",
        "native_redistribution": "passed",
        "paddle_evidence": "passed",
        "qwen_evidence": "passed",
        "sbom": "passed",
    }
    blockers: list[str] = []
    for name in sorted(FINAL_RC_ACCEPTANCE_GATES):
        status = str(acceptance_gates.get(name, {}).get("status", "MISSING")).upper()
        gates[name] = "passed" if status == "PASS" else "blocked"
        if status != "PASS":
            blockers.append(f"{name.upper()}_{status}")

    historical = load_json(evidence_root / "historical-regression.json")
    historical_status = str(historical.get("gate_status", "MISSING")).upper()
    if historical_status == "PASS":
        gates["historical_regression"] = "passed"
    elif historical_status == "PASS_WITH_LIMITATION":
        gates["historical_regression"] = "passed_with_limitation"
    else:
        gates["historical_regression"] = "blocked"
        blockers.append(f"HISTORICAL_REGRESSION_{historical_status}")

    detector = load_json(evidence_root / "detector-provenance.json")
    if detector.get("redistribution_status") != "ALLOWED_WITH_CONDITIONS":
        gates["detector_license"] = "blocked"
        blockers.append("DETECTOR_REDISTRIBUTION_NOT_CLEARED")

    local_inference = load_json(evidence_root / "local-inference-architecture.json")
    if local_inference.get("status") != "PASS":
        gates["local_inference"] = "blocked"
        blockers.append("LOCAL_INFERENCE_NOT_PASSED")

    migration = load_json(evidence_root / "license-migration.json")
    if migration.get("current_project_license") != "AGPL-3.0-only":
        gates["license_distribution"] = "blocked"
        blockers.append("PROJECT_LICENSE_ALIGNMENT_NOT_PASSED")
    return gates, blockers


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, env=env)


def replace_directory(staged: Path, target: Path, *, allowed_parent: Path) -> None:
    staged = staged.resolve()
    target = target.resolve()
    allowed_parent = allowed_parent.resolve()
    if staged.parent != allowed_parent or target.parent != allowed_parent:
        raise ValueError("refusing to replace a directory outside the allowed parent")
    if not staged.is_dir():
        raise FileNotFoundError(f"staged directory is missing: {staged}")
    backup = allowed_parent / f".{target.name}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        target.replace(backup)
    try:
        staged.replace(target)
    except BaseException:
        if backup.exists() and not target.exists():
            backup.replace(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def rebuild_final_core_models(core_models: Path) -> None:
    models_root = (ROOT / "models").resolve()
    staged = models_root / ".core-models-v1-final-rc-staging"
    if staged.exists():
        if staged.parent != models_root:
            raise ValueError("unexpected Core Models staging path")
        shutil.rmtree(staged)
    run(
        [
            sys.executable,
            "scripts/prepare_gate1_core_models.py",
            "--output",
            str(staged),
            "--work-root",
            str(ROOT / "artifacts/final-rc-core-model-build"),
            "--isolated-training",
        ]
    )
    manifest = load_json(staged / "manifest.json")
    expected = {"baseline", "detector", "ocr_detection", "ocr_orientation", "ocr_recognition"}
    if set(manifest.get("models", {})) != expected:
        raise RuntimeError("rebuilt final RC Core Models have an unexpected component set")
    replace_directory(staged, core_models, allowed_parent=models_root)


def safe_clean(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != RELEASE_ROOT.resolve():
        raise ValueError(f"refusing to clean unexpected release directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def assert_online_bootstrap_hygiene(*roots: Path) -> None:
    violations = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lowered = path.name.casefold()
            suffix = path.suffix.casefold()
            forbidden_native = suffix in {".dll", ".dylib", ".pyd", ".so"} and any(
                token in lowered for token in FORBIDDEN_ONLINE_ASSET_NAMES
            )
            forbidden_model_or_wheel = (
                suffix in {".whl", ".safetensors", ".gguf"}
                and "visionguard_moderation" not in lowered
            )
            if forbidden_native or forbidden_model_or_wheel:
                violations.append(path)
    if violations:
        rendered = ", ".join(str(path) for path in violations[:10])
        raise RuntimeError(
            f"online-bootstrap release contains forbidden Advanced AI assets: {rendered}"
        )


def build_bootstrap_wheel() -> Path:
    target = ROOT / "bootstrap-dist"
    target.mkdir(exist_ok=True)
    for existing in target.glob("*.whl"):
        existing.unlink()
    bootstrap_project = ROOT / "packaging" / "bootstrap" / "pyproject.toml"
    # Keep pip's deeply nested ephemeral wheel paths out of the repository.
    # A long checkout path can otherwise exceed Windows path limits and make
    # setuptools report a misleading missing-file error for the final wheel.
    with tempfile.TemporaryDirectory(prefix="vg-wheel-") as temporary:
        build_root = Path(temporary)
        build_temp = build_root / "tmp"
        build_temp.mkdir()
        build_env = os.environ.copy()
        build_env.update(
            {"TEMP": str(build_temp), "TMP": str(build_temp), "TMPDIR": str(build_temp)}
        )
        shutil.copy2(bootstrap_project, build_root / "pyproject.toml")
        shutil.copytree(ROOT / "src" / "visionguard", build_root / "src" / "visionguard")
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--ignore-requires-python",
                "--wheel-dir",
                str(target),
            ],
            cwd=build_root,
            env=build_env,
        )
    wheels = list(target.glob("visionguard_moderation-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("expected exactly one VisionGuard bootstrap wheel")
    return wheels[0]


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


def write_release_notes(
    output: Path,
    version: str,
    blockers: list[str],
    *,
    final_rc: bool = False,
    limitations: list[str] | None = None,
) -> Path:
    target = output / "RELEASE_NOTES.md"
    blocker_text = (
        "\n".join(f"- `{blocker}`" for blocker in blockers)
        if blockers
        else "- None recorded for this RC candidate."
    )
    limitation_text = "\n".join(f"- {limitation}" for limitation in limitations or []) or "- None."
    candidate_status = (
        "严格 RC 候选；仍须完成候选级 CI smoke 后才能创建 Tag 或公开上传。"
        if final_rc
        else "本地生成的候选产物，不表示已经获准公开发布。"
    )
    target.write_text(
        f"""# VisionGuard {version} Local Release Candidate

{candidate_status}

## Distribution model

- VisionGuard 自有代码采用 AGPL-3.0-only。
- 安装、组件/模型获取和更新可以联网。
- 图片审核推理在本地完成，不依赖云端推理 API。
- Real Offline 不是 v1.0 产品要求或 RC gate。

## Blocking gates

{blocker_text}

## Accepted limitations

{limitation_text}

公开分发前必须完成 `docs/release_gate.md` 所列门禁并让严格 validator 无绕过通过。
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
    parser.add_argument(
        "--advanced-ai-mode",
        choices=("online-bootstrap", "bundled"),
        default="online-bootstrap",
        help="Default is small official-source bootstrap; bundled is legacy fallback only.",
    )
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument(
        "--final-rc",
        action="store_true",
        help="Rebuild an evidence-backed RC from a clean committed source tree.",
    )
    args = parser.parse_args()
    if not SEMVER.fullmatch(args.version):
        raise ValueError("--version must be a SemVer value")
    app_version = source_version()
    if args.version.split("-", maxsplit=1)[0] != app_version:
        raise ValueError(
            f"release base version {args.version} does not match app version {app_version}"
        )
    if args.final_rc:
        if not re.fullmatch(r"1\.0\.0-rc\.[1-9][0-9]*", args.version):
            raise ValueError("--final-rc requires version 1.0.0-rc.N")
        if args.advanced_ai_mode != "online-bootstrap":
            raise ValueError("--final-rc only supports online-bootstrap distribution")
        if args.skip_build or args.no_clean or args.skip_advanced_ai or args.skip_validation:
            raise ValueError(
                "--final-rc forbids --skip-build, --no-clean, --skip-advanced-ai, "
                "and --skip-validation"
            )
        assert_clean_source_tree()

    output = RELEASE_ROOT / f"v{args.version}"
    RELEASE_ROOT.mkdir(exist_ok=True)
    if not args.no_clean:
        safe_clean(output)
    output.mkdir(parents=True, exist_ok=True)

    core_runtime = ROOT / "runtime-dist-core/visionguard-core-runtime"
    core_models = ROOT / "models/core-models-v1"
    if not args.skip_build:
        if args.advanced_ai_mode == "online-bootstrap" and not args.skip_advanced_ai:
            build_bootstrap_wheel()
            assert_online_bootstrap_hygiene(ROOT / "bootstrap-dist", ROOT / "packaging/bootstrap")
        run([sys.executable, "scripts/build_runtime.py", "--profile", "core"])
        if args.final_rc:
            rebuild_final_core_models(core_models)
        elif not core_models.joinpath("manifest.json").is_file():
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
        if args.advanced_ai_mode == "online-bootstrap":
            assert_online_bootstrap_hygiene(core_runtime, core_models)
        run(["npm.cmd", "run", "tauri:build:release"], cwd=DESKTOP)
    if not core_runtime.joinpath("runtime-manifest.json").is_file():
        raise FileNotFoundError("Core Runtime is missing")
    if not core_models.joinpath("manifest.json").is_file():
        raise FileNotFoundError("Core Models are missing")

    assets: list[dict[str, object]] = []
    installer = output / f"VisionGuard-Setup-{args.version}.exe"
    shutil.copy2(find_installer(), installer)
    # Only the strict final-RC path may mark the rebuilt installer publishable.
    assets.append(
        asset_record(
            installer,
            output,
            kind="windows_installer",
            publishable=args.final_rc,
        )
    )

    advanced_manifest: str | None = None
    if not args.skip_advanced_ai and args.advanced_ai_mode == "bundled":
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
    sbom_paths = generate_sbom(
        output / "sbom",
        args.version,
        webview_installer,
        include_legacy_vlm=args.advanced_ai_mode == "bundled",
    )
    if args.final_rc:
        gates, blockers = derive_final_rc_gates(ROOT / "release-evidence")
    else:
        blockers = [
            "CLEAN_CORE_ACCEPTANCE_PENDING",
            "FRESH_USER_GUI_ACCEPTANCE_PENDING",
            "ADVANCED_AI_GPU_ACCEPTANCE_PENDING",
            "HISTORICAL_REGRESSION_PENDING",
        ]
        gates = {
            "advanced_ai_gpu": "pending_manual",
            "asset_hosting": "passed",
            "clean_core": "pending",
            "detector_license": "passed",
            "fresh_user_gui": "pending_manual",
            "local_inference": "passed",
            "overall_clean_environment": "pending",
            "upgrade": "pending_manual",
            "rollback": "pending_manual",
            "uninstall": "pending_manual",
            "reinstall": "pending_manual",
            "historical_regression": "pending",
            "license_distribution": "blocked",
            "native_redistribution": "passed",
            "paddle_evidence": "passed",
            "qwen_evidence": "passed",
            "sbom": "passed",
        }
    limitations = (
        load_json(ROOT / "release-evidence/historical-regression.json").get("limitations", [])
        if args.final_rc
        else []
    )
    notes = write_release_notes(
        output,
        args.version,
        blockers,
        final_rc=args.final_rc,
        limitations=limitations,
    )
    notice = output / "THIRD_PARTY_NOTICES.md"
    license_report = output / "release_licenses.md"
    detector_provenance = output / "detector_provenance.md"
    project_license = output / "LICENSE"
    project_notice = output / "NOTICE"
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", notice)
    shutil.copy2(ROOT / "docs/release_licenses.md", license_report)
    shutil.copy2(ROOT / "docs/detector_provenance.md", detector_provenance)
    shutil.copy2(ROOT / "LICENSE", project_license)
    shutil.copy2(ROOT / "NOTICE", project_notice)
    evidence_sources = [
        ROOT / "release-evidence/model-provenance.json",
        ROOT / "release-evidence/native-nvidia-inventory.json",
        ROOT / "release-evidence/runtime-provenance.json",
        ROOT / "release-evidence/detector-provenance.json",
        ROOT / "release-evidence/nvjitlink-analysis.json",
        ROOT / "release-evidence/acceptance-status.json",
        ROOT / "release-evidence/historical-regression.json",
        ROOT / "release-evidence/stable-release-risk-waiver.json",
        ROOT / "release-evidence/local-inference-architecture.json",
        ROOT / "release-evidence/license-migration.json",
        ROOT / "release-evidence/advanced-ai-bootstrap.json",
        ROOT / "release-evidence/windows-core-acceptance.json",
        ROOT / "release-evidence/fresh-user-gui.json",
        ROOT / "release-evidence/advanced-ai-gpu-acceptance.json",
        ROOT / "release-evidence/windows-acceptance-summary.json",
        ROOT / "release-evidence/upgrade-rollback-acceptance.json",
        ROOT / "release-evidence/licenses/APACHE-2.0.txt",
        ROOT / "release-evidence/model-cards/Qwen3-VL-2B-Instruct.md",
    ]
    evidence_paths = []
    for source in evidence_sources:
        relative = source.relative_to(ROOT)
        target = output / relative
        copy_release_evidence(source, target)
        evidence_paths.append(target)
    manifest = {
        "schema_version": 4,
        "release_version": args.version,
        "project_license": "AGPL-3.0-only",
        "source": {"commit": source_commit(), "expected_tag": f"v{args.version}"},
        "release_channel": "release_candidate",
        "generated_at": datetime.now(UTC).isoformat(),
        "app_version": app_version,
        "platform": "windows",
        "architecture": "x86_64",
        "edition": "bundled_cpu_core_optional_advanced_ai_online_bootstrap",
        "components": {
            "desktop": {"version": app_version, "required": True},
            "core_runtime": {"version": args.runtime_version, "required": True},
            "core_models": {"version": "core-models-v1", "required": True},
            "advanced_ai_bootstrap": {
                "version": args.advanced_version,
                "required": False,
                "mode": args.advanced_ai_mode,
            },
        },
        "sizes": {
            "installer_bytes": installer.stat().st_size,
            "core_runtime_installed_bytes": directory_size(core_runtime),
            "core_models_installed_bytes": directory_size(core_models),
        },
        "distribution": {
            "installer": "nsis_current_user_bundled_cpu_core",
            "advanced_ai": args.advanced_ai_mode,
            "advanced_ai_manifest": advanced_manifest,
            "bootstrap_manifest": "embedded:bootstrap/advanced-ai-bootstrap-manifest.json",
            "network_assisted_installation": True,
            "local_inference": True,
            "cloud_inference": False,
            "code_signing": "unsigned",
            "public_release_ready": args.final_rc and not blockers,
            "blockers": blockers,
        },
        "gates": gates,
        "assets": assets,
        "metadata_files": [
            "SHA256SUMS.txt",
            notes.name,
            notice.name,
            license_report.name,
            detector_provenance.name,
            project_license.name,
            project_notice.name,
        ]
        + [path.relative_to(output).as_posix() for path in sbom_paths]
        + [path.relative_to(output).as_posix() for path in evidence_paths],
    }
    manifest_path = output / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksum_paths = [output / str(asset["name"]) for asset in assets]
    checksum_paths.extend(
        [
            notes,
            notice,
            license_report,
            detector_provenance,
            project_license,
            project_notice,
            manifest_path,
            *sbom_paths,
            *evidence_paths,
        ]
    )
    write_checksums(output, checksum_paths)
    if args.advanced_ai_mode == "online-bootstrap":
        assert_online_bootstrap_hygiene(output)
    if not args.skip_validation:
        validation = [sys.executable, "scripts/validate_release.py", str(output)]
        if args.final_rc:
            validation.append("--rc")
        run(validation)
    print(json.dumps({"release": str(output), "assets": len(assets)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
