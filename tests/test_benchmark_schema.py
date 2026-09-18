import pytest
from pydantic import ValidationError

from visionguard.benchmarking.config import BenchmarkConfig
from visionguard.benchmarking.schemas import BatchMode, BenchmarkRecord, BenchmarkStatus


def test_benchmark_config_rejects_invalid_or_duplicate_batch_sizes() -> None:
    with pytest.raises(ValidationError):
        BenchmarkConfig(experiment_name="phase10_test", batch_sizes=[1, 1])
    with pytest.raises(ValidationError):
        BenchmarkConfig(experiment_name="phase10_test", batch_sizes=[0])


def test_record_exposes_batch_mode_and_memory_contract() -> None:
    record = BenchmarkRecord(
        run_id="run-1",
        benchmark_type="pipeline",
        target="pipeline",
        mode="cascaded",
        batch_mode=BatchMode.MIXED,
        batch_size=4,
        sample_count=4,
        total_latency_ms=100,
        per_sample_latency_ms=25,
        throughput_images_per_second=40,
        status=BenchmarkStatus.SUCCESS,
        started_at="2026-09-18T00:00:00Z",
    )

    assert record.batch_mode == "mixed"
    assert record.memory.peak_allocated_mb is None
