"""Application-scoped service container and FastAPI dependency access."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from visionguard.api.config import APIConfig
from visionguard.api.errors import ServiceNotReadyError

LOGGER = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    config: APIConfig
    full_pipeline: Any
    cascaded_pipeline: Any
    semaphore: asyncio.Semaphore
    startup_info: dict[str, Any] = field(default_factory=dict)
    initialization_count: int = 1
    ready: bool = False
    accepting_requests: bool = False
    active_tasks: set[asyncio.Task] = field(default_factory=set)
    warmup_operation: Callable[[], Any] | None = None

    @property
    def detector(self):
        return getattr(self.full_pipeline, "detector", None)

    @property
    def ocr(self):
        return getattr(self.full_pipeline, "ocr_engine", None)

    @property
    def baseline(self):
        return getattr(self.full_pipeline, "text_baseline", None)

    @property
    def vlm(self):
        return getattr(self.full_pipeline, "vlm_provider", None)

    @property
    def moderation_policy(self):
        return getattr(self.full_pipeline, "policy", None)

    @property
    def routing_policy(self):
        return getattr(self.cascaded_pipeline, "routing_policy", None)

    @property
    def fusion_engine(self):
        return getattr(self.full_pipeline, "fusion_engine", None)

    def pipeline_for(self, mode: str):
        if mode == "full":
            return self.full_pipeline
        if mode == "cascaded":
            return self.cascaded_pipeline
        raise ValueError(f"unsupported pipeline mode: {mode}")

    def components(self) -> dict[str, bool]:
        full = self.full_pipeline
        cascaded = self.cascaded_pipeline
        return {
            "detector": self.detector is not None,
            "ocr": self.ocr is not None,
            "baseline": self.baseline is not None,
            "vlm": self.vlm is not None and bool(getattr(self.vlm, "available", True)),
            "routing": self.routing_policy is not None,
            "fusion": self.fusion_engine is not None,
            "full_pipeline": full is not None,
            "cascaded_pipeline": cascaded is not None,
        }

    def capabilities(self) -> dict[str, bool]:
        components = self.components()
        core_ready = all(
            components[name] for name in ("detector", "ocr", "baseline", "routing", "fusion")
        )
        vlm_available = components["vlm"] and bool(getattr(self.vlm, "available", True))
        return {
            "core_ready": core_ready,
            "vlm_available": vlm_available,
            "fast_review": core_ready,
            "deep_review": core_ready and vlm_available,
        }

    def track(self, task: asyncio.Task) -> None:
        self.active_tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task) -> None:
        self.active_tasks.discard(task)
        if task.cancelled():
            return
        try:
            error = task.exception()
            if error is not None:
                LOGGER.error(
                    "background inference task failed",
                    exc_info=(type(error), error, error.__traceback__),
                )
        except Exception:
            LOGGER.exception("failed to retrieve background inference task status")


def get_container(request: Request) -> ServiceContainer:
    container = getattr(request.app.state, "services", None)
    if container is None or not container.ready or not container.accepting_requests:
        raise ServiceNotReadyError()
    return container
