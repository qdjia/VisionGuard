"""Generate portable JSON/CSV-backed Markdown performance reports."""

import json
from pathlib import Path

from visionguard.benchmarking.analysis import identify_bottleneck
from visionguard.benchmarking.schemas import BenchmarkSummary


def load_summaries(root: str | Path) -> list[BenchmarkSummary]:
    root = Path(root).expanduser().resolve()
    summaries = []
    for path in sorted(root.rglob("summary.json")):
        summaries.append(BenchmarkSummary.model_validate_json(path.read_text(encoding="utf-8")))
    return summaries


def generate_performance_report(summaries: list[BenchmarkSummary], output: str | Path) -> Path:
    if not summaries:
        raise ValueError("at least one benchmark summary is required")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"performance report already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = summaries[0].environment
    lines = [
        "# VisionGuard Performance Report",
        "",
        "> Results apply only to the recorded hardware, software stack, and engineering dataset.",
        "",
        "## Environment",
        "",
        f"- OS: {environment.os}",
        f"- Python: {environment.python}",
        f"- PyTorch: {environment.pytorch or 'N/A'}",
        f"- CUDA: {environment.cuda or 'N/A'}",
        f"- GPU: {environment.gpu_name or 'N/A'}",
        f"- GPU memory: {environment.gpu_total_memory_mb or 'N/A'} MB",
        "",
        "## Results",
        "",
        (
            "| Target | Mode | Batch | Batch mode | Mean ms | P50 | P95 | P99 | "
            "images/s | VLM rate | Peak GPU MB |"
        ),
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        percentiles = summary.batch_latency.percentiles_ms
        lines.append(
            "| "
            + " | ".join(
                [
                    summary.target,
                    summary.mode,
                    str(summary.batch_size),
                    str(summary.batch_mode),
                    f"{summary.batch_latency.mean_ms:.2f}",
                    f"{percentiles.get('p50', 0):.2f}",
                    f"{percentiles.get('p95', 0):.2f}",
                    f"{percentiles.get('p99', 0):.2f}",
                    f"{summary.throughput_images_per_second:.3f}",
                    f"{summary.vlm_call_rate:.2%}",
                    (
                        f"{summary.peak_gpu_memory_mb:.1f}"
                        if summary.peak_gpu_memory_mb is not None
                        else "N/A"
                    ),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Module breakdown", ""])
    for summary in summaries:
        bottleneck, share = identify_bottleneck(summary)
        lines.append(
            f"- {summary.mode}, batch {summary.batch_size}: bottleneck "
            f"`{bottleneck or 'N/A'}` ({share:.1f}%)."
        )
    lines.extend(
        [
            "",
            "## Cold and warm execution",
            "",
        ]
    )
    for summary in summaries:
        startup = (
            f"{summary.startup_time_ms:.2f} ms" if summary.startup_time_ms is not None else "N/A"
        )
        cold = (
            f"{summary.cold_inference_ms:.2f} ms"
            if summary.cold_inference_ms is not None
            else "N/A"
        )
        lines.append(
            f"- {summary.mode}, batch {summary.batch_size}: startup={startup}, "
            f"cold inference={cold}, "
            f"warm mean={summary.batch_latency.mean_ms:.2f} ms."
        )
        if summary.startup_components_ms:
            details = ", ".join(
                f"{name}={value:.2f} ms" for name, value in summary.startup_components_ms.items()
            )
            lines.append(f"  - Startup components: {details}.")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            (
                "- Pipeline batching is mixed: YOLO and Baseline are true batch; "
                "OCR and VLM are sequential."
            ),
            (
                "- CUDA synchronization is enabled only around benchmark timing and changes "
                "asynchronous execution behavior."
            ),
            (
                "- Peak allocated, currently allocated, and reserved GPU memory have "
                "different meanings."
            ),
            "- This report measures engineering performance, not moderation accuracy.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def write_comparison_json(value: dict, output: str | Path) -> Path:
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return output
