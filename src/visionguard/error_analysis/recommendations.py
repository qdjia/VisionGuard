"""Deterministic recommendations; this module never edits model or policy settings."""

from collections import Counter

from visionguard.error_analysis.schemas import ErrorCase

_ACTIONS = {
    "false_low": "Review unsafe misses first; inspect routing guards and missing evidence.",
    "unsafe_fast_pass": (
        "Add verified examples near the fast-path boundary and audit routing thresholds."
    ),
    "false_high": "Inspect high-scoring false evidence before considering threshold changes.",
    "low_confidence_ocr": "Compare raw-image and light-preprocessing OCR on the affected samples.",
    "potential_unnecessary_vlm": (
        "Measure latency/quality trade-offs before tightening VLM routing."
    ),
    "module_failure": "Fix the failing module and preserve the case as an integration regression.",
    "near_decision_boundary": (
        "Expand verified samples around the decision boundary; do not tune on this set alone."
    ),
    "ambiguous_label": "Send the sample for independent annotation review before model changes.",
}


def generate_recommendations(cases: list[ErrorCase]) -> list[dict]:
    counts = Counter(failure.value for case in cases for failure in case.observed_failures)
    return [
        {"failure": failure, "count": count, "recommendation": _ACTIONS[failure]}
        for failure, count in counts.most_common()
        if failure in _ACTIONS
    ]
