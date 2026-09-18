"""Human-readable taxonomy summaries and error-analysis reports."""

import csv
from pathlib import Path

from visionguard.error_analysis.schemas import ErrorCase
from visionguard.error_analysis.taxonomy import FailureType, stage_for


def write_taxonomy_csv(cases: list[ErrorCase], path: str | Path) -> Path:
    counts = {failure: 0 for failure in FailureType}
    for case in cases:
        for failure in case.observed_failures:
            counts[failure] += 1
    target = Path(path).resolve()
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("stage", "failure", "count"))
        writer.writeheader()
        for failure in FailureType:
            writer.writerow(
                {
                    "stage": stage_for(failure).value,
                    "failure": failure.value,
                    "count": counts[failure],
                }
            )
    return target


def render_top_errors(cases: list[ErrorCase], limit: int) -> str:
    lines = ["# Top error cases", ""]
    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ordered = sorted(cases, key=lambda item: (priority[item.severity.value], item.case_id))
    for case in ordered[:limit]:
        lines.extend(
            [
                f"## {case.case_id} - {case.primary_failure.value}",
                "",
                f"- Image: `{case.image}`",
                f"- Severity: {case.severity.value}",
                f"- Attribution confidence: {case.attribution_confidence.value}",
                f"- Observed: {', '.join(item.value for item in case.observed_failures)}",
                "- Suspected only: "
                + (", ".join(item.value for item in case.suspected_causes) or "none"),
                "",
            ]
        )
    return "\n".join(lines)


def render_case(case: ErrorCase) -> str:
    def block(title: str, value) -> list[str]:
        return [f"## {title}", "", "```json", str(value), "```", ""]

    lines = [
        f"# Error case {case.case_id}",
        "",
        f"- Image: `{case.image}`",
        f"- Primary failure: {case.primary_failure.value}",
        f"- Severity: {case.severity.value}",
        f"- Attribution confidence: {case.attribution_confidence.value}",
        "- Suspected causes: "
        + (", ".join(item.value for item in case.suspected_causes) or "none"),
        "",
    ]
    lines += block("Ground truth", case.ground_truth.model_dump(mode="json"))
    lines += block("Final prediction", case.prediction)
    for stage in ("detection", "ocr", "baseline", "vlm"):
        lines += block(stage.title(), case.module_outputs.get(stage, "not available"))
    lines += block("Routing", case.routing or "not available")
    lines += block("Fusion", case.fusion or "not available")
    lines += block("Thresholds", case.thresholds)
    lines += block("Timing", case.timing)
    lines.extend(
        [
            "## Suggested investigation",
            "",
            "Verify the evidence and annotation before changing a production setting.",
            "",
        ]
    )
    return "\n".join(lines)


def render_report(
    summary: dict, cases: list[ErrorCase], recommendations: list[dict], low_sample_threshold: int
) -> str:
    lines = ["# VisionGuard systematic error analysis", "", "## Scope", ""]
    lines.append(
        f"Analysed {summary['total_samples']} samples and found "
        f"{summary['total_errors']} prediction/system errors and "
        f"{summary['diagnostic_case_count']} diagnostic/hard cases."
    )
    if summary["total_samples"] < low_sample_threshold:
        lines.append("\n> Warning: the sample is too small for production-quality conclusions.")
    lines.extend(["", "## Dataset and GT coverage", ""])
    lines.append(f"- Evaluable samples: {summary['evaluable_samples']}")
    lines.append(f"- Hard cases: {summary.get('hard_case_count', 0)}")
    lines.append(f"- Regression set: {summary.get('regression_set_count', 0)}")
    lines.extend(["", "## Overall performance", ""])
    lines.append(f"- Error rate: {summary['error_rate']:.4f}")
    lines.append(f"- False-low rate: {summary['false_low_rate']:.4f}")
    lines.extend(["", "## Critical errors", ""])
    lines.append(f"- False low: {summary['false_low_count']}")
    lines.append(f"- Unsafe fast pass: {summary['unsafe_fast_pass_count']}")
    lines.extend(["", "## Failure taxonomy and stage attribution", ""])
    lines.extend(f"- {key}: {value}" for key, value in summary["counts_by_failure_stage"].items())
    lines.extend(["", "## Most frequent failures", ""])
    failures = sorted(summary["counts_by_failure"].items(), key=lambda item: -item[1])
    lines.extend(f"- {key}: {value}" for key, value in failures[:10])
    for title, key in (
        ("Category breakdown", "category_breakdown"),
        ("Confidence breakdown", "confidence_bins"),
        ("Boundary analysis", "boundary_analysis"),
        ("Routing errors", "path_breakdown"),
        ("VLM errors", "vlm_error_count"),
        ("Fusion errors and value", "fusion_value_analysis"),
        ("OCR / Detector / Baseline issues", "ocr_issue_count"),
        ("System failures", "system_failure_count"),
    ):
        lines.extend(["", f"## {title}", "", f"`{summary.get(key)}`"])
    lines.extend(["", "## Hard cases and regression set", ""])
    lines.append(
        "Hard cases include errors and correct-but-fragile boundary/conflict cases; "
        "only verified critical/high cases enter live regression by default."
    )
    lines.extend(["", "## Deterministic recommendations", ""])
    lines.extend(
        f"- {item['failure']} ({item['count']}): {item['recommendation']}"
        for item in recommendations
    )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "Observed failures are label comparisons or recorded system events. "
            "Suspected causes are hypotheses only. No configuration, threshold, "
            "prompt, or model weights were changed automatically.",
            "",
        ]
    )
    return "\n".join(lines)
