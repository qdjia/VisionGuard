"""Run single-image YOLO inference and save an annotated image."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from visionguard.config import ConfigLoadError, load_config
from visionguard.core.logging import configure_logging
from visionguard.detection import DetectorError, YOLODetector, save_visualization
from visionguard.utils import load_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="Input image path")
    parser.add_argument("--config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--output", type=Path, required=True, help="Annotated output image")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    try:
        config = load_config(args.config)
        image = load_image(args.image)
        detector = YOLODetector(config.detection)
        result = detector.predict(image)
        output = save_visualization(image, result.detections, args.output)
    except (ConfigLoadError, DetectorError) as exc:
        logging.getLogger(__name__).error("Detector command failed: %s", exc)
        return 1

    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"saved visualization to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
