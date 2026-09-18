"""Benchmark-only timing boundaries and reproducible environment snapshots."""

import importlib.metadata
import platform
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from visionguard.benchmarking.memory import (
    memory_metrics,
    reset_peak_gpu_memory,
    synchronize_cuda,
)
from visionguard.benchmarking.schemas import EnvironmentSnapshot, MemoryMetrics


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def environment_snapshot() -> EnvironmentSnapshot:
    torch_version = cuda_version = gpu_name = None
    gpu_total = None
    cuda_is_available = False
    try:
        import torch

        torch_version = torch.__version__
        cuda_version = torch.version.cuda
        cuda_is_available = torch.cuda.is_available()
        if cuda_is_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
    except ImportError:
        pass
    return EnvironmentSnapshot(
        python=platform.python_version(),
        os=f"{platform.system()} {platform.release()}",
        processor=platform.processor() or None,
        pytorch=torch_version,
        cuda=cuda_version,
        cuda_available=cuda_is_available,
        gpu_name=gpu_name,
        gpu_total_memory_mb=gpu_total,
        transformers=_version("transformers"),
        ultralytics=_version("ultralytics"),
        paddleocr=_version("paddleocr"),
        numpy=np.__version__,
    )


@dataclass
class ProfileResult:
    elapsed_ms: float = 0.0
    memory: MemoryMetrics | None = None


@contextmanager
def profile_operation(*, synchronize: bool, measure_gpu: bool, measure_cpu: bool):
    """Synchronize only around benchmark timing; never changes production execution."""

    result = ProfileResult()
    reset_peak_gpu_memory(measure_gpu)
    synchronize_cuda(synchronize)
    started = perf_counter()
    try:
        yield result
    finally:
        synchronize_cuda(synchronize)
        result.elapsed_ms = (perf_counter() - started) * 1000
        result.memory = memory_metrics(measure_gpu=measure_gpu, measure_cpu=measure_cpu)
