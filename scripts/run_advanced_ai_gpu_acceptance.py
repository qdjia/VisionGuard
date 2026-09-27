"""Run a fresh, isolated Advanced AI bootstrap and local GPU acceptance flow."""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import httpx  # noqa: E402
import yaml  # noqa: E402

from scripts.build_release import build_bootstrap_wheel  # noqa: E402
from visionguard.bootstrap.manager import BootstrapError, BootstrapManager  # noqa: E402


def wait_endpoint(status_path: Path, process: subprocess.Popen, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if status_path.is_file():
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            if payload.get("state") == "failed":
                raise RuntimeError(payload)
            endpoint = payload.get("endpoint")
            if endpoint:
                return str(endpoint)
        if process.poll() is not None:
            raise RuntimeError(f"runtime exited with {process.returncode}")
        time.sleep(0.25)
    raise TimeoutError(f"runtime endpoint timeout: {status_path.name}")


def review(endpoint: str, image: Path, mode: str) -> dict:
    with image.open("rb") as stream:
        response = httpx.post(
            f"{endpoint}/v1/review?pipeline_mode={mode}&include_details=true",
            files={"file": (image.name, stream, "image/png")},
            timeout=360,
        )
    response.raise_for_status()
    return response.json()


def shutdown(endpoint: str | None, token: str, process: subprocess.Popen | None) -> None:
    if endpoint:
        try:
            httpx.post(
                f"{endpoint}/_runtime/shutdown",
                headers={"X-VisionGuard-Control": token},
                timeout=5,
            )
        except httpx.HTTPError:
            pass
    if process and process.poll() is None:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def start_vlm(
    python: Path, models: Path, work: Path, revision: str
) -> tuple[subprocess.Popen, str, str, Path]:
    work.mkdir(parents=True, exist_ok=True)
    status = work / "status.json"
    status.unlink(missing_ok=True)
    config = work / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_path": str(models / "vlm"),
                "model_bundle_version": "vlm-models-v1",
                "model_revision": revision,
                "cache_root": str(work / "cache"),
                "log_root": str(work / "logs"),
                "prompts_dir": str(ROOT / "prompts/vlm"),
                "prompt_version": "v1",
                "device": "auto",
                "dtype": "auto",
                "timeout_seconds": 180,
                "load_timeout_seconds": 300,
                "max_new_tokens": 512,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    token = secrets.token_hex(24)
    environment = {
        **os.environ,
        "VISIONGUARD_VLM_SESSION_TOKEN": token,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "visionguard.vlm_runtime",
            "--config",
            str(config),
            "--status-file",
            str(status),
        ],
        cwd=work,
        env=environment,
    )
    endpoint = wait_endpoint(status, process, 90)
    unauthorized = httpx.get(f"{endpoint}/v1/meta", timeout=5)
    if unauthorized.status_code != 404:
        process.kill()
        raise RuntimeError("VLM endpoint accepted a request without its session token")
    return process, endpoint, token, status


def start_core(runtime: Path, models: Path, work: Path) -> tuple[subprocess.Popen, str, str, Path]:
    work.mkdir(parents=True, exist_ok=True)
    status = work / "status.json"
    status.unlink(missing_ok=True)
    config = work / "config.json"
    config.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_bundle_path": str(models),
                "user_data_dir": str(work),
                "artifact_root": str(work / "artifacts"),
                "log_root": str(work / "logs"),
                "cache_root": str(work / "cache"),
                "warmup_on_startup": False,
                "save_artifacts": False,
                "model_validation": "quick",
                "runtime_edition": "cpu",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    token = secrets.token_hex(24)
    process = subprocess.Popen(
        [str(runtime), "--config", str(config), "--status-file", str(status)],
        cwd=work,
        env={**os.environ, "VISIONGUARD_CONTROL_TOKEN": token, "YOLO_AUTOINSTALL": "false"},
    )
    endpoint = wait_endpoint(status, process, 240)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{endpoint}/health/ready", timeout=5).status_code == 200:
                return process, endpoint, token, status
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError("Core Runtime did not become ready")


def register_vlm(core: str, core_token: str, vlm: str, vlm_token: str) -> None:
    response = httpx.put(
        f"{core}/_runtime/vlm",
        headers={"X-VisionGuard-Control": core_token},
        json={"endpoint": vlm, "session_token": vlm_token},
        timeout=10,
    )
    response.raise_for_status()


