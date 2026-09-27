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
PROCESS_NAMES = {
    "visionguard.exe",
    "visionguard-desktop.exe",
    "visionguard-core-runtime.exe",
}
EXPECTED_MODEL_ROLES = {
    "baseline",
    "detector",
    "ocr_detection",
    "ocr_orientation",
    "ocr_recognition",
}
PACKAGED_RUNTIME_CONFIGS = (
    "api.yaml",
    "classes.yaml",
    "detector.yaml",
    "fusion.yaml",
    "moderation_policy.yaml",
    "ocr.yaml",
    "pipeline.yaml",
    "pipeline_cascaded.yaml",
    "routing.yaml",
    "vlm.yaml",
)
INSTALL_LAYOUT = (
    (
        ("desktop_executable", "visionguard-desktop.exe", "file"),
        ("core_runtime_directory", "components/core-runtime", "directory"),
        (
            "core_runtime_executable",
            "components/core-runtime/visionguard-core-runtime.exe",
            "file",
        ),
        ("core_runtime_manifest", "components/core-runtime/runtime-manifest.json", "file"),
    )
    + tuple(
        (
            f"core_runtime_config_{Path(name).stem}",
            f"components/core-runtime/_internal/resources/configs/{name}",
            "file",
        )
        for name in PACKAGED_RUNTIME_CONFIGS
    )
    + (
        ("core_models_directory", "components/core-models", "directory"),
        ("core_models_manifest", "components/core-models/manifest.json", "file"),
    )
)


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
        relative = path.relative_to(root).as_posix().casefold()
        name = path.name.casefold()
        is_advanced_ai_payload = (
            "components/vlm-runtime" in relative
            or "components/vlm-models" in relative
            or "qwen" in name
            or name == "visionguard-vlm-runtime.exe"
            or path.suffix.casefold() in {".gguf", ".safetensors"}
        )
        if path.is_file() and (
            any(token in name for token in FORBIDDEN_CORE_NAMES) or is_advanced_ai_payload
        ):
            violations.append(path.relative_to(root).as_posix())
    return sorted(violations)


def _safe_manifest_path(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    candidate = Path(relative.replace("/", os.sep))
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def inspect_installed_layout(root: Path) -> dict[str, list[dict[str, object]] | list[str]]:
    """Describe the official installed layout without leaking the absolute runner path."""
    expected: list[dict[str, object]] = []
    observed: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    errors: list[str] = []

    def inspect(role: str, relative: str, kind: str) -> None:
        item = {"role": role, "path": relative, "kind": kind}
        expected.append(item)
        path = root / Path(relative.replace("/", os.sep))
        exists = path.is_file() if kind == "file" else path.is_dir()
        if exists:
            observed_item = dict(item)
            if kind == "file":
                observed_item["size_bytes"] = path.stat().st_size
            observed.append(observed_item)
        else:
            missing.append(item)

    for role, relative, kind in INSTALL_LAYOUT:
        inspect(role, relative, kind)

    runtime_manifest_path = root / "components/core-runtime/runtime-manifest.json"
    if runtime_manifest_path.is_file():
        try:
            runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
            if runtime_manifest.get("component") != "core":
                errors.append("Core Runtime manifest component is not 'core'")
            if runtime_manifest.get("entrypoint") != "visionguard-core-runtime.exe":
                errors.append("Core Runtime manifest entrypoint is unexpected")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Core Runtime manifest is unreadable: {type(exc).__name__}")

    models_root = root / "components/core-models"
    model_manifest_path = models_root / "manifest.json"
    if model_manifest_path.is_file():
        try:
            model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
            models = model_manifest.get("models")
            if model_manifest.get("bundle_type") != "core":
                errors.append("Core Models manifest bundle_type is not 'core'")
            if not isinstance(models, dict):
                errors.append("Core Models manifest has no models mapping")
                models = {}
            actual_roles = set(models)
            if actual_roles != EXPECTED_MODEL_ROLES:
                errors.append(
                    "Core Models roles differ from the required Detector/OCR/Baseline set: "
                    f"{sorted(actual_roles)}"
                )
            for model_role in sorted(EXPECTED_MODEL_ROLES & actual_roles):
                model = models[model_role]
                if not isinstance(model, dict):
                    errors.append(f"Core Models role {model_role} has invalid metadata")
                    continue
                model_path = _safe_manifest_path(models_root, model.get("path"))
                if model_path is None:
                    errors.append(f"Core Models role {model_role} has an unsafe artifact path")
                    continue
                relative = model_path.relative_to(root).as_posix()
                kind = str(model.get("kind", ""))
                if kind not in {"file", "directory"}:
                    errors.append(f"Core Models role {model_role} has invalid kind {kind!r}")
                    continue
                inspect(f"model_{model_role}", relative, kind)
                if kind == "directory":
                    files = model.get("files")
                    if not isinstance(files, list):
                        errors.append(f"Core Models role {model_role} has no file inventory")
                        continue
                    for file_index, file_metadata in enumerate(files):
                        declared = (
                            file_metadata.get("path") if isinstance(file_metadata, dict) else None
                        )
                        declared_path = _safe_manifest_path(model_path, declared)
                        if declared_path is None:
                            errors.append(
                                "Core Models role "
                                f"{model_role} file {file_index} has an unsafe path"
                            )
                            continue
                        inspect(
                            f"model_{model_role}_file",
                            declared_path.relative_to(root).as_posix(),
                            "file",
                        )
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Core Models manifest is unreadable: {type(exc).__name__}")

    return {
        "expected_paths": expected,
        "observed_paths": observed,
        "missing_paths": missing,
        "layout_errors": errors,
    }


def format_install_tree(
    root: Path, *, max_depth: int = 4, max_entries: int = 240, max_children: int = 40
) -> list[str]:
    """Return a bounded, relative install tree suitable for public CI evidence."""
    lines = ["<install-root>/"]
    if not root.is_dir():
        lines.append("  [missing]")
        return lines
    emitted = 0
    truncated = False

    def visit(directory: Path, depth: int, prefix: str) -> None:
        nonlocal emitted, truncated
        if depth >= max_depth or emitted >= max_entries:
            if emitted >= max_entries:
                truncated = True
            return
        children = sorted(
            directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())
        )
        shown = children[:max_children]
        for index, child in enumerate(shown):
            if emitted >= max_entries:
                truncated = True
                return
            last = index == len(shown) - 1 and len(children) <= max_children
            branch = "`-- " if last else "|-- "
            suffix = "/" if child.is_dir() else f" ({child.stat().st_size} bytes)"
            lines.append(f"{prefix}{branch}{child.name}{suffix}")
            emitted += 1
            if child.is_dir():
                visit(child, depth + 1, prefix + ("    " if last else "|   "))
        if len(children) > max_children and emitted < max_entries:
            lines.append(f"{prefix}`-- ... {len(children) - max_children} entries omitted")
            emitted += 1
            truncated = True

    visit(root, 0, "")
    if truncated:
        lines.append(f"... tree bounded to depth {max_depth} and {max_entries} entries")
    return lines


