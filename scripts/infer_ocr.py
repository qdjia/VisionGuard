"""Run full-image OCR and save an annotated image."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.ocr import OCREngine, load_ocr_config, save_ocr_visualization
from visionguard.utils import load_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    configure_logging()
    image = load_image(args.image)
    result = OCREngine(load_ocr_config(args.config)).recognize(image)
    target = save_ocr_visualization(image, result.blocks, args.output)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"saved OCR visualization to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
