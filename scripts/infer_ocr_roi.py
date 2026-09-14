"""Run OCR inside one ROI and return coordinates in the original image frame."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.ocr import OCREngine, load_ocr_config, save_ocr_visualization
from visionguard.schemas import BoundingBox
from visionguard.utils import load_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--bbox", nargs=4, type=float, required=True, metavar=("X1", "Y1", "X2", "Y2")
    )
    parser.add_argument("--config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configure_logging()
    image = load_image(args.image)
    result = OCREngine(load_ocr_config(args.config)).recognize_roi(
        image, BoundingBox(x1=args.bbox[0], y1=args.bbox[1], x2=args.bbox[2], y2=args.bbox[3])
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if args.output:
        saved = save_ocr_visualization(image, result.blocks, args.output)
        print(f"saved OCR visualization to {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
