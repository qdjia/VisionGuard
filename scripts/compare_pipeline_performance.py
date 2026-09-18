#!/usr/bin/env python
"""Fair Full versus Cascaded comparison over shared initialized models."""

import argparse
import json

from visionguard.benchmarking import (
    BatchMode,
    BatchReviewRunner,
    BenchmarkRunner,
    compare_summaries,
    generate_performance_report,
    load_benchmark_config,
    load_manifest,
)
from visionguard.benchmarking.bootstrap import add_model_arguments, build_pair, ensure_new_output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", default="configs/benchmark.yaml")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output", required=True)
    add_model_arguments(parser)
    args = parser.parse_args()
    output = ensure_new_output(args.output)
    output.mkdir(parents=True)
    config = load_benchmark_config(args.config)
    samples = load_manifest(args.manifest)
    full, cascaded, startup_ms, startup_components = build_pair(args)
    summaries = []
    for index, (mode, pipeline) in enumerate((("full", full), ("cascaded", cascaded))):
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
            mode=mode,
            batch_mode=BatchMode.MIXED,
            batch_size=args.batch_size,
            samples=samples,
            operation=BatchReviewRunner(pipeline).run,
            measured_runs=config.module_runs.pipeline,
        )
        summary = benchmark.summarize(records, cold_inference_ms=cold_ms)
        benchmark.save(output / mode, records, summary)
        summaries.append(summary)
    comparison = compare_summaries(summaries[0], summaries[1])
    (output / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    generate_performance_report(summaries, output / "performance_report.md")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
