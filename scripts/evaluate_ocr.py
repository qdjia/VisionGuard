"""Evaluate OCR Character Error Rate from a JSONL manifest."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.ocr import OCREngine, OCREvaluator, load_ocr_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/ocr/evaluation.json"))
    parser.add_argument("--error-threshold", type=float, default=0.3)
    args = parser.parse_args()
    configure_logging()
    result = OCREvaluator(OCREngine(load_ocr_config(args.config))).evaluate_jsonl(
        args.manifest, args.output, error_threshold=args.error_threshold
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
