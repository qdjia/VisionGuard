"""Validate a YOLO detection dataset and print a structured report."""

import argparse
import json
from pathlib import Path

from visionguard.detection.dataset import DatasetValidator, load_dataset_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    report = DatasetValidator(load_dataset_config(args.data)).validate()
    print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
