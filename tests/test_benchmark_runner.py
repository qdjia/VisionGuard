from pathlib import Path

import pytest

from visionguard.benchmarking import BatchMode, BenchmarkConfig, BenchmarkRunner


def config(**updates) -> BenchmarkConfig:
    values = {
        "experiment_name": "phase10_test",
        "warmup_runs": 0,
        "measured_runs": 2,
        "batch_sizes": [1, 2],
        "include_cold_start": False,
        "measure_gpu_memory": False,
    }
    values.update(updates)
    return BenchmarkConfig(**values)


def test_runner_preserves_batch_order_and_writes_non_overwriting_artifacts(tmp_path: Path) -> None:
    observed = []

    def operation(batch):
        observed.append(list(batch))
        return []

    runner = BenchmarkRunner(config())
    records, cold = runner.benchmark_operation(
        target="detector",
        mode="module",
        batch_mode=BatchMode.TRUE_BATCH,
        batch_size=2,
        samples=["a", "b"],
        operation=operation,
    )
    summary = runner.summarize(records, cold_inference_ms=cold)
    output = runner.save(tmp_path / "run", records, summary)

    assert len(observed) == 2
    assert observed[0] == observed[1]
    assert (output / "records.jsonl").is_file()
    assert (output / "summary.json").is_file()
    assert (output / "summary.csv").is_file()
    with pytest.raises(FileExistsError):
        runner.save(output, records, summary)


def test_cuda_oom_is_recorded_and_does_not_abort_remaining_runs() -> None:
    calls = 0

    def operation(_batch):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("CUDA out of memory")
        return []

    runner = BenchmarkRunner(config())
    records, _ = runner.benchmark_operation(
        target="detector",
        mode="module",
        batch_mode=BatchMode.TRUE_BATCH,
        batch_size=1,
        samples=["a"],
        operation=operation,
    )

    assert [record.status for record in records] == ["oom", "success"]
