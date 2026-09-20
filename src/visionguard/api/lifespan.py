"""One-time model bootstrap, warmup, and graceful resource release."""

from __future__ import annotations

import asyncio
import gc
import inspect
import logging
from contextlib import asynccontextmanager
from functools import partial
from time import perf_counter

import anyio
import numpy as np

from visionguard.api.config import APIConfig
from visionguard.api.dependencies import ServiceContainer
from visionguard.core.logging import configure_logging
from visionguard.pipeline.runner import build_pipeline_pair

LOGGER = logging.getLogger(__name__)


def build_service_container(config: APIConfig) -> ServiceContainer:
    """Initialize all heavy dependencies once and share them across both modes."""
    started = perf_counter()
    component_timings: dict[str, float] = {}
    paths = config.services
    full, cascaded = build_pipeline_pair(
        full_pipeline_config=paths.full_pipeline_config,
        cascaded_pipeline_config=paths.cascaded_pipeline_config,
        routing_config=paths.routing_config,
        detector_config=paths.detector_config,
        ocr_config=paths.ocr_config,
        baseline_config=paths.baseline_config,
        vlm_config=paths.vlm_config,
        policy=paths.moderation_policy,
        fusion_config=paths.fusion_config,
        startup_timings=component_timings,
    )
    dummy = np.zeros((112, 112, 3), dtype=np.uint8)
    return ServiceContainer(
        config=config,
        full_pipeline=full,
        cascaded_pipeline=cascaded,
        semaphore=asyncio.Semaphore(config.api.max_concurrent_inference),
        startup_info={
            "model_initialization_ms": (perf_counter() - started) * 1000,
            "component_initialization_ms": component_timings,
        },
        warmup_operation=partial(full.run, dummy, save_artifacts=False),
    )


async def _create_container(factory, config: APIConfig) -> ServiceContainer:
    if inspect.iscoroutinefunction(factory):
        return await factory(config)
    return await anyio.to_thread.run_sync(factory, config)


async def shutdown_container(container: ServiceContainer) -> None:
    container.accepting_requests = False
    container.ready = False
    pending = list(container.active_tasks)
    if pending:
        done, remaining = await asyncio.wait(
            pending,
            timeout=container.config.api.shutdown_grace_seconds,
        )
        LOGGER.info("shutdown inference tasks completed=%d pending=%d", len(done), len(remaining))
    else:
        remaining = set()
    if remaining:
        LOGGER.warning("shutdown grace period elapsed with %d inference task(s)", len(remaining))
        return
    container.full_pipeline = None
    container.cascaded_pipeline = None
    container.warmup_operation = None
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        LOGGER.info("PyTorch unavailable during shutdown cleanup")
    LOGGER.info("VisionGuard service resources released")


def create_lifespan(config: APIConfig, container_factory=build_service_container):
    @asynccontextmanager
    async def lifespan(app):
        LOGGER.info("VisionGuard service startup started")
        container = await _create_container(container_factory, config)
        app.state.services = container
        try:
            # Some ML runtimes reconfigure the root logger while loading. Restore
            # application logging after bootstrap so request/run correlation remains visible.
            configure_logging()
            logging.getLogger("visionguard").disabled = False
            logging.getLogger("visionguard").setLevel(logging.INFO)
            if config.api.warmup_on_startup and container.warmup_operation is not None:
                started = perf_counter()
                await anyio.to_thread.run_sync(container.warmup_operation)
                container.startup_info["service_warmup_ms"] = (perf_counter() - started) * 1000
            container.ready = True
            container.accepting_requests = True
            LOGGER.info(
                "VisionGuard service ready init_count=%d concurrency=%d",
                container.initialization_count,
                config.api.max_concurrent_inference,
            )
            yield
        finally:
            await shutdown_container(container)

    return lifespan
