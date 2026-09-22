"""Exercise a packaged VisionGuard runtime without using the source interpreter."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _request(url: str, *, token: str | None = None, timeout: float = 3) -> dict:
    headers = {"X-VisionGuard-Control": token} if token else {}
    request = urllib.request.Request(url, headers=headers, method="POST" if token else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _wait_status(path: Path, timeout: float, wanted: set[str]) -> dict:
    deadline = time.monotonic() + timeout
    latest: dict = {}
    while time.monotonic() < deadline:
        try:
            latest = _read_json(path)
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.25)
            continue
        if latest.get("state") in wanted:
            return latest
        time.sleep(0.25)
    raise TimeoutError(f"runtime status timeout; last status={latest}")


def _wait_url(url: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _request(url)
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"health timeout for {url}: {last_error}")


def _review(endpoint: str, image: Path, timeout: float) -> dict:
    boundary = f"----VisionGuard{secrets.token_hex(12)}"
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; filename="{image.name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode(),
            image.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        f"{endpoint}/v1/review?pipeline_mode=cascaded&include_details=false",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        type=Path,
        default=ROOT / "runtime-dist" / "visionguard-runtime" / "visionguard-runtime.exe",
    )
    parser.add_argument(
        "--models", type=Path, default=ROOT / "models" / "models-v1"
    )
    parser.add_argument(
        "--work-dir", type=Path, default=ROOT / "artifacts" / "runtime-smoke"
    )
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--image", type=Path, default=ROOT / "data" / "vlm_eval" / "safe.png")
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    models = args.models.resolve()
    work_dir = args.work_dir.resolve()
    if not runtime.is_file():
        raise FileNotFoundError(f"packaged runtime not found: {runtime}")
    work_dir.mkdir(parents=True, exist_ok=True)
    status_path = work_dir / "status.json"
    status_path.unlink(missing_ok=True)
    config_path = work_dir / "runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 0,
                "model_bundle_path": str(models),
                "user_data_dir": str(work_dir),
                "artifact_root": str(work_dir / "artifacts"),
                "log_root": str(work_dir / "logs"),
                "cache_root": str(work_dir / "cache"),
                "warmup_on_startup": False,
                "save_artifacts": False,
                "model_validation": "quick",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    token = secrets.token_urlsafe(32)
    environment = os.environ.copy()
    environment["VISIONGUARD_CONTROL_TOKEN"] = token
    environment["YOLO_AUTOINSTALL"] = "false"
    command = [str(runtime), "--config", str(config_path), "--status-file", str(status_path)]
    if args.validate_only:
        command.append("--validate-only")
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=work_dir, env=environment)
    try:
        status = _wait_status(status_path, args.timeout, {"ready", "failed"})
        if status["state"] == "failed":
            raise RuntimeError(
                f"{status.get('error_code')}: {status.get('error_message')}"
            )
        if args.validate_only:
            return_code = process.wait(timeout=10)
            if return_code:
                raise RuntimeError(f"validate-only runtime exited with {return_code}")
        else:
            endpoint = status["endpoint"]
            live = _wait_url(f"{endpoint}/health/live", args.timeout)
            ready = _wait_url(f"{endpoint}/health/ready", args.timeout)
            meta = _request(f"{endpoint}/v1/meta")
            review = (
                None
                if args.skip_review
                else _review(endpoint, args.image.resolve(), args.timeout)
            )
            review_result = review.get("result", review) if review is not None else None
            print(
                json.dumps(
                    {
                        "live": live,
                        "ready": ready,
                        "meta": meta,
                        "review": None
                        if review_result is None
                        else {
                            "request_id": review.get("request_id"),
                            "risk_level": review_result.get("risk_level"),
                            "vlm_called": (review.get("routing") or {}).get(
                                "call_vlm"
                            ),
                        },
                    },
                    ensure_ascii=False,
                )
            )
            _request(f"{endpoint}/_runtime/shutdown", token=token)
            process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    final = _read_json(status_path)
    print(
        json.dumps(
            {
                "runtime": str(runtime),
                "pid": final.get("pid"),
                "state": final.get("state"),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "model_bundle_version": final.get("model_bundle_version"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"packaged runtime smoke failed: {exc}", file=sys.stderr)
        raise
