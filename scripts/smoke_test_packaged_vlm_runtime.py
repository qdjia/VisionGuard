"""Offline smoke test for the packaged optional VLM runtime."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import httpx
import yaml

from visionguard.moderation.policy import load_policy
from visionguard.vlm.schemas import VLMContext

ROOT = Path(__file__).resolve().parents[1]


def gpu_memory_mib() -> int | None:
    try:
        value = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).splitlines()[0]
        return int(value.strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        type=Path,
        default=ROOT / "runtime-dist-vlm/visionguard-vlm-runtime/visionguard-vlm-runtime.exe",
    )
    parser.add_argument("--models", type=Path, default=ROOT / "models/vlm-models-v1")
    parser.add_argument("--image", type=Path, default=ROOT / "data/vlm_eval/safe.png")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "artifacts/vlm-runtime-smoke")
    parser.add_argument("--requests", type=int, default=3)
    args = parser.parse_args()
    runtime, bundle, work = args.runtime.resolve(), args.models.resolve(), args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    config_path, status_path = work / "config.yaml", work / "status.json"
    status_path.unlink(missing_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_path": str(bundle / "vlm"),
                "model_bundle_version": "vlm-models-v1",
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
    idle_gpu_mib = gpu_memory_mib()
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(runtime), "--config", str(config_path), "--status-file", str(status_path)],
        cwd=work,
        env=environment,
    )
    endpoint = None
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if status_path.is_file():
                status = json.loads(status_path.read_text(encoding="utf-8"))
                endpoint = status.get("endpoint")
                if endpoint:
                    break
                if status.get("state") == "failed":
                    raise RuntimeError(status)
            if process.poll() is not None:
                raise RuntimeError(f"VLM runtime exited with {process.returncode}")
            time.sleep(0.2)
        if not endpoint:
            raise TimeoutError("VLM runtime did not publish a dynamic endpoint")
        process_start_ms = (time.perf_counter() - started) * 1000
        headers = {"X-VisionGuard-Session": token}
        unauthorized = httpx.get(f"{endpoint}/v1/meta", timeout=5)
        if unauthorized.status_code != 404:
            raise RuntimeError("session protection failed")
        before = httpx.get(f"{endpoint}/v1/meta", headers=headers, timeout=5).json()
        policy = load_policy(ROOT / "configs/moderation_policy.yaml")
        latencies, results, runtime_timings = [], [], []
        for _ in range(args.requests):
            request_started = time.perf_counter()
            with args.image.open("rb") as stream:
                response = httpx.post(
                    f"{endpoint}/v1/analyze",
                    headers=headers,
                    files={"image": (args.image.name, stream, "image/png")},
                    data={
                        "context_json": VLMContext().model_dump_json(),
                        "policy_json": policy.model_dump_json(),
                        "prompt_version": "v1",
                        "request_metadata_json": json.dumps({"smoke": True}),
                    },
                    timeout=360,
                )
            response.raise_for_status()
            latencies.append((time.perf_counter() - request_started) * 1000)
            payload = response.json()
            results.append(payload["result"])
            runtime_timings.append(payload["timing"])
        after = httpx.get(f"{endpoint}/v1/meta", headers=headers, timeout=5).json()
        loaded_gpu_mib = gpu_memory_mib()
        report = {
            "offline": True,
            "process_start_ms": process_start_ms,
            "first_review_ms": latencies[0],
            "subsequent_review_ms": latencies[1:],
            "pid_stable": before["pid"] == after["pid"] == process.pid,
            "model_init_count": after["model_init_count"],
            "model_load_ms": runtime_timings[0].get("model_load_ms"),
            "gpu_memory_idle_mib": idle_gpu_mib,
            "gpu_memory_loaded_mib": loaded_gpu_mib,
            "structured_results": results,
            "before": before,
            "after": after,
        }
        (work / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if endpoint:
            try:
                httpx.post(
                    f"{endpoint}/_runtime/shutdown",
                    headers={"X-VisionGuard-Session": token},
                    timeout=5,
                )
            except Exception:
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
