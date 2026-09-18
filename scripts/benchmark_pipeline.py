#!/usr/bin/env python
"""Benchmark one Full or Cascaded pipeline in stage-wise mixed batches."""

import argparse

from visionguard.benchmarking import (
    BatchMode,
    BatchReviewRunner,
    BenchmarkRunner,
    generate_performance_report,
    load_benchmark_config,
    load_manifest,
)
from visionguard.benchmarking.bootstrap import add_model_arguments, build_one, ensure_new_output
from visionguard.pipeline.artifacts import PipelineArtifactStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", default="configs/benchmark.yaml")
    parser.add_argument("--pipeline-mode", choices=("full", "cascaded"), required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output", required=True)
    add_model_arguments(parser)
    args = parser.parse_args()
    output = ensure_new_output(args.output)
    config = load_benchmark_config(args.config)
    pipeline, startup_ms, startup_components = build_one(args, args.pipeline_mode)
    if config.save_pipeline_artifacts:
        request_artifacts = output.parent / f"{output.name}_request_artifacts"
        if request_artifacts.exists():
            raise FileExistsError(f"request artifact output already exists: {request_artifacts}")
        pipeline.config = pipeline.config.model_copy(
            update={"save_artifacts": True, "artifact_root": request_artifacts}
        )
        pipeline.artifact_store = PipelineArtifactStore(pipeline.config)

        def operation(batch):
            return [pipeline.run(source) for source in batch]

        batch_mode = BatchMode.SEQUENTIAL
    else:
        operation = BatchReviewRunner(pipeline).run
        batch_mode = BatchMode.MIXED
    benchmark = BenchmarkRunner(
        config,
        startup_time_ms=startup_ms,
        startup_components_ms=startup_components,
    )
    records, cold_ms = benchmark.benchmark_operation(
        target="pipeline",
        mode=args.pipeline_mode,
        batch_mode=batch_mode,
        batch_size=args.batch_size,
        samples=load_manifest(args.manifest),
        operation=operation,
        measured_runs=config.module_runs.pipeline,
    )
    summary = benchmark.summarize(records, cold_inference_ms=cold_ms)
    benchmark.save(output, records, summary)
    generate_performance_report([summary], output / "performance_report.md")
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
