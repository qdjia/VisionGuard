"""Run the complete Phase 7 pipeline on one image."""

import argparse
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_pipeline


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--pipeline-config", type=Path, default=Path("configs/pipeline.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, default=Path("configs/vlm.yaml"))
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    parser.add_argument("--output", type=Path, help="override the pipeline artifact root")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    configure_logging()
    pipeline = build_pipeline(
        pipeline_config=args.pipeline_config,
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
        fusion_config=args.fusion_config,
    )
    if args.output:
        pipeline.config = pipeline.config.model_copy(
            update={"artifact_root": args.output.resolve(), "save_artifacts": True}
        )
        pipeline.artifact_store.config = pipeline.config
    result = pipeline.run(args.image)
    print(result.model_dump_json(indent=2))
    print("\nPipeline summary")
    print(f"Run ID: {result.run_id}")
    print(f"Review status: {result.review_status}")
    print(f"Risk level: {result.final.risk_level}")
    print(f"Categories: {[item.name for item in result.final.categories]}")
    print(f"Manual review: {result.final.requires_manual_review}")
    print(f"Fusion score: {result.fusion.risk_score:.3f}")
    print(f"Fusion reasons: {[str(code) for code in result.fusion.reason_codes]}")
    for name, status in result.module_status.items():
        print(f"{name}: {status.status} ({status.latency_ms:.2f} ms)")
    print(f"Total time: {result.timing.total_ms:.2f} ms")
    print(f"Artifact directory: {result.artifacts.directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
