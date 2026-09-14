"""Start a configuration-driven YOLO training experiment."""

import argparse
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.detection.dataset import DatasetValidator, load_dataset_config
from visionguard.detection.trainer import YOLOTrainer
from visionguard.training import load_train_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--device")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    configure_logging()
    config = load_train_config(args.config)
    updates = {
        key: value
        for key, value in {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "device": args.device,
            "resume": args.resume.resolve() if args.resume else None,
        }.items()
        if value is not None
    }
    config = config.model_copy(update=updates)
    report = DatasetValidator(load_dataset_config(config.data)).validate()
    if not report.valid:
        print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return 2
    result = YOLOTrainer(config).train()
    print(json.dumps(result.summary.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
