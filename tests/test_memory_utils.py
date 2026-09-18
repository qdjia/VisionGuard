from visionguard.benchmarking.memory import is_cuda_oom, memory_metrics


def test_memory_schema_is_valid_without_cuda() -> None:
    result = memory_metrics(measure_gpu=False, measure_cpu=False)

    assert result.gpu_available is False
    assert result.allocated_mb is None
    assert result.cpu_rss_mb is None


def test_only_cuda_oom_message_is_classified_as_oom() -> None:
    assert is_cuda_oom(RuntimeError("CUDA out of memory")) is True
    assert is_cuda_oom(RuntimeError("ordinary failure")) is False
