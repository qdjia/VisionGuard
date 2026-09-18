"""Numerically stable benchmark statistics built on NumPy."""

import numpy as np

from visionguard.benchmarking.schemas import LatencyStatistics


def latency_statistics(
    values_ms: list[float], percentiles: list[int] | tuple[int, ...] = (50, 90, 95, 99)
) -> LatencyStatistics:
    if not values_ms:
        return LatencyStatistics(
            count=0,
            mean_ms=0,
            median_ms=0,
            std_ms=0,
            min_ms=0,
            max_ms=0,
            percentiles_ms={f"p{value}": 0 for value in percentiles},
        )
    values = np.asarray(values_ms, dtype=np.float64)
    calculated = np.percentile(values, percentiles)
    return LatencyStatistics(
        count=len(values_ms),
        mean_ms=float(np.mean(values)),
        median_ms=float(np.median(values)),
        std_ms=float(np.std(values)),
        min_ms=float(np.min(values)),
        max_ms=float(np.max(values)),
        percentiles_ms={
            f"p{percentile}": float(result)
            for percentile, result in zip(percentiles, calculated, strict=True)
        },
    )


def throughput(sample_count: int, elapsed_ms: float) -> float:
    if sample_count < 0 or elapsed_ms < 0:
        raise ValueError("sample_count and elapsed_ms must be non-negative")
    return sample_count / max(elapsed_ms / 1000.0, 1e-9)
