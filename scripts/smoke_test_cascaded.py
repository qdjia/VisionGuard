"""Run representative real images through one initialized cascaded pipeline."""

import argparse
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_cascaded_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--pipeline-config", type=Path, default=Path("configs/pipeline_cascaded.yaml")
    )
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
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
        fusion_config=args.fusion_config,
    )
    failures = 0
    for image in args.images:
        try:
            result = pipeline.run(image)
            print(
                image,
                f"route={result.routing.route}",
                f"call_vlm={result.routing.call_vlm}",
                f"reasons={[str(code) for code in result.routing.reason_codes]}",
                f"scores={result.fusion.scores.model_dump(mode='json')}",
                f"fusion={result.fusion.risk_score:.3f}/{result.fusion.risk_level}",
                f"manual={result.fusion.requires_manual_review}",
                f"review={result.review_status}",
                f"total_ms={result.timing.total_ms:.2f}",
            )
        except Exception as exc:
            failures += 1
            print(image, f"FAILED: {type(exc).__name__}: {exc}")
    print(f"samples={len(args.images)} failures={failures}")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
