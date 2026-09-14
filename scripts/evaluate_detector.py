"""Evaluate a YOLO checkpoint on a validation or test split."""

import argparse
import json
from pathlib import Path

from visionguard.detection.evaluator import YOLOEvaluator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metrics = YOLOEvaluator().evaluate(
        args.checkpoint,
        args.data,
        split=args.split,
        device=args.device,
        image_size=args.image_size,
    )
    payload = json.dumps(metrics.model_dump(mode="json"), indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
