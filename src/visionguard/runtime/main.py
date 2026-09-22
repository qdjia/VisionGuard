"""Stable executable entry point for the local VisionGuard AI runtime."""

from __future__ import annotations

import argparse
import hmac
import logging
import os
import platform
import shutil
import socket
from pathlib import Path
from typing import Any

import uvicorn

from visionguard.api import create_app
from visionguard.runtime import RUNTIME_API_VERSION, RUNTIME_VERSION
from visionguard.runtime.config import load_runtime_config, materialize_api_config
from visionguard.runtime.logging import configure_runtime_logging
from visionguard.runtime.manifest import (
    resolved_model_paths,
    validate_model_bundle,
)
from visionguard.runtime.paths import resolve_resources
from visionguard.runtime.status import StatusWriter

LOGGER = logging.getLogger(__name__)


class HardwarePreflightError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RuntimeControl:
    def __init__(self, token: str | None) -> None:
        self._token = token
        self._callback = None

    def attach(self, callback) -> None:
        self._callback = callback

    def authorized(self, client_host: str, supplied: str | None) -> bool:
        return bool(
            self._token
            and supplied
            and client_host in {"127.0.0.1", "::1"}
            and hmac.compare_digest(self._token, supplied)
        )

    def request_shutdown(self) -> None:
        if self._callback is not None:
            self._callback()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def _diagnostics() -> dict[str, Any]:
    values: dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
    }
    try:
        import torch

        values.update(
            {
                "torch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "cuda_version": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "gpu_memory_bytes": (
                    torch.cuda.get_device_properties(0).total_memory
                    if torch.cuda.is_available()
                    else None
                ),
            }
        )
    except Exception as exc:
        values["torch_error"] = type(exc).__name__
    return values


def _hardware_preflight(config) -> dict[str, Any]:
    """Fail before model construction when this release cannot run safely."""

    diagnostics = _diagnostics()
    diagnostics["runtime_edition"] = config.runtime_edition
    system = str(diagnostics.get("platform", "")).lower()
    architecture = str(diagnostics.get("architecture", "")).lower()
    if system != "windows" or architecture not in {"amd64", "x86_64"}:
        raise HardwarePreflightError(
            "PLATFORM_NOT_SUPPORTED",
            "This VisionGuard release requires 64-bit Windows.",
        )
    if config.runtime_edition == "gpu" and not diagnostics.get("cuda_available", False):
        raise HardwarePreflightError(
            "GPU_REQUIREMENT_NOT_SATISFIED",
            "The GPU edition requires an NVIDIA GPU and a compatible driver.",
        )
    config.user_data_dir.mkdir(parents=True, exist_ok=True)
    free_disk = shutil.disk_usage(config.user_data_dir).free
    diagnostics["user_data_free_disk_bytes"] = free_disk
    if free_disk < config.minimum_free_disk_bytes:
        raise HardwarePreflightError(
            "RUNTIME_DISK_SPACE_INSUFFICIENT",
            "Insufficient free disk space for VisionGuard runtime data.",
        )
    return diagnostics


def _offline_environment(cache_root: Path) -> None:
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[key] = "1"
    os.environ["HF_HOME"] = str(cache_root / "huggingface")
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root / "paddlex")
    os.environ["YOLO_AUTOINSTALL"] = "false"


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = StatusWriter(
        args.status_file,
        runtime_version=RUNTIME_VERSION,
        api_version=RUNTIME_API_VERSION,
    )
    try:
        config = load_runtime_config(args.config)
        resources = resolve_resources(config)
        configure_runtime_logging(
            resources.log_dir,
            level=config.log_level,
            max_bytes=config.log_max_bytes,
            backup_count=config.log_backup_count,
        )
        _offline_environment(resources.cache_dir)
        status.update(state="checking_hardware")
        diagnostics = _hardware_preflight(config)
        status.update(state="validating_models", diagnostics=diagnostics)
        manifest, validation = validate_model_bundle(
            resources.model_bundle_dir,
            runtime_version=RUNTIME_VERSION,
            full_hash=config.model_validation == "full",
        )
        status.update(
            model_bundle_version=validation.bundle_version,
            model_validation=validation.model_dump(mode="json"),
        )
        if manifest is None or validation.status != "ready":
            error_code = (
                "MODEL_BUNDLE_MISSING" if validation.status == "missing" else "MODEL_BUNDLE_INVALID"
            )
            status.update(
                state="failed",
                error_code=error_code,
                error_message="Model bundle validation failed.",
            )
            return 2
        if args.validate_only:
            status.update(state="ready")
            return 0

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((config.host, config.port))
        listener.listen(2048)
        assigned_port = listener.getsockname()[1]
        endpoint = f"http://{config.host}:{assigned_port}"
        status.update(state="launching", endpoint=endpoint)

        run_dir = resources.runtime_dir / f"run-{os.getpid()}"
        run_dir.mkdir(parents=True, exist_ok=True)
        api_config = materialize_api_config(
            config.model_copy(update={"port": assigned_port}),
            resource_root=resources.resource_root,
            run_dir=run_dir,
            bundle_version=manifest.bundle_version,
            model_paths=resolved_model_paths(resources.model_bundle_dir, manifest),
        )

        control_token = os.environ.pop("VISIONGUARD_CONTROL_TOKEN", None)
        control = RuntimeControl(control_token)

        def observe(phase: str, value: Any) -> None:
            if phase == "ready":
                status.update(state="ready", diagnostics={**_diagnostics(), "startup": value or {}})
            elif phase == "failed":
                status.update(
                    state="failed",
                    error_code="RUNTIME_NOT_READY",
                    error_message=f"Model initialization failed ({type(value).__name__}).",
                )
            elif phase == "stopping":
                status.update(state="stopping")
            else:
                status.update(state="waiting_for_ready")

        app = create_app(
            config=api_config,
            startup_observer=observe,
            runtime_control=control,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=config.host,
                port=0,
                log_level=config.log_level.lower(),
                log_config=None,
                access_log=False,
                workers=1,
            )
        )
        control.attach(lambda: setattr(server, "should_exit", True))
        status.update(state="waiting_for_ready")
        server.run(sockets=[listener])
        status.update(state="stopping")
        return 0
    except HardwarePreflightError as exc:
        LOGGER.error("VisionGuard hardware preflight failed: %s", exc.code)
        status.update(
            state="failed",
            error_code=exc.code,
            error_message=str(exc),
            diagnostics=_diagnostics(),
        )
        return 3
    except Exception as exc:
        logging.getLogger(__name__).exception("VisionGuard runtime failed")
        status.update(
            state="failed",
            error_code="RUNTIME_START_FAILED",
            error_message=f"Runtime startup failed ({type(exc).__name__}).",
        )
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
