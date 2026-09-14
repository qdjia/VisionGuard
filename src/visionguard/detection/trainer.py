"""Configuration-driven Ultralytics YOLO fine-tuning."""

import csv
import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from visionguard.detection.dataset import load_dataset_config, write_resolved_dataset_config
from visionguard.detection.detector import resolve_device
from visionguard.detection.predictions import export_validation_predictions
from visionguard.training.config import TrainConfig
from visionguard.training.experiment import ExperimentManager
from visionguard.training.metrics import extract_detection_metrics
from visionguard.training.schemas import TrainingResult, TrainingSummary
from visionguard.utils.seed import set_seed

LOGGER = logging.getLogger(__name__)


def _best_epoch(results_csv: Path) -> int | None:
    if not results_csv.is_file():
        return None
    with results_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return None
    metric_key = next((key for key in rows[0] if "mAP50-95" in key), None)
    epoch_key = next((key for key in rows[0] if key.strip() == "epoch"), None)
    if metric_key is None or epoch_key is None:
        return None
    best = max(rows, key=lambda row: float(row[metric_key]))
    return int(float(best[epoch_key]))


def _factory(model: str) -> Any:
    from ultralytics import YOLO

    return YOLO(model)


class YOLOTrainer:
    def __init__(
        self, config: TrainConfig, model_factory: Callable[[str], Any] | None = None
    ) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self._factory = model_factory or _factory
        self.experiment = ExperimentManager(config)

    def train(self) -> TrainingResult:
        directory = self.experiment.prepare()
        config_path = self.experiment.save_config()
        self.experiment.save_environment()
        set_seed(self.config.seed, deterministic=self.config.deterministic)
        model = self._factory(self.config.model)
        amp = self.config.amp and self.device.startswith("cuda")
        ultralytics_data = write_resolved_dataset_config(
            load_dataset_config(self.config.data), directory / "dataset.resolved.yaml"
        )
        args = self.config.augmentation.model_dump()
        args.update(
            data=str(ultralytics_data),
            epochs=self.config.epochs,
            batch=self.config.batch_size,
            imgsz=self.config.image_size,
            device=self.device,
            workers=self.config.workers,
            seed=self.config.seed,
            deterministic=self.config.deterministic,
            optimizer=self.config.optimizer,
            lr0=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_epochs=self.config.warmup_epochs,
            patience=self.config.patience,
            amp=amp,
            pretrained=self.config.pretrained,
            save_period=self.config.save_period,
            project=str(self.config.artifacts_dir),
            name=self.config.experiment_name,
            exist_ok=True,
        )
        if self.config.resume:
            args["resume"] = (
                str(self.config.resume) if isinstance(self.config.resume, Path) else True
            )
        LOGGER.info(
            "Starting experiment=%s model=%s device=%s",
            self.config.experiment_name,
            self.config.model,
            self.device,
        )
        started = perf_counter()
        train_result = model.train(**args)
        elapsed = perf_counter() - started
        metrics_source = getattr(train_result, "metrics", None) or train_result
        try:
            metrics = extract_detection_metrics(metrics_source)
        except ValueError:
            metrics = extract_detection_metrics(
                model.val(data=str(ultralytics_data), device=self.device)
            )
        metrics_path = self.experiment.save_json("metrics.json", metrics)
        best = directory / "weights" / "best.pt"
        last = directory / "weights" / "last.pt"
        summary = TrainingSummary(
            experiment_name=self.config.experiment_name,
            model=self.config.model,
            dataset=self.config.data,
            epochs=self.config.epochs,
            best_epoch=_best_epoch(directory / "results.csv"),
            best_checkpoint=best,
            last_checkpoint=last,
            precision=metrics.precision,
            recall=metrics.recall,
            map50=metrics.map50,
            map50_95=metrics.map50_95,
            training_time_seconds=elapsed,
            average_epoch_time_seconds=elapsed / self.config.epochs,
            device=self.device,
            seed=self.config.seed,
            config_path=self.config.config_path,
        )
        summary_path = self.experiment.save_json("training_summary.json", summary)
        if best.is_file() and self.config.validation_sample_count:
            export_validation_predictions(
                best,
                self.config.data,
                directory / "predictions",
                sample_count=self.config.validation_sample_count,
                device=self.device,
                image_size=self.config.image_size,
            )
        return TrainingResult(
            experiment_dir=directory,
            metrics_path=metrics_path,
            summary_path=summary_path,
            config_snapshot_path=config_path,
            summary=summary,
        )

    def resume(self, checkpoint: Path) -> TrainingResult:
        return YOLOTrainer(
            self.config.model_copy(update={"resume": checkpoint}), self._factory
        ).train()
