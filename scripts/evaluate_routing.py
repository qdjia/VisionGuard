"""Evaluate VLM call rate, latency, routing proxy metrics, and unsafe fast passes."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_cascaded_pipeline
from visionguard.routing.evaluator import evaluate_routing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--pipeline-config", type=Path, default=Path("configs/pipeline_cascaded.yaml")
    )
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    args = parser.parse_args()
    configure_logging()
    pipeline = build_cascaded_pipeline(
        pipeline_config=args.pipeline_config,
        routing_config=args.routing_config,
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
    )
    summary = evaluate_routing(pipeline, args.manifest, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("unsafe_fast_pass_count:", summary["metrics"]["unsafe_fast_pass_count"])
    print("unsafe_fast_pass_rate:", summary["metrics"]["unsafe_fast_pass_rate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
