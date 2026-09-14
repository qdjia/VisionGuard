"""Checkpoint evaluation independent from training and CLI concerns."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from visionguard.detection.dataset import load_dataset_config, write_resolved_dataset_config
from visionguard.detection.detector import resolve_device
from visionguard.training.metrics import extract_detection_metrics
from visionguard.training.schemas import DetectionMetrics


def _factory(path: str) -> Any:
    from ultralytics import YOLO

    return YOLO(path)


class YOLOEvaluator:
    def __init__(self, model_factory: Callable[[str], Any] | None = None) -> None:
        self._factory = model_factory or _factory

    def evaluate(
        self,
        checkpoint: str | Path,
        data: str | Path,
        *,
        split: str = "val",
        device: str = "auto",
        image_size: int = 640,
    ) -> DetectionMetrics:
        if split not in {"val", "test"}:
            raise ValueError("split must be 'val' or 'test'")
        checkpoint_path = Path(checkpoint).expanduser().resolve()
        model = self._factory(str(checkpoint_path))
        experiment_dir = checkpoint_path.parent.parent
        resolved = write_resolved_dataset_config(
            load_dataset_config(data), experiment_dir / "dataset.evaluation.yaml"
        )
        result = model.val(
            data=str(resolved),
            split=split,
            device=resolve_device(device),
            imgsz=image_size,
            project=str(experiment_dir),
            name=f"evaluation_{split}",
            exist_ok=True,
        )
        return extract_detection_metrics(result)
