"""Experiment directories and machine-readable artifact persistence."""

import json
import platform
from pathlib import Path
from typing import Any

import yaml


class ExperimentManager:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.directory = config.artifacts_dir / config.experiment_name

    def prepare(self) -> Path:
        if (
            self.directory.exists()
            and any(self.directory.iterdir())
            and not getattr(self.config, "resume", False)
        ):
            raise FileExistsError(
                f"experiment directory is not empty: {self.directory}; use resume or a new name"
            )
        self.directory.mkdir(parents=True, exist_ok=True)
        return self.directory

    def save_config(self) -> Path:
        target = self.directory / "config.yaml"
        payload = self.config.model_dump(mode="json")
        target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return target

    def save_json(self, filename: str, value: Any) -> Path:
        target = self.directory / filename
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        target.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    def save_environment(self) -> Path:
        import torch
        import ultralytics

        return self.save_json(
            "environment.json",
            {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "ultralytics": ultralytics.__version__,
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "seed": self.config.seed,
            },
        )
