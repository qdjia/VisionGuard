"""Executable entry point for the optional loopback Advanced AI runtime."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path

import uvicorn

from visionguard.vlm_runtime import VLM_API_VERSION, VLM_RUNTIME_VERSION
from visionguard.vlm_runtime.app import create_vlm_app
from visionguard.vlm_runtime.config import load_vlm_runtime_config
from visionguard.vlm_runtime.service import LazyVLMService


def _write_status(path: Path, **values) -> None:
    payload = {
        "api_version": VLM_API_VERSION,
        "runtime_version": VLM_RUNTIME_VERSION,
        "pid": os.getpid(),
        **values,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _validate_model_contract(config) -> None:
    manifest_path = config.model_path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("VLM_MODEL_INVALID: manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("bundle_type") != "vlm":
        raise ValueError("VLM_MODEL_INVALID: bundle_type must be vlm")
    if manifest.get("bundle_version") != config.model_bundle_version:
        raise ValueError("VLM_VERSION_INCOMPATIBLE: model bundle version mismatch")
    if int(manifest.get("compatible_api_major", -1)) != VLM_API_VERSION:
        raise ValueError("VLM_CONTRACT_INCOMPATIBLE: API major mismatch")
    if config.prompt_version not in manifest.get("compatible_prompt_versions", []):
        raise ValueError("VLM_VERSION_INCOMPATIBLE: prompt version mismatch")


def run(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    args = parser.parse_args(argv)
    token = os.environ.pop("VISIONGUARD_VLM_SESSION_TOKEN", "")
    try:
        config = load_vlm_runtime_config(args.config)
        if not config.model_path.exists():
            _write_status(args.status_file, state="failed", error_code="VLM_MODEL_MISSING")
            return 2
        _validate_model_contract(config)
        service = LazyVLMService(config)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((config.host, config.port))
        listener.listen(128)
        endpoint = f"http://{config.host}:{listener.getsockname()[1]}"
        holder = {}
        app = create_vlm_app(
            config,
            service,
            token,
            shutdown=lambda: setattr(holder["server"], "should_exit", True),
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=config.host,
                port=0,
                workers=1,
                access_log=False,
                log_config=None,
            )
        )
        holder["server"] = server
        _write_status(
            args.status_file,
            state="installed",
            endpoint=endpoint,
            model_bundle_version=config.model_bundle_version,
        )
        server.run(sockets=[listener])
        _write_status(args.status_file, state="stopped", endpoint=endpoint)
        return 0
    except Exception as exc:
        _write_status(
            args.status_file,
            state="failed",
            error_code="VLM_RUNTIME_START_FAILED",
            error_message=f"{type(exc).__name__}: {str(exc)[:240]}",
        )
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
