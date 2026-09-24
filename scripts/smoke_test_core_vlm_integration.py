"""Packaged Core + optional VLM integration, crash isolation, and shutdown smoke."""

import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def wait_endpoint(status: Path, process: subprocess.Popen, timeout: float = 90) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if status.is_file():
            payload = json.loads(status.read_text(encoding="utf-8"))
            if payload.get("state") == "failed":
                raise RuntimeError(payload)
            if payload.get("endpoint") and payload.get("state") in {
                "installed",
                "waiting_for_ready",
                "ready",
            }:
                return payload["endpoint"]
        if process.poll() is not None:
            raise RuntimeError(f"runtime exited: {process.returncode}")
        time.sleep(0.2)
    raise TimeoutError(status)


def main() -> None:
    work = (ROOT / "artifacts/core-vlm-integration-smoke").resolve()
    work.mkdir(parents=True, exist_ok=True)
    core_status, vlm_status = work / "core-status.json", work / "vlm-status.json"
    core_status.unlink(missing_ok=True)
    vlm_status.unlink(missing_ok=True)
    core_config, vlm_config = work / "core.json", work / "vlm.yaml"
    core_config.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_bundle_path": str((ROOT / "models/core-models-v1").resolve()),
                "user_data_dir": str(work),
                "artifact_root": str(work / "artifacts"),
                "log_root": str(work / "logs/core"),
                "cache_root": str(work / "cache/core"),
                "model_validation": "quick",
                "runtime_edition": "cpu",
                "warmup_on_startup": False,
                "save_artifacts": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    vlm_config.write_text(
        yaml.safe_dump(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_path": str((ROOT / "models/vlm-models-v1/vlm").resolve()),
                "model_bundle_version": "vlm-models-v1",
                "cache_root": str(work / "cache/vlm"),
                "log_root": str(work / "logs/vlm"),
                "prompts_dir": str((ROOT / "prompts/vlm").resolve()),
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
    core_token, vlm_token = secrets.token_hex(24), secrets.token_hex(24)
    core_env = {**os.environ, "VISIONGUARD_CONTROL_TOKEN": core_token}
    vlm_env = {
        **os.environ,
        "VISIONGUARD_VLM_SESSION_TOKEN": vlm_token,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    core = subprocess.Popen(
        [
            str(ROOT / "runtime-dist-core/visionguard-core-runtime/visionguard-core-runtime.exe"),
            "--config",
            str(core_config),
            "--status-file",
            str(core_status),
        ],
        cwd=work,
        env=core_env,
    )
    vlm = subprocess.Popen(
        [
            str(ROOT / "runtime-dist-vlm/visionguard-vlm-runtime/visionguard-vlm-runtime.exe"),
            "--config",
            str(vlm_config),
            "--status-file",
            str(vlm_status),
        ],
        cwd=work,
        env=vlm_env,
    )
    report = {}
    try:
        core_endpoint = wait_endpoint(core_status, core, 180)
        vlm_endpoint = wait_endpoint(vlm_status, vlm, 60)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{core_endpoint}/health/ready", timeout=3).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        response = httpx.put(
            f"{core_endpoint}/_runtime/vlm",
            headers={"X-VisionGuard-Control": core_token},
            json={"endpoint": vlm_endpoint, "session_token": vlm_token},
            timeout=10,
        )
        response.raise_for_status()
        registered_meta = httpx.get(f"{core_endpoint}/v1/meta", timeout=5).json()
        with (ROOT / "data/vlm_eval/safe.png").open("rb") as stream:
            review = httpx.post(
                f"{core_endpoint}/v1/review?pipeline_mode=cascaded&include_details=true",
                files={"file": ("safe.png", stream, "image/png")},
                timeout=360,
            ).json()
        core_pid = core.pid
        vlm.kill()
        vlm.wait(timeout=10)
        with (ROOT / "data/vlm_eval/safe.png").open("rb") as stream:
            after_crash = httpx.post(
                f"{core_endpoint}/v1/review?pipeline_mode=full",
                files={"file": ("safe.png", stream, "image/png")},
                timeout=180,
            ).json()
        report = {
            "core_pid_unchanged": core.poll() is None and core.pid == core_pid,
            "vlm_pid": vlm.pid,
            "registered_capabilities": registered_meta["capabilities"],
            "review": {
                "status": review["status"],
                "risk_level": review["result"]["risk_level"],
                "vlm": review["modules"]["vlm"],
            },
            "after_vlm_crash": {
                "status": after_crash["status"],
                "risk_level": after_crash["result"]["risk_level"],
                "manual": after_crash["result"]["requires_manual_review"],
                "vlm": after_crash["modules"]["vlm"],
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        (work / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    finally:
        try:
            endpoint = json.loads(core_status.read_text(encoding="utf-8")).get("endpoint")
            if endpoint:
                httpx.post(
                    f"{endpoint}/_runtime/shutdown",
                    headers={"X-VisionGuard-Control": core_token},
                    timeout=5,
                )
        except Exception:
            pass
        for process in (vlm, core):
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
