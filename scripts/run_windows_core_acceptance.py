"""Install and smoke-test a packaged Core candidate on a clean Windows runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CORE_NAMES = (
    "nvjitlink",
    "cublas",
    "cudnn",
    "cusparse",
    "cufft",
    "curand",
    "nvrtc",
    "torch_cuda",
)
PROCESS_NAMES = {"visionguard.exe", "visionguard-core-runtime.exe"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def powershell_version() -> str:
    """Return the runner PowerShell version without depending on the active shell."""
    for executable in ("pwsh", "powershell"):
        try:
            result = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "$PSVersionTable.PSVersion.ToString()",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        version = result.stdout.strip()
        if version:
            return version
    return "unavailable"


def forbidden_core_files(root: Path) -> list[str]:
    violations = []
    for path in root.rglob("*"):
        if path.is_file() and any(token in path.name.casefold() for token in FORBIDDEN_CORE_NAMES):
            violations.append(path.relative_to(root).as_posix())
    return violations


def running_product_processes() -> list[str]:
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], check=False, capture_output=True, text=True
    )
    if result.returncode:
        return ["TASKLIST_QUERY_FAILED"]
    rows = csv.reader(io.StringIO(result.stdout))
    return sorted({row[0] for row in rows if row and row[0].casefold() in PROCESS_NAMES})


def wait_removed(path: Path, timeout: float = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not path.exists():
            return True
        time.sleep(1)
    return not path.exists()


def product_shortcuts() -> dict[str, list[Path]]:
    desktop_root = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    start_root = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )
    return {
        "desktop": list(desktop_root.glob("VisionGuard*.lnk")) if desktop_root.is_dir() else [],
        "start_menu": list(start_root.rglob("VisionGuard*.lnk")) if start_root.is_dir() else [],
    }


def parse_smoke(stdout: str) -> dict:
    payloads = []
    for line in stdout.splitlines():
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    for payload in payloads:
        if {"live", "ready", "meta", "review"}.issubset(payload):
            return payload
    raise RuntimeError("packaged Core smoke did not emit its contract result")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--build-metadata", required=True, type=Path)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--install-dir", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "acceptance.log"
    evidence_path = output / "windows-core-acceptance.json"
    install_dir = (args.install_dir or output / "installed-app").resolve()
    installer = args.installer.resolve()
    metadata_path = args.build_metadata.resolve()
    build_metadata: dict[str, object] = {}
    checks: dict[str, object] = {}
    started = time.perf_counter()
    status, reason = "FAIL", "ACCEPTANCE_DID_NOT_COMPLETE"
    smoke: dict[str, object] = {}
    actual_hash = ""
    log_lines: list[str] = []

    def record(message: str) -> None:
        log_lines.append(message)
        print(message, flush=True)

    try:
        if platform.system() != "Windows" or platform.machine().lower() not in {
            "amd64",
            "x86_64",
        }:
            raise RuntimeError("Gate 1 requires an official 64-bit Windows runner")
        if not installer.is_file():
            raise FileNotFoundError(f"candidate installer is missing: {installer.name}")
        build_metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if build_metadata.get("schema_version") != 1:
            raise RuntimeError("unsupported Gate 1 build metadata schema")
        if build_metadata.get("installer_name") != installer.name:
            raise RuntimeError("candidate filename does not match build metadata")
        if build_metadata.get("git_sha") != args.git_sha:
            raise RuntimeError("candidate git SHA does not match acceptance run")
        if str(build_metadata.get("workflow_run_id")) != args.workflow_run_id:
            raise RuntimeError("candidate workflow run does not match acceptance run")
        actual_hash = sha256(installer)
        if actual_hash.casefold() != args.expected_sha256.casefold():
            raise RuntimeError("candidate installer SHA-256 mismatch")
        if actual_hash.casefold() != str(build_metadata.get("sha256", "")).casefold():
            raise RuntimeError("candidate SHA-256 does not match build metadata")
        checks["installer_sha256"] = True
        preexisting_processes = running_product_processes()
        preexisting_shortcuts = product_shortcuts()
        checks["visionguard_not_preinstalled"] = (
            not install_dir.exists()
            and not preexisting_processes
            and not preexisting_shortcuts["desktop"]
            and not preexisting_shortcuts["start_menu"]
        )
        if not checks["visionguard_not_preinstalled"]:
            raise RuntimeError("VisionGuard is already present on the clean acceptance runner")
        dev_paths = [
            ROOT / ".venv",
            ROOT / "desktop/node_modules",
            ROOT / "desktop/src-tauri/target",
            Path.home() / ".paddleocr",
            Path.home() / ".paddlex",
            Path.home() / ".cache/paddle",
        ]
        hf_cache = Path.home() / ".cache" / "huggingface"
        dev_paths.append(hf_cache)
        checks["no_project_development_cache"] = not any(path.exists() for path in dev_paths)
        if not checks["no_project_development_cache"]:
            raise RuntimeError("project development caches exist on the acceptance runner")
        record("Installing candidate silently")
        install_result = subprocess.run(
            [str(installer), "/S", f"/D={install_dir}"], check=False, timeout=300
        )
        checks["silent_install_exit_code"] = install_result.returncode
        if install_result.returncode:
            raise RuntimeError(f"silent installer exited with {install_result.returncode}")
        desktop = install_dir / "VisionGuard.exe"
        runtime_candidates = list(install_dir.rglob("visionguard-core-runtime.exe"))
        model_candidates = [
            path.parent
            for path in install_dir.rglob("manifest.json")
            if path.parent.name == "core-models"
        ]
        if not desktop.is_file() or len(runtime_candidates) != 1 or len(model_candidates) != 1:
            raise RuntimeError("installed Desktop/Core Runtime/Core Models layout is incomplete")
        checks["install_directory"] = install_dir.is_dir()
        checks["desktop_executable"] = True
        checks["core_runtime"] = True
        checks["core_models"] = True
        installed_shortcuts = product_shortcuts()
        checks["desktop_shortcut_created"] = bool(installed_shortcuts["desktop"])
        checks["start_menu_created"] = bool(installed_shortcuts["start_menu"])
        if not checks["start_menu_created"]:
            raise RuntimeError("installer did not create the expected Start Menu entry")
        violations = forbidden_core_files(install_dir)
        checks["forbidden_nvidia_binaries"] = violations
        if violations:
            raise RuntimeError(f"Core install contains forbidden CUDA/NVIDIA files: {violations}")
        smoke_dir = output / "core-smoke"
        smoke_command = [
            sys.executable,
            str(ROOT / "scripts/smoke_test_packaged_runtime.py"),
            "--runtime",
            str(runtime_candidates[0]),
            "--models",
            str(model_candidates[0]),
            "--work-dir",
            str(smoke_dir),
            "--image",
            str(ROOT / "data/vlm_eval/safe.png"),
            "--mode",
            "cascaded",
            "--runtime-edition",
            "cpu",
        ]
        result = subprocess.run(
            smoke_command, check=False, capture_output=True, text=True, timeout=360
        )
        log_lines.extend([result.stdout, result.stderr])
        if result.returncode:
            raise RuntimeError(f"packaged Core smoke exited with {result.returncode}")
        smoke = parse_smoke(result.stdout)
        checks["live"] = smoke["live"].get("status") == "ok"
        checks["ready"] = smoke["ready"].get("status") in {"ok", "ready"}
        checks["meta"] = bool(smoke["meta"].get("core_ready"))
        checks["fast_review"] = bool(smoke["review"].get("schema_valid"))
        if not all(checks[key] for key in ("live", "ready", "meta", "fast_review")):
            raise RuntimeError("Core health/meta/Fast Review contract failed")
        status, reason = "PASS", "ALL_REQUIRED_CORE_CHECKS_PASSED"
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        record(reason)
    finally:
        uninstallers = list(install_dir.glob("uninstall*.exe")) if install_dir.exists() else []
        if len(uninstallers) == 1:
            result = subprocess.run([str(uninstallers[0]), "/S"], check=False, timeout=180)
            checks["silent_uninstall_exit_code"] = result.returncode
            checks["install_directory_removed"] = wait_removed(install_dir)
        else:
            checks["silent_uninstall_exit_code"] = None
            checks["install_directory_removed"] = not install_dir.exists()
        time.sleep(2)
        orphans = running_product_processes()
        checks["orphan_processes"] = orphans
        remaining_shortcuts = product_shortcuts()
        checks["desktop_shortcut_removed"] = not remaining_shortcuts["desktop"]
        checks["start_menu_removed"] = not remaining_shortcuts["start_menu"]
        if status == "PASS" and (
            checks["silent_uninstall_exit_code"] != 0
            or not checks["install_directory_removed"]
            or orphans
            or not checks["desktop_shortcut_removed"]
            or not checks["start_menu_removed"]
        ):
            status, reason = "FAIL", "UNINSTALL_OR_ORPHAN_CHECK_FAILED"
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        evidence = {
            "schema_version": 1,
            "gate": "clean_core",
            "status": status,
            "reason": reason,
            "executed_at": datetime.now(UTC).isoformat(),
            "git_sha": args.git_sha,
            "workflow_run_id": args.workflow_run_id,
            "installer_name": installer.name,
            "installer_sha256": actual_hash,
            "runner": {
                "provider": "GitHub-hosted Windows runner",
                "os": os.environ.get("RUNNER_OS", platform.platform()),
                "architecture": platform.machine(),
                "powershell_version": powershell_version(),
            },
            "candidate": {
                "installer_name": installer.name,
                "sha256": actual_hash,
                "size_bytes": installer.stat().st_size if installer.is_file() else None,
                "build_metadata": build_metadata,
            },
            "checks": checks,
            "install": {
                "exit_code": checks.get("silent_install_exit_code"),
                "install_directory": checks.get("install_directory", False),
                "desktop_executable": checks.get("desktop_executable", False),
                "core_runtime": checks.get("core_runtime", False),
                "core_models": checks.get("core_models", False),
            },
            "live": smoke.get("live"),
            "ready": smoke.get("ready"),
            "meta": smoke.get("meta"),
            "fast_review": smoke.get("review"),
            "nvidia_binary_scan": {
                "scope": "VisionGuard install directory only",
                "violations": checks.get("forbidden_nvidia_binaries", []),
                "passed": checks.get("forbidden_nvidia_binaries") == [],
            },
            "uninstall": {
                "exit_code": checks.get("silent_uninstall_exit_code"),
                "install_directory_removed": checks.get("install_directory_removed", False),
                "desktop_shortcut_removed": checks.get("desktop_shortcut_removed", False),
                "start_menu_removed": checks.get("start_menu_removed", False),
                "user_data_policy": "AppData may be retained by product design",
            },
            "orphan_check": {
                "processes": orphans,
                "passed": not orphans,
            },
            "core": {
                "live": smoke.get("live"),
                "ready": smoke.get("ready"),
                "meta": smoke.get("meta"),
                "fast_review": smoke.get("review"),
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
