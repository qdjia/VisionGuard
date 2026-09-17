"""Replay full-pipeline evidence across safe thresholds without changing routing.yaml."""

import argparse
import csv
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_pipeline
from visionguard.routing import RoutingPolicy, load_routing_config
from visionguard.routing.evaluator import calculate_metrics, load_manifest


def _simulated_record(row, full_result, decision):
    result = full_result.model_dump(mode="json")
    result["routing"] = decision.model_dump(mode="json")
    result["routing_signals"] = decision.signals.model_dump(mode="json")
    if not decision.call_vlm:
        result["decision_source"] = "fast_path"
        result["vlm"] = None
        result["module_status"]["vlm"] = {
            "status": "skipped",
            "started_at": None,
            "latency_ms": 0,
            "error_type": None,
            "error_message": "skipped by replayed routing policy",
        }
        result["final"] = {
            "risk_level": "low",
            "categories": [],
            "reason": "Low risk from replayed Stage 1 safe consensus.",
            "confidence_score": None,
            "requires_manual_review": False,
        }
        result["timing"]["total_ms"] = max(
            0,
            result["timing"]["total_ms"]
            - result["timing"]["vlm_ms"]
            - result["timing"]["context_build_ms"],
        )
        result["timing"]["vlm_ms"] = 0
        result["timing"]["context_build_ms"] = 0
    return {
        "image": row["image"],
        "ground_truth": {
            "risk_level": row["risk_level"],
            "categories": row["categories"],
        },
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--safe-thresholds", type=float, nargs="+", default=[0.05, 0.10, 0.15, 0.20, 0.30]
    )
    parser.add_argument("--pipeline-config", type=Path, default=Path("configs/pipeline.yaml"))
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    args = parser.parse_args()
    configure_logging()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"threshold sweep output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    full = build_pipeline(
        pipeline_config=args.pipeline_config,
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
        fusion_config=args.fusion_config,
    )
    # Sweep owns one summary directory; avoid duplicating per-run full artifacts.
    full.config = full.config.model_copy(update={"save_artifacts": False})
    full.artifact_store.config = full.config
    manifest, rows = load_manifest(args.manifest, full.policy)
    full_results = [full.run(manifest.parent / row["image"]) for row in rows]
    base = load_routing_config(args.routing_config)
    reports = []
    for threshold in args.safe_thresholds:
        baseline_config = base.baseline.model_copy(update={"safe_threshold": threshold})
        policy = RoutingPolicy(base.model_copy(update={"baseline": baseline_config}))
        records = []
        for row, result in zip(rows, full_results, strict=True):
            signals = policy.collect_signals(
                result.detection,
                result.ocr,
                result.baseline,
                result.module_status,
                result.vlm,
            )
            records.append(_simulated_record(row, result, policy.decide(signals)))
        metrics = calculate_metrics(records)
        reports.append(
            {
                "safe_threshold": threshold,
                "routing_policy_version": base.version,
                **metrics,
            }
        )
    csv_path = output / "routing_threshold_sweep.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reports[0]))
        writer.writeheader()
        writer.writerows(reports)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "routing_policy_version": base.version,
                "analysis_only": True,
                "formal_config_modified": False,
                "latency_estimate_note": (
                    "Fast-path latency replays measured full-pipeline timing with VLM and "
                    "context-build time removed; rerun each policy for production benchmarks."
                ),
                "results": reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