def network_blocked(message: str) -> bool:
    lowered = message.casefold()
    return any(
        token in lowered
        for token in (
            "network",
            "urlerror",
            "timeout",
            "timed out",
            "connection",
            "remote end closed",
            "chunkedencoding",
            "http error",
        )
    )


def probe_managed_gpu(python: Path) -> dict[str, object]:
    """Capture the GPU view from the freshly installed managed PyTorch runtime."""
    script = (
        "import json,torch;"
        "available=torch.cuda.is_available();"
        "props=torch.cuda.get_device_properties(0) if available else None;"
        "print(json.dumps({'torch_version':torch.__version__,"
        "'cuda_available':available,'torch_cuda_version':torch.version.cuda,"
        "'device_name':torch.cuda.get_device_name(0) if available else None,"
        "'device_memory_bytes':props.total_memory if props else None}))"
    )
    result = subprocess.run(
        [str(python), "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONNOUSERSITE": "1"},
    )
    payload = json.loads(result.stdout)
    if not payload.get("cuda_available"):
        raise RuntimeError("fresh managed PyTorch cannot access CUDA")
    return payload


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "release-evidence/advanced-ai-gpu-acceptance.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "packaging/bootstrap/advanced-ai-bootstrap-manifest.json",
    )
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--bootstrap-attempts", type=int, default=2)
    parser.add_argument(
        "--core-runtime",
        type=Path,
        default=ROOT / "runtime-dist-core/visionguard-core-runtime/visionguard-core-runtime.exe",
    )
    parser.add_argument("--core-models", type=Path, default=ROOT / "models/core-models-v1")
    args = parser.parse_args(argv)
    if platform.system() != "Windows":
        raise SystemExit("Advanced AI GPU acceptance requires Windows")
    data_dir = args.data_dir.resolve()
    if data_dir.exists() and any(data_dir.iterdir()) and not args.resume:
        raise SystemExit("--data-dir must be empty for a fresh run; use --resume only for retry")
    data_dir.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    wheel = args.wheel.resolve() if args.wheel else build_bootstrap_wheel().resolve()
    status_path = data_dir / "bootstrap-status.json"
    cancel_path = data_dir / "cancel.install"
    report: dict[str, object] = {
        "schema_version": 1,
        "gate": "advanced_ai_gpu",
        "status": "FAIL",
        "reason": "ACCEPTANCE_DID_NOT_COMPLETE",
        "executed_at": datetime.now(UTC).isoformat(),
        "fresh_environment": not args.resume,
        "independent_cache": True,
        "data_root_scope": "dedicated VisionGuard acceptance directory",
        "manifest": {
            "python_version": manifest["python"]["version"],
            "pytorch": manifest["packages"]["pytorch"],
            "transformers": next(
                item
                for item in manifest["packages"]["runtime"]
                if item.startswith("transformers==")
            ),
            "accelerate": next(
                item for item in manifest["packages"]["runtime"] if item.startswith("accelerate==")
            ),
            "model_id": manifest["model"]["id"],
            "model_revision": manifest["model"]["revision"],
        },
    }
    manager = BootstrapManager(
        args.manifest.resolve(),
        data_dir,
        status_path,
        wheel,
        ROOT / "prompts/vlm",
        cancel_path,
    )
    installed = None
    attempts = []
    for attempt in range(1, max(1, args.bootstrap_attempts) + 1):
        started = time.perf_counter()
        try:
            installed = manager.install()
            attempts.append(
                {"attempt": attempt, "status": "PASS", "seconds": time.perf_counter() - started}
            )
            break
        except BootstrapError as exc:
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "BLOCKED_NETWORK" if network_blocked(str(exc)) else "FAIL",
                    "error_code": exc.code,
                    "message": str(exc),
                    "seconds": time.perf_counter() - started,
                }
            )
            if not network_blocked(str(exc)):
                break
    report["bootstrap_attempts"] = attempts
    if installed is None:
        active = data_dir / "components/components.json"
        report["atomicity"] = {"half_installed_active": active.exists()}
        blocked = any(item["status"] == "BLOCKED_NETWORK" for item in attempts)
        report["status"] = "BLOCKED_NETWORK" if blocked else "FAIL"
        report["reason"] = attempts[-1].get("message", "BOOTSTRAP_FAILED")
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if blocked else 1

    report["bootstrap"] = installed
    try:
        registry = json.loads((data_dir / "components/components.json").read_text(encoding="utf-8"))
        managed_python = data_dir / registry["python_executable"]
        managed_models = data_dir / registry["vlm_models_directory"]
        report["gpu"] = probe_managed_gpu(managed_python)
        report["restart_rediscovery"] = {
            "registry_reloaded": True,
            "python_executable_exists": managed_python.is_file(),
            "model_directory_exists": managed_models.is_dir(),
            "scope": "managed component registry; Desktop GUI restart remains a manual check",
        }
        if not managed_python.is_file() or not managed_models.is_dir():
            raise RuntimeError("active Advanced AI registry does not resolve after bootstrap")
    except Exception as exc:
        report["reason"] = f"managed environment validation failed: {type(exc).__name__}: {exc}"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    smoke_dir = data_dir / "acceptance/vlm-three-request-smoke"
    smoke_env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    smoke = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/smoke_test_packaged_vlm_runtime.py"),
            "--managed-python",
            str(managed_python),
            "--models",
            str(managed_models),
            "--model-revision",
            manifest["model"]["revision"],
            "--image",
            str(ROOT / "data/vlm_eval/safe.png"),
            "--work-dir",
            str(smoke_dir),
            "--requests",
            "3",
        ],
        env=smoke_env,
        check=False,
        timeout=1200,
    )
    if smoke.returncode:
        report["reason"] = f"three-request VLM smoke failed: {smoke.returncode}"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    vlm_smoke = json.loads((smoke_dir / "report.json").read_text(encoding="utf-8"))
    report["vlm_three_request_smoke"] = vlm_smoke

    core = vlm = None
    core_endpoint = vlm_endpoint = None
    core_token = vlm_token = ""
    try:
        core, core_endpoint, core_token, _ = start_core(
            args.core_runtime.resolve(), args.core_models.resolve(), data_dir / "acceptance/core"
        )
        vlm, vlm_endpoint, vlm_token, _ = start_vlm(
            managed_python,
            managed_models,
            data_dir / "acceptance/vlm-integration-1",
            manifest["model"]["revision"],
        )
        register_vlm(core_endpoint, core_token, vlm_endpoint, vlm_token)
        safe = review(core_endpoint, ROOT / "data/vlm_eval/safe.png", "full")
        risky = review(core_endpoint, ROOT / "data/vlm_eval/risky.png", "full")
        cascaded = [
            review(core_endpoint, ROOT / f"data/vlm_eval/{name}", "cascaded")
            for name in ("safe.png", "text.png", "risky.png")
        ]
        routed = [item for item in cascaded if (item.get("routing") or {}).get("call_vlm")]
        if not routed:
            raise RuntimeError("no cascaded Core request routed through RemoteVLMProvider")
        core_pid = core.pid
        vlm.kill()
        vlm.wait(timeout=10)
        after_crash = review(core_endpoint, ROOT / "data/vlm_eval/safe.png", "full")
        crash_pass = (
            core.poll() is None
            and core.pid == core_pid
            and after_crash.get("status") == "partial"
            and bool(after_crash.get("result", {}).get("requires_manual_review"))
        )
        vlm, vlm_endpoint, vlm_token, _ = start_vlm(
            managed_python,
            managed_models,
            data_dir / "acceptance/vlm-integration-2",
            manifest["model"]["revision"],
        )
        register_vlm(core_endpoint, core_token, vlm_endpoint, vlm_token)
        restarted = review(core_endpoint, ROOT / "data/vlm_eval/safe.png", "full")
        restart_pass = core.poll() is None and restarted.get("status") == "completed"
        report["integration"] = {
            "dynamic_loopback_port": not vlm_endpoint.endswith(":0"),
            "session_token_rejected_when_missing": True,
            "safe": {
                "status": safe.get("status"),
                "risk_level": safe.get("result", {}).get("risk_level"),
            },
            "risky": {
                "status": risky.get("status"),
                "risk_level": risky.get("result", {}).get("risk_level"),
            },
            "routing_triggered_vlm": True,
            "cascaded_attempts": len(cascaded),
            "crash_fail_safe": crash_pass,
            "restart_without_core_restart": restart_pass,
            "local_inference_boundary": {
                "hf_offline_after_install": True,
                "cloud_inference_provider": False,
            },
        }
        if vlm_smoke.get("model_init_count") != 1 or not crash_pass or not restart_pass:
            raise RuntimeError("model init, crash isolation, or restart acceptance failed")
        report["status"] = "PASS"
        report["reason"] = "ALL_ADVANCED_AI_GPU_CHECKS_PASSED"
    except Exception as exc:
        report["status"] = "FAIL"
        report["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        if vlm is not None and vlm.poll() is None:
            vlm.kill()
            vlm.wait(timeout=10)
        shutdown(core_endpoint, core_token, core)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
