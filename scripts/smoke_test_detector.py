"""Explicit real-weight smoke test; excluded from the unit-test suite."""

from __future__ import annotations

import argparse
from pathlib import Path

from visionguard.config import load_config
from visionguard.core.logging import configure_logging
from visionguard.detection import YOLODetector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.yaml"))
    args = parser.parse_args()
    configure_logging()

    detector = YOLODetector(load_config(args.config).detection)
    first = detector.predict(args.image)
    second = detector.predict(args.image)
    print(f"model={first.model_name} device={first.device} warmed_up={detector.is_warmed_up}")
    print(f"first_ms={first.timing.total_ms:.2f} second_ms={second.timing.total_ms:.2f}")
    print(f"detections={len(second.detections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

