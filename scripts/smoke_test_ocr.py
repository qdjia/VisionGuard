"""Run real PaddleOCR smoke checks for full image, blank image, and ROI."""

import argparse
from pathlib import Path

import numpy as np

from visionguard.core.logging import configure_logging
from visionguard.ocr import OCREngine, load_ocr_config
from visionguard.schemas import BoundingBox


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chinese-image", type=Path, required=True)
    parser.add_argument("--english-image", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/ocr.yaml"))
    args = parser.parse_args()
    configure_logging()
    engine = OCREngine(load_ocr_config(args.config))
    for name, image in (
        ("chinese", args.chinese_image),
        ("english", args.english_image),
        ("blank", np.full((256, 512, 3), 255, dtype=np.uint8)),
    ):
        result = engine.recognize(image)
        print(
            name,
            f"blocks={result.filtered_block_count}",
            f"text={result.full_text!r}",
            f"total_ms={result.timing.total_ms:.2f}",
        )
    roi = engine.recognize_roi(args.chinese_image, BoundingBox(x1=0, y1=0, x2=500, y2=300))
    print(
        "roi",
        f"blocks={roi.filtered_block_count}",
        f"text={roi.full_text!r}",
        f"total_ms={roi.timing.total_ms:.2f}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
