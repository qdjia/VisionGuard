"""Offline replay helpers for artifacts, strategies, and ablations."""

import json
from pathlib import Path

from visionguard.fusion.normalization import build_fusion_signals
from visionguard.fusion.schemas import FusionSignals
from visionguard.pipeline.schemas import ReviewResult

ABLATION_PROFILES = (
    "vlm_only",
    "detection_vlm",
    "text_vlm",
    "detection_baseline_vlm",
    "full",
)


def load_fusion_records(path: str | Path) -> list[dict]:
    source = Path(path).resolve()
    records = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not records:
        raise ValueError("fusion replay records are empty")
    return records


def signals_from_record(record: dict) -> FusionSignals:
    payload = record.get("signals")
    if payload is None:
        result = record.get("result", {})
        payload = (result.get("fusion") or result.get("final") or {}).get("signals")
    if payload is None:
        raise ValueError("record does not contain fusion signals")
    return FusionSignals.model_validate(payload)


def ablate_signals(signals: FusionSignals, profile: str) -> FusionSignals:
    if profile not in ABLATION_PROFILES:
        raise ValueError(f"unknown fusion ablation profile: {profile}")
    if profile == "full":
        return signals
    update: dict = {}
    if profile in {"vlm_only", "text_vlm"}:
        update.update(
            detection_count=0,
            max_detection_confidence=None,
            mean_detection_confidence=None,
            high_risk_detection_count=0,
            high_risk_classes=[],
            detection_evidence=[],
            detector_status="skipped",
        )
    if profile in {"vlm_only", "detection_vlm"}:
        update.update(
            ocr_block_count=0,
            mean_ocr_confidence=None,
            ocr_text_length=0,
            ocr_status="skipped",
            baseline_label=None,
            baseline_probability=None,
            baseline_status="skipped",
        )
    if profile == "detection_baseline_vlm":
        update.update(module_failures=[])
    disabled = {
        "vlm_only": {"detector", "ocr", "baseline"},
        "detection_vlm": {"ocr", "baseline"},
        "text_vlm": {"detector"},
        "detection_baseline_vlm": set(),
    }[profile]
    update["module_failures"] = [name for name in signals.module_failures if name not in disabled]
    visual_available = profile in {"detection_vlm", "detection_baseline_vlm"} and (
        update.get("detector_status", signals.detector_status) == "success"
    )
    text_available = profile in {"text_vlm", "detection_baseline_vlm"} and (
        update.get("ocr_status", signals.ocr_status) == "success"
        and update.get("baseline_status", signals.baseline_status) == "success"
    )
    update.update(
        evidence_conflict=False,
        routing_overridden_by_fusion=False,
        insufficient_evidence=not (visual_available or text_available or signals.vlm_available),
    )
    return signals.model_copy(update=update)


def replay_artifact_tree(root: str | Path, engine) -> list[dict]:
    root = Path(root).resolve()
    results: list[dict] = []
    for path in sorted(root.rglob("review_result.json")):
        review = ReviewResult.model_validate_json(path.read_text(encoding="utf-8"))
        signals = build_fusion_signals(
            review.detection,
            review.ocr,
            review.baseline,
            review.vlm,
            review.routing,
            review.module_status,
            engine.config,
        )
        decision = engine.decide(signals)
        results.append(
            {
                "artifact": str(path),
                "run_id": review.run_id,
                "signals": signals.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
            }
        )
    if not results:
        raise ValueError(f"no review_result.json artifacts found under {root}")
    return results
