#!/usr/bin/env python
"""Sweep configured batch sizes without aborting the sweep on CUDA OOM."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", default="configs/benchmark.yaml")
    parser.add_argument("--pipeline-mode", choices=("full", "cascaded"), required=True)
    parser.add_argument("--output", required=True)
    add_model_arguments(parser)
    args = parser.parse_args()
    output = ensure_new_output(args.output)
    output.mkdir(parents=True)
    config = load_benchmark_config(args.config)
    pipeline, startup_ms, startup_components = build_one(args, args.pipeline_mode)
    operation = BatchReviewRunner(pipeline).run
    samples = load_manifest(args.manifest)
    summaries = []
    for index, batch_size in enumerate(config.batch_sizes):
        run_config = config.model_copy(
            update={"include_cold_start": config.include_cold_start and index == 0}
        )
        benchmark = BenchmarkRunner(
            run_config,
            startup_time_ms=startup_ms,
            startup_components_ms=startup_components,
        )
        records, cold_ms = benchmark.benchmark_operation(
            target="pipeline",
            mode=args.pipeline_mode,
            batch_mode=BatchMode.MIXED,
            batch_size=batch_size,
            samples=samples,
            operation=operation,
            measured_runs=config.module_runs.pipeline,
        )
        summary = benchmark.summarize(records, cold_inference_ms=cold_ms)
        benchmark.save(output / f"batch_{batch_size}", records, summary)
        summaries.append(summary)
        if summary.oom_runs:
            print(f"batch_size={batch_size}: OOM recorded; continuing sweep")
    generate_performance_report(summaries, output / "performance_report.md")
    print(f"saved {len(summaries)} batch-size summaries to {output}")


if __name__ == "__main__":
    main()
