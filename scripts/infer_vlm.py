import argparse
from pathlib import Path

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.core.logging import configure_logging
from visionguard.moderation.policy import load_policy
from visionguard.schemas import DetectionResult, OCRResult
from visionguard.vlm import build_context, create_provider, load_vlm_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/vlm.yaml"))
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--detection-json", type=Path)
    parser.add_argument("--ocr-json", type=Path)
    parser.add_argument("--baseline-json", type=Path)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--output", type=Path, help="optional structured JSON artifact")
    args = parser.parse_args()
    configure_logging()
    config = load_vlm_config(args.config)
    if args.mock:
        config = config.model_copy(update={"provider": "mock"})
    values = [
        schema.model_validate_json(path.read_text(encoding="utf-8")) if path else None
        for schema, path in (
            (DetectionResult, args.detection_json),
            (OCRResult, args.ocr_json),
            (TextModerationPrediction, args.baseline_json),
        )
    ]
    result = create_provider(config).analyze(
        args.image, build_context(*values), load_policy(args.policy)
    )
    print(result.model_dump_json(indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
