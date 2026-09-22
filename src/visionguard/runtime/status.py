"""Atomic runtime-to-desktop startup handshake and diagnostics."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import Field

from visionguard.config.models import StrictConfigModel

RuntimePhase = Literal[
    "starting",
    "checking_hardware",
    "validating_models",
    "launching",
    "waiting_for_ready",
    "ready",
    "failed",
    "stopping",
]


class RuntimeStatus(StrictConfigModel):
    state: RuntimePhase
    pid: int = Field(gt=0)
    endpoint: str | None = None
    runtime_version: str
    api_version: str
    model_bundle_version: str | None = None
    model_validation: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    elapsed_ms: float = Field(ge=0)
    updated_at: datetime


class StatusWriter:
    def __init__(self, path: str | Path, *, runtime_version: str, api_version: str) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_version = runtime_version
        self.api_version = api_version
        self.started = perf_counter()
        self._lock = threading.Lock()
        self._values: dict[str, Any] = {
            "state": "starting",
            "pid": os.getpid(),
            "endpoint": None,
            "runtime_version": runtime_version,
            "api_version": api_version,
            "model_bundle_version": None,
            "model_validation": None,
            "diagnostics": {},
            "error_code": None,
            "error_message": None,
        }
        self.update(state="starting")

    def update(self, **values: Any) -> RuntimeStatus:
        with self._lock:
            self._values.update(values)
            payload = RuntimeStatus(
                **self._values,
                elapsed_ms=(perf_counter() - self.started) * 1000,
                updated_at=datetime.now(UTC),
            )
            temporary = self.path.with_suffix(self.path.suffix + f".{os.getpid()}.tmp")
            temporary.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(self.path)
            return payload
