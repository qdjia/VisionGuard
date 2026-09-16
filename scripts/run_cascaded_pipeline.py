"""Run the Phase 8 rule-based cascaded pipeline on one image."""

import argparse
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_cascaded_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--pipeline-config", type=Path, default=Path("configs/pipeline_cascaded.yaml")
    )
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, default=Path("configs/vlm.yaml"))
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
    result = pipeline.run(args.image)
    print(result.model_dump_json(indent=2))
    print(
        f"run_id={result.run_id} route={result.routing.route} "
        f"call_vlm={result.routing.call_vlm} "
        f"reasons={[str(code) for code in result.routing.reason_codes]} "
        f"total_ms={result.timing.total_ms:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
