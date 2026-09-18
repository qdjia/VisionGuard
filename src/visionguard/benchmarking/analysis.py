"""Cross-run comparisons and bottleneck identification."""

from visionguard.benchmarking.schemas import BenchmarkSummary


def identify_bottleneck(summary: BenchmarkSummary) -> tuple[str | None, float]:
    if not summary.module_share_percent:
        return None, 0.0
    name, share = max(summary.module_share_percent.items(), key=lambda item: item[1])
    return (name, share) if share > 0 else (None, 0.0)


def compare_summaries(
    full: BenchmarkSummary, cascaded: BenchmarkSummary
) -> dict[str, float | None]:
    if full.sample_count == 0 or cascaded.sample_count == 0:
        raise ValueError("both summaries must contain successful samples")

    def reduction(original: float, current: float) -> float | None:
        return (original - current) / original * 100 if original else None

    return {
        "mean_latency_reduction_percent": reduction(
            full.batch_latency.mean_ms, cascaded.batch_latency.mean_ms
        ),
        "p95_latency_reduction_percent": reduction(
            full.batch_latency.percentiles_ms.get("p95", 0),
            cascaded.batch_latency.percentiles_ms.get("p95", 0),
        ),
        "throughput_change_percent": (
            (cascaded.throughput_images_per_second - full.throughput_images_per_second)
            / full.throughput_images_per_second
            * 100
            if full.throughput_images_per_second
            else None
        ),
        "full_vlm_call_rate": full.vlm_call_rate,
        "cascaded_vlm_call_rate": cascaded.vlm_call_rate,
        "peak_gpu_memory_change_mb": (
            cascaded.peak_gpu_memory_mb - full.peak_gpu_memory_mb
            if full.peak_gpu_memory_mb is not None and cascaded.peak_gpu_memory_mb is not None
            else None
        ),
    }
