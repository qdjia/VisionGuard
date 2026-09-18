"""Machine-readable contracts for performance experiments."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from visionguard.schemas.common import SchemaModel


class BatchMode(StrEnum):
    TRUE_BATCH = "true_batch"
    SEQUENTIAL = "sequential"
    MIXED = "mixed"


class BenchmarkStatus(StrEnum):
    SUCCESS = "success"
    OOM = "oom"
    ERROR = "error"


class MemoryMetrics(SchemaModel):
    gpu_available: bool = False
    allocated_mb: float | None = Field(default=None, ge=0)
    reserved_mb: float | None = Field(default=None, ge=0)
    peak_allocated_mb: float | None = Field(default=None, ge=0)
    cpu_rss_mb: float | None = Field(default=None, ge=0)


class LatencyStatistics(SchemaModel):
    count: int = Field(ge=0)
    mean_ms: float = Field(ge=0)
    median_ms: float = Field(ge=0)
    std_ms: float = Field(ge=0)
    min_ms: float = Field(ge=0)
    max_ms: float = Field(ge=0)
    percentiles_ms: dict[str, float] = Field(default_factory=dict)


class ModuleTimingBreakdown(SchemaModel):
    image_load_ms: float = Field(default=0, ge=0)
    detector_ms: float = Field(default=0, ge=0)
    ocr_ms: float = Field(default=0, ge=0)
    baseline_ms: float = Field(default=0, ge=0)
    routing_ms: float = Field(default=0, ge=0)
    context_build_ms: float = Field(default=0, ge=0)
    vlm_ms: float = Field(default=0, ge=0)
    fusion_ms: float = Field(default=0, ge=0)
    artifact_ms: float = Field(default=0, ge=0)


class BenchmarkRecord(SchemaModel):
    run_id: str = Field(min_length=1)
    benchmark_type: Literal["module", "pipeline"]
    target: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    batch_mode: BatchMode
    batch_size: int = Field(gt=0)
    sample_count: int = Field(gt=0)
    total_latency_ms: float = Field(ge=0)
    per_sample_latency_ms: float = Field(ge=0)
    throughput_images_per_second: float = Field(ge=0)
    memory: MemoryMetrics = Field(default_factory=MemoryMetrics)
    vlm_called: int = Field(default=0, ge=0)
    selected_vlm_count: int = Field(default=0, ge=0)
    vlm_call_rate: float = Field(default=0, ge=0, le=1)
    fast_path_sample_count: int = Field(default=0, ge=0)
    vlm_path_sample_count: int = Field(default=0, ge=0)
    fast_path_mean_latency_ms: float | None = Field(default=None, ge=0)
    vlm_path_mean_latency_ms: float | None = Field(default=None, ge=0)
    manual_review_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    module_timing: ModuleTimingBreakdown = Field(default_factory=ModuleTimingBreakdown)
    status: BenchmarkStatus
    error: str | None = None
    started_at: datetime


class EnvironmentSnapshot(SchemaModel):
    python: str
    os: str
    processor: str | None = None
    pytorch: str | None = None
    cuda: str | None = None
    cuda_available: bool
    gpu_name: str | None = None
    gpu_total_memory_mb: float | None = None
    transformers: str | None = None
    ultralytics: str | None = None
    paddleocr: str | None = None
    numpy: str


class BenchmarkSummary(SchemaModel):
    experiment_name: str
    target: str
    mode: str
    batch_mode: BatchMode
    batch_size: int = Field(gt=0)
    sample_count: int = Field(ge=0)
    successful_runs: int = Field(ge=0)
    oom_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    batch_latency: LatencyStatistics
    per_sample_latency: LatencyStatistics
    throughput_images_per_second: float = Field(ge=0)
    peak_gpu_memory_mb: float | None = Field(default=None, ge=0)
    vlm_call_rate: float = Field(ge=0, le=1)
    manual_review_rate: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    fast_path_mean_latency_ms: float | None = Field(default=None, ge=0)
    vlm_path_mean_latency_ms: float | None = Field(default=None, ge=0)
    module_mean_ms: ModuleTimingBreakdown
    module_share_percent: dict[str, float]
    startup_time_ms: float | None = Field(default=None, ge=0)
    startup_components_ms: dict[str, float] = Field(default_factory=dict)
    cold_inference_ms: float | None = Field(default=None, ge=0)
    environment: EnvironmentSnapshot
    dataset_kind: Literal["engineering", "formal"]
    limitations: list[str] = Field(default_factory=list)
