"""Evaluate live Full or Cascaded Pipeline fusion decisions."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.fusion.evaluator import evaluate_fusion
from visionguard.pipeline import build_cascaded_pipeline, build_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("full", "cascaded"), default="cascaded")
    parser.add_argument("--pipeline-config", type=Path)
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    args = parser.parse_args()
    configure_logging()
    common = dict(
        pipeline_config=args.pipeline_config
        or Path(
            "configs/pipeline_cascaded.yaml" if args.mode == "cascaded" else "configs/pipeline.yaml"
        ),
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
        fusion_config=args.fusion_config,
    )
    pipeline = (
        build_cascaded_pipeline(routing_config=args.routing_config, **common)
        if args.mode == "cascaded"
        else build_pipeline(**common)
    )
    summary = evaluate_fusion(pipeline, args.manifest, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
