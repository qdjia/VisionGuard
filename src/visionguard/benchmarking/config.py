"""Strict, reproducible Phase 10 benchmark configuration."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from visionguard.config.models import StrictConfigModel


class BenchmarkRunCounts(StrictConfigModel):
    detector: int = Field(default=20, gt=0)
    ocr: int = Field(default=10, gt=0)
    baseline: int = Field(default=50, gt=0)
    vlm: int = Field(default=3, gt=0)
    fusion: int = Field(default=50, gt=0)
    pipeline: int = Field(default=5, gt=0)


class BenchmarkConfig(StrictConfigModel):
    experiment_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{4,79}$")
    warmup_runs: int = Field(default=2, ge=0)
    measured_runs: int = Field(default=5, gt=0)
    module_runs: BenchmarkRunCounts = Field(default_factory=BenchmarkRunCounts)
    batch_sizes: list[int] = Field(default_factory=lambda: [1, 2, 4, 8])
    percentiles: list[int] = Field(default_factory=lambda: [50, 90, 95, 99])
    synchronize_cuda: bool = True
    measure_gpu_memory: bool = True
    measure_cpu_memory: bool = False
    save_raw_records: bool = True
    pipeline_modes: list[Literal["full", "cascaded"]] = Field(
        default_factory=lambda: ["full", "cascaded"]
    )
    include_cold_start: bool = True
    shuffle_samples: bool = True
    seed: int = 42
    save_pipeline_artifacts: bool = False
    dataset_kind: Literal["engineering", "formal"] = "engineering"
    output_root: Path = Path("artifacts/benchmarks")

    @model_validator(mode="after")
    def validate_lists(self) -> "BenchmarkConfig":
        if not self.batch_sizes or any(size <= 0 for size in self.batch_sizes):
            raise ValueError("batch_sizes must contain positive integers")
        if len(set(self.batch_sizes)) != len(self.batch_sizes):
            raise ValueError("batch_sizes must not contain duplicates")
        if not self.percentiles or any(value <= 0 or value >= 100 for value in self.percentiles):
            raise ValueError("percentiles must be between 0 and 100")
        if len(set(self.pipeline_modes)) != len(self.pipeline_modes):
            raise ValueError("pipeline_modes must not contain duplicates")
        return self


def load_benchmark_config(path: str | Path) -> BenchmarkConfig:
    source = Path(path).expanduser().resolve()
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("benchmark"), dict):
        raise ValueError(f"benchmark config must contain a mapping named 'benchmark': {source}")
    data = dict(raw["benchmark"])
    if "output_root" in data:
        data["output_root"] = (source.parent / data["output_root"]).resolve()
    return BenchmarkConfig.model_validate(data)
