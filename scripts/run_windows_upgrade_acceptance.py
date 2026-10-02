"""Validate Windows installer upgrade, downgrade rejection, and explicit rollback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from scripts.run_windows_core_acceptance import (
        core_smoke_contract_checks,
        inspect_installed_layout,
        parse_smoke,
        running_product_processes,
        wait_removed,
        write_evidence,
    )
else:
    from run_windows_core_acceptance import (
        core_smoke_contract_checks,
        inspect_installed_layout,
        parse_smoke,
        running_product_processes,
        wait_removed,
        write_evidence,
    )

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
FINGERPRINT_FILES = (
    "visionguard-desktop.exe",
    "components/core-runtime/visionguard-core-runtime.exe",
    "components/core-runtime/runtime-manifest.json",
    "components/core-models/manifest.json",
    "bootstrap/advanced-ai-bootstrap-manifest.json",
)


class LifecycleAcceptanceError(RuntimeError):
    """A fail-closed lifecycle contract violation."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(value)
    if match is None:
        raise LifecycleAcceptanceError(f"invalid numeric application version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def load_candidate(installer: Path, metadata_path: Path, role: str) -> dict[str, object]:
    if not installer.is_file():
        raise LifecycleAcceptanceError(f"{role} installer is missing: {installer.name}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleAcceptanceError(f"invalid {role} metadata: {type(exc).__name__}") from exc
    if metadata.get("schema_version") != 1:
        raise LifecycleAcceptanceError(f"unsupported {role} metadata schema")
    required = ("git_sha", "workflow_run_id", "installer_name", "sha256", "app_version")
    missing = [name for name in required if not str(metadata.get(name, "")).strip()]
    if missing:
        raise LifecycleAcceptanceError(f"{role} metadata is missing: {', '.join(missing)}")
    if metadata["installer_name"] != installer.name:
        raise LifecycleAcceptanceError(f"{role} installer filename does not match metadata")
    actual_hash = sha256(installer)
    if actual_hash != str(metadata["sha256"]).casefold():
        raise LifecycleAcceptanceError(f"{role} installer SHA-256 mismatch")
    version_tuple(str(metadata["app_version"]))
    result = dict(metadata)
    result["actual_sha256"] = actual_hash
    result["size_bytes"] = installer.stat().st_size
    return result


def validate_candidate_pair(baseline: dict[str, object], candidate: dict[str, object]) -> None:
    if version_tuple(str(baseline["app_version"])) >= version_tuple(
        str(candidate["app_version"])
    ):
        raise LifecycleAcceptanceError("candidate version must be greater than baseline version")
    if baseline["git_sha"] == candidate["git_sha"]:
        raise LifecycleAcceptanceError("baseline and candidate must come from different commits")
    if baseline["actual_sha256"] == candidate["actual_sha256"]:
        raise LifecycleAcceptanceError("baseline and candidate installers must be different files")


def install_fingerprint(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in FINGERPRINT_FILES:
        target = root / Path(relative.replace("/", os.sep))
        if not target.is_file():
            raise LifecycleAcceptanceError(f"installed fingerprint file is missing: {relative}")
        result[relative] = sha256(target)
    wheels = sorted((root / "bootstrap/packages").glob("visionguard_moderation-*.whl"))
    if len(wheels) != 1:
        raise LifecycleAcceptanceError("installed bootstrap wheel inventory is invalid")
    relative = wheels[0].relative_to(root).as_posix()
    result[relative] = sha256(wheels[0])
    return result


def run_installer(installer: Path, install_dir: Path, timeout: int = 360) -> int:
    result = subprocess.run(
        [str(installer), "/S", f"/D={install_dir}"], check=False, timeout=timeout
    )
    return result.returncode


def uninstall(install_dir: Path, timeout: int = 240) -> tuple[int | None, bool]:
    uninstallers = list(install_dir.glob("uninstall*.exe")) if install_dir.exists() else []
    if len(uninstallers) != 1:
        return None, not install_dir.exists()
    result = subprocess.run([str(uninstallers[0]), "/S"], check=False, timeout=timeout)
    return result.returncode, wait_removed(install_dir)


def smoke_core(install_dir: Path, work_dir: Path) -> dict[str, object]:
    command = [
        sys.executable,
        str(ROOT / "scripts/smoke_test_packaged_runtime.py"),
        "--runtime",
        str(install_dir / "components/core-runtime/visionguard-core-runtime.exe"),
        "--models",
        str(install_dir / "components/core-models"),
        "--work-dir",
        str(work_dir),
        "--image",
        str(ROOT / "data/vlm_eval/safe.png"),
        "--mode",
        "cascaded",
        "--runtime-edition",
        "cpu",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=420)
    if result.returncode:
        raise LifecycleAcceptanceError(
            f"packaged Core smoke failed with {result.returncode}: {result.stderr[-2000:]}"
        )
    payload = parse_smoke(result.stdout)
    failed = [name for name, passed in core_smoke_contract_checks(payload).items() if not passed]
    if failed:
        raise LifecycleAcceptanceError(f"packaged Core contract failed: {', '.join(failed)}")
    return payload


def public_candidate(metadata: dict[str, object]) -> dict[str, object]:
    return {
        name: metadata[name]
        for name in (
            "app_version",
            "git_sha",
            "workflow_run_id",
            "installer_name",
            "actual_sha256",
            "size_bytes",
        )
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-installer", required=True, type=Path)
    parser.add_argument("--baseline-metadata", required=True, type=Path)
    parser.add_argument("--candidate-installer", required=True, type=Path)
    parser.add_argument("--candidate-metadata", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--user-data-dir", type=Path)
    args = parser.parse_args(argv)

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    install_dir = (args.install_dir or output / "installed-app").resolve()
    user_data = (args.user_data_dir or output / "product-user-data").resolve()
    evidence_path = output / "upgrade-rollback-acceptance.json"
    log_path = output / "acceptance.log"
    log_lines: list[str] = []
    checks: dict[str, object] = {}
    baseline: dict[str, object] = {}
    candidate: dict[str, object] = {}
    status, reason = "FAIL", "LIFECYCLE_ACCEPTANCE_DID_NOT_COMPLETE"
    started = time.perf_counter()

    def record(message: str) -> None:
        log_lines.append(message)
        print(message, flush=True)

    try:
        if platform.system() != "Windows":
            raise LifecycleAcceptanceError("Gate 4 requires Windows")
        if install_dir.exists() or running_product_processes():
            raise LifecycleAcceptanceError("VisionGuard must not be installed or running")
        baseline = load_candidate(
            args.baseline_installer.resolve(), args.baseline_metadata.resolve(), "baseline"
        )
        candidate = load_candidate(
            args.candidate_installer.resolve(), args.candidate_metadata.resolve(), "candidate"
        )
        validate_candidate_pair(baseline, candidate)
        checks["candidate_provenance"] = True

        user_data.mkdir(parents=True, exist_ok=True)
        marker = user_data / "gate4-user-data-marker.json"
        marker_payload = {
            "schema_version": 1,
            "purpose": "verify installer lifecycle data retention",
        }
        marker.write_text(json.dumps(marker_payload, indent=2) + "\n", encoding="utf-8")
        marker_hash = sha256(marker)

        record("Installing baseline candidate")
        checks["baseline_install_exit_code"] = run_installer(
            args.baseline_installer.resolve(), install_dir
        )
        if checks["baseline_install_exit_code"] != 0:
            raise LifecycleAcceptanceError("baseline installer failed")
        baseline_layout = inspect_installed_layout(install_dir)
        if baseline_layout["missing_paths"] or baseline_layout["layout_errors"]:
            raise LifecycleAcceptanceError("baseline installed layout is incomplete")
        baseline_fingerprint = install_fingerprint(install_dir)
        smoke_core(install_dir, output / "baseline-smoke")
        checks["baseline_ready"] = True

        record("Installing newer candidate over baseline")
        checks["upgrade_install_exit_code"] = run_installer(
            args.candidate_installer.resolve(), install_dir
        )
        if checks["upgrade_install_exit_code"] != 0:
            raise LifecycleAcceptanceError("candidate upgrade installer failed")
        candidate_layout = inspect_installed_layout(install_dir)
        if candidate_layout["missing_paths"] or candidate_layout["layout_errors"]:
            raise LifecycleAcceptanceError("upgraded installed layout is incomplete")
        candidate_fingerprint = install_fingerprint(install_dir)
        checks["installed_payload_changed"] = baseline_fingerprint != candidate_fingerprint
        if not checks["installed_payload_changed"]:
            raise LifecycleAcceptanceError("upgrade did not replace the installed payload")
        smoke_core(install_dir, output / "candidate-smoke")
        checks["candidate_ready"] = True
        checks["user_data_preserved_after_upgrade"] = (
            marker.is_file() and sha256(marker) == marker_hash
        )
        if not checks["user_data_preserved_after_upgrade"]:
            raise LifecycleAcceptanceError("user data changed during upgrade")

        record("Verifying in-place downgrade is rejected or leaves candidate active")
        checks["downgrade_attempt_exit_code"] = run_installer(
            args.baseline_installer.resolve(), install_dir
        )
        post_downgrade_fingerprint = install_fingerprint(install_dir)
        checks["in_place_downgrade_rejected"] = (
            checks["downgrade_attempt_exit_code"] != 0
            or post_downgrade_fingerprint == candidate_fingerprint
        )
        if not checks["in_place_downgrade_rejected"]:
            raise LifecycleAcceptanceError("older installer replaced the active candidate in place")

        record("Performing explicit rollback through uninstall and baseline reinstall")
        uninstall_code, removed = uninstall(install_dir)
        checks["candidate_uninstall_exit_code"] = uninstall_code
        checks["candidate_install_directory_removed"] = removed
        if uninstall_code != 0 or not removed:
            raise LifecycleAcceptanceError("candidate uninstall failed before rollback")
        checks["user_data_preserved_after_uninstall"] = (
            marker.is_file() and sha256(marker) == marker_hash
        )
        if not checks["user_data_preserved_after_uninstall"]:
            raise LifecycleAcceptanceError("user data changed during candidate uninstall")
        checks["rollback_install_exit_code"] = run_installer(
            args.baseline_installer.resolve(), install_dir
        )
        if checks["rollback_install_exit_code"] != 0:
            raise LifecycleAcceptanceError("baseline reinstall failed during rollback")
        checks["rollback_payload_restored"] = (
            install_fingerprint(install_dir) == baseline_fingerprint
        )
        if not checks["rollback_payload_restored"]:
            raise LifecycleAcceptanceError("rollback did not restore the baseline payload")
        smoke_core(install_dir, output / "rollback-smoke")
        checks["rollback_ready"] = True
        checks["user_data_preserved_after_rollback"] = (
            marker.is_file() and sha256(marker) == marker_hash
        )
        if not checks["user_data_preserved_after_rollback"]:
            raise LifecycleAcceptanceError("user data changed during rollback")
        status, reason = "PASS", "ALL_UPGRADE_AND_ROLLBACK_CHECKS_PASSED"
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        record(reason)
    finally:
        uninstall_code, removed = uninstall(install_dir)
        checks["final_uninstall_exit_code"] = uninstall_code
        checks["final_install_directory_removed"] = removed
        time.sleep(1)
        orphans = running_product_processes()
        checks["orphan_processes"] = orphans
        if status == "PASS" and (uninstall_code != 0 or not removed or orphans):
            status, reason = "FAIL", "FINAL_CLEANUP_OR_ORPHAN_CHECK_FAILED"
        evidence = {
            "schema_version": 1,
            "gate": "installer_lifecycle",
            "status": status,
            "reason": reason,
            "executed_at": datetime.now(UTC).isoformat(),
            "runner": {"os": platform.platform(), "architecture": platform.machine()},
            "baseline": public_candidate(baseline) if baseline else {},
            "candidate": public_candidate(candidate) if candidate else {},
            "upgrade": {
                "status": "PASS" if status == "PASS" else "FAIL",
                "checks": {
                    name: value
                    for name, value in checks.items()
                    if name.startswith(("baseline_", "upgrade_", "candidate_", "user_data_"))
                },
            },
            "rollback": {
                "status": "PASS" if status == "PASS" else "FAIL",
                "checks": {
                    name: value
                    for name, value in checks.items()
                    if name.startswith(("downgrade_", "in_place_", "rollback_"))
                },
            },
            "cleanup": {
                "uninstall_exit_code": checks.get("final_uninstall_exit_code"),
                "install_directory_removed": checks.get("final_install_directory_removed"),
                "orphan_processes": orphans,
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        write_evidence(evidence_path, evidence)
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
