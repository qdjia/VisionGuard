import pytest

from visionguard.benchmarking.statistics import latency_statistics, throughput


def test_statistics_and_percentiles_use_numpy_definition() -> None:
    result = latency_statistics([10, 20, 30, 40], [50, 90, 95, 99])

    assert result.mean_ms == 25
    assert result.median_ms == 25
    assert result.min_ms == 10
    assert result.max_ms == 40
    assert result.percentiles_ms["p95"] == pytest.approx(38.5)


def test_throughput_uses_samples_over_total_seconds() -> None:
    assert throughput(8, 2000) == 4
    with pytest.raises(ValueError):
        throughput(-1, 1)
