"""Optional CUDA and process-memory profiling without hard runtime dependencies."""

from visionguard.benchmarking.schemas import MemoryMetrics

_MB = 1024 * 1024


def _torch():
    try:
        import torch
    except ImportError:
        return None
    return torch


def cuda_available() -> bool:
    torch = _torch()
    return bool(torch is not None and torch.cuda.is_available())


def synchronize_cuda(enabled: bool = True) -> None:
    if enabled and cuda_available():
        _torch().cuda.synchronize()


def reset_peak_gpu_memory(enabled: bool = True) -> None:
    if enabled and cuda_available():
        torch = _torch()
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()


def empty_cuda_cache() -> None:
    if cuda_available():
        torch = _torch()
        torch.cuda.empty_cache()


def memory_metrics(*, measure_gpu: bool, measure_cpu: bool) -> MemoryMetrics:
    allocated = reserved = peak = None
    available = measure_gpu and cuda_available()
    if available:
        torch = _torch()
        allocated = torch.cuda.memory_allocated() / _MB
        reserved = torch.cuda.memory_reserved() / _MB
        peak = torch.cuda.max_memory_allocated() / _MB
    cpu_rss = None
    if measure_cpu:
        try:
            import os

            import psutil

            cpu_rss = psutil.Process(os.getpid()).memory_info().rss / _MB
        except ImportError:
            cpu_rss = None
    return MemoryMetrics(
        gpu_available=available,
        allocated_mb=allocated,
        reserved_mb=reserved,
        peak_allocated_mb=peak,
        cpu_rss_mb=cpu_rss,
    )


def is_cuda_oom(error: BaseException) -> bool:
    torch = _torch()
    if torch is not None and isinstance(error, getattr(torch.cuda, "OutOfMemoryError", ())):
        return True
    message = str(error).lower()
    return "cuda" in message and "out of memory" in message
