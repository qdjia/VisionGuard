#!/usr/bin/env python
"""Benchmark YOLO, OCR, Baseline, VLM, and Fusion independently."""

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
from visionguard.utils.image import load_image
from visionguard.vlm import build_context


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--config", default="configs/benchmark.yaml")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument(
        "--modules",
        nargs="+",
        choices=("detector", "ocr", "baseline", "vlm", "fusion"),
        default=("detector", "ocr", "baseline", "vlm", "fusion"),
    )
    parser.add_argument("--output", required=True)
    add_model_arguments(parser)
    args = parser.parse_args()
    output = ensure_new_output(args.output)
    output.mkdir(parents=True)
    config = load_benchmark_config(args.config)
    pipeline, startup_ms, startup_components = build_one(args, "cascaded")
    paths = load_manifest(args.manifest)
    images = [load_image(path) for path in paths]

    # Preparation is deliberately outside every measured module boundary.
    prepared = BatchReviewRunner(pipeline).run(paths)
    texts = [item.ocr.full_text if item.ocr else "" for item in prepared]
    contexts = [build_context(item.detection, item.ocr, item.baseline) for item in prepared]
    fusion_signals = [item.fusion.signals for item in prepared]
    operations = {
        "detector": (
            images,
            lambda batch: pipeline.detector.predict_batch(list(batch)),
            BatchMode.TRUE_BATCH,
        ),
        "ocr": (
            images,
            lambda batch: [pipeline.ocr_engine.recognize(image) for image in batch],
            BatchMode.SEQUENTIAL,
        ),
        "baseline": (
            texts,
            lambda batch: pipeline.text_baseline.predict_batch(list(batch)),
            BatchMode.TRUE_BATCH,
        ),
        "vlm": (
            list(zip(images, contexts, strict=True)),
            lambda batch: [
                pipeline.vlm_provider.analyze(image, context, pipeline.policy)
                for image, context in batch
            ],
            BatchMode.SEQUENTIAL,
        ),
        "fusion": (
            fusion_signals,
            lambda batch: [pipeline.fusion_engine.decide(signals) for signals in batch],
            BatchMode.SEQUENTIAL,
        ),
    }
    summaries = []
    for module in args.modules:
        samples, operation, batch_mode = operations[module]
        # Upstream preparation has already warmed the shared models, so reporting a
        # module "cold" request here would be misleading. Startup remains separate.
        benchmark = BenchmarkRunner(
            config.model_copy(update={"include_cold_start": False}),
            startup_time_ms=startup_ms,
            startup_components_ms=startup_components,
        )
        records, cold_ms = benchmark.benchmark_operation(
            target=module,
            mode="module",
            batch_mode=batch_mode,
            batch_size=args.batch_size,
            samples=samples,
            operation=operation,
            measured_runs=getattr(config.module_runs, module),
        )
        summary = benchmark.summarize(records, cold_inference_ms=cold_ms)
        benchmark.save(output / module, records, summary)
        summaries.append(summary)
    generate_performance_report(summaries, output / "performance_report.md")
    print(f"saved {len(summaries)} module benchmarks to {output}")


if __name__ == "__main__":
    main()