def console_safe_text(message: str, encoding: str | None) -> str:
    """Make CI console output representable without changing the UTF-8 evidence log."""
    if not encoding:
        return message
    try:
        return message.encode(encoding, errors="backslashreplace").decode(encoding)
    except LookupError:
        return message.encode("ascii", errors="backslashreplace").decode("ascii")


def write_evidence(path: Path, payload: dict[str, object]) -> None:
    """Serialize failure or success evidence consistently for artifact upload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def core_smoke_contract_checks(smoke: dict) -> dict[str, bool]:
    """Evaluate the versioned public smoke payload without using legacy field paths."""
    live = smoke.get("live")
    ready = smoke.get("ready")
    meta = smoke.get("meta")
    review = smoke.get("review")
    capabilities = meta.get("capabilities") if isinstance(meta, dict) else None
    return {
        "live": isinstance(live, dict) and live.get("status") == "ok",
        "ready": isinstance(ready, dict) and ready.get("status") in {"ok", "ready"},
        "meta": isinstance(capabilities, dict) and capabilities.get("core_ready") is True,
        "fast_review": isinstance(review, dict) and review.get("schema_valid") is True,
    }


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
    layout_evidence: dict[str, list[dict[str, object]] | list[str]] = {
        "expected_paths": [],
        "observed_paths": [],
        "missing_paths": [],
        "layout_errors": [],
    }

    def record(message: str) -> None:
        log_lines.append(message)
        print(console_safe_text(message, sys.stdout.encoding), flush=True)

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
        record("Installed application tree (relative, bounded):")
        for tree_line in format_install_tree(install_dir):
            record(tree_line)
        layout_evidence = inspect_installed_layout(install_dir)
        checks["expected_paths"] = layout_evidence["expected_paths"]
        checks["observed_paths"] = layout_evidence["observed_paths"]
        checks["missing_paths"] = layout_evidence["missing_paths"]
        checks["layout_errors"] = layout_evidence["layout_errors"]
        if layout_evidence["missing_paths"] or layout_evidence["layout_errors"]:
            missing_names = [item["path"] for item in layout_evidence["missing_paths"]]
            raise RuntimeError(
                "installed layout validation failed; "
                f"missing_paths={missing_names}; errors={layout_evidence['layout_errors']}"
            )
        runtime = install_dir / "components/core-runtime/visionguard-core-runtime.exe"
        models = install_dir / "components/core-models"
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
            str(runtime),
            "--models",
            str(models),
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
            record("Packaged Core smoke stdout:")
            for line in result.stdout.splitlines() or ["<empty>"]:
                record(line)
            record("Packaged Core smoke stderr:")
            for line in result.stderr.splitlines() or ["<empty>"]:
                record(line)
            runtime_logs = sorted((smoke_dir / "logs").glob("*.log"))
            for runtime_log in runtime_logs:
                record(f"Packaged Core runtime log: {runtime_log.name}")
                for line in runtime_log.read_text(encoding="utf-8", errors="replace").splitlines():
                    record(line)
            raise RuntimeError(f"packaged Core smoke exited with {result.returncode}")
        smoke = parse_smoke(result.stdout)
        contract_checks = core_smoke_contract_checks(smoke)
        checks.update(contract_checks)
        failed_contracts = [name for name, passed in contract_checks.items() if not passed]
        if failed_contracts:
            raise RuntimeError(
                "Core health/meta/Fast Review contract failed: "
                + ", ".join(failed_contracts)
            )
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
            "expected_paths": layout_evidence["expected_paths"],
            "observed_paths": layout_evidence["observed_paths"],
            "missing_paths": layout_evidence["missing_paths"],
            "layout_errors": layout_evidence["layout_errors"],
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
        write_evidence(evidence_path, evidence)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
