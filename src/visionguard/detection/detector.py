"""Reusable single-image Ultralytics YOLO detector."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from visionguard.config.models import DetectionConfig
from visionguard.detection.exceptions import DetectorLoadError, InferenceError
from visionguard.schemas import BoundingBox, Detection, DetectionResult, TimingInfo
from visionguard.utils.image import ImageInput, load_image

LOGGER = logging.getLogger(__name__)
ModelFactory = Callable[[str], Any]


def _default_model_factory(model_path: str) -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise DetectorLoadError(
            "Ultralytics is not installed; install the Phase 2 runtime dependencies"
        ) from exc
    return YOLO(model_path)


def resolve_device(requested: str) -> str:
    """Resolve ``auto`` without initializing CUDA repeatedly during prediction."""

    if requested.lower() != "auto":
        return requested
    try:
        import torch
    except ImportError:
        LOGGER.warning("PyTorch is unavailable; falling back to CPU")
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class YOLODetector:
    """Own one model instance and expose normalized single-image predictions."""

    def __init__(
        self,
        config: DetectionConfig,
        *,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.config = config
        self.device = resolve_device(config.device)
        self.use_half = config.half_precision and self.device.startswith("cuda")
        self._warmed_up = False
        factory = model_factory or _default_model_factory

        LOGGER.info("Loading YOLO model path=%s device=%s", config.model_path, self.device)
        try:
            self._model = factory(str(config.model_path))
        except DetectorLoadError:
            raise
        except Exception as exc:
            raise DetectorLoadError(f"failed to load YOLO model: {config.model_path}") from exc

        self.model_name = Path(config.model_path).name
        LOGGER.info("YOLO model loaded: %s", self.model_name)
        if config.half_precision and not self.use_half:
            LOGGER.info("Half precision disabled because resolved device is %s", self.device)
        if config.warmup_enabled:
            self.warmup()

    @property
    def is_warmed_up(self) -> bool:
        return self._warmed_up

    def _predict_raw(self, image: np.ndarray) -> Any:
        return self._model.predict(
            source=image,
            conf=self.config.conf_threshold,
            iou=self.config.iou_threshold,
            imgsz=self.config.image_size,
            max_det=self.config.max_det,
            device=self.device,
            half=self.use_half,
            verbose=False,
        )

    def warmup(self) -> None:
        """Warm the model at most once; warmup latency is not part of predictions."""

        if self._warmed_up:
            return
        started = perf_counter()
        dummy = np.zeros((self.config.image_size, self.config.image_size, 3), dtype=np.uint8)
        try:
            for _ in range(self.config.warmup_runs):
                self._predict_raw(dummy)
        except Exception as exc:
            raise InferenceError(
                f"YOLO warmup failed for model={self.model_name} device={self.device}"
            ) from exc
        self._warmed_up = True
        elapsed_ms = (perf_counter() - started) * 1000
        LOGGER.info("YOLO detector warmup completed in %.2f ms", elapsed_ms)

    def predict(self, image: ImageInput) -> DetectionResult:
        """Run one prediction and return a backend-independent result schema."""

        total_started = perf_counter()
        preprocess_started = perf_counter()
        normalized = load_image(image)
        preprocess_ms = (perf_counter() - preprocess_started) * 1000
        height, width = normalized.shape[:2]

        inference_started = perf_counter()
        try:
            raw_results = self._predict_raw(normalized)
        except Exception as exc:
            LOGGER.exception(
                "YOLO inference failed for model=%s device=%s", self.model_name, self.device
            )
            raise InferenceError(
                f"YOLO inference failed for model={self.model_name} device={self.device}"
            ) from exc
        inference_ms = (perf_counter() - inference_started) * 1000

        postprocess_started = perf_counter()
        try:
            detections = self._parse_results(raw_results)
        except Exception as exc:
            raise InferenceError(
                f"failed to parse YOLO output from model={self.model_name}"
            ) from exc
        postprocess_ms = (perf_counter() - postprocess_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000

        result = DetectionResult(
            image_width=width,
            image_height=height,
            detections=detections,
            timing=TimingInfo(
                preprocess_ms=preprocess_ms,
                inference_ms=inference_ms,
                postprocess_ms=postprocess_ms,
                total_ms=total_ms,
            ),
            device=self.device,
            model_name=self.model_name,
        )
        LOGGER.info(
            "Inference finished model=%s device=%s detections=%d total_ms=%.2f",
            self.model_name,
            self.device,
            len(detections),
            total_ms,
        )
        return result

    def _parse_results(self, raw_results: Any) -> list[Detection]:
        if raw_results is None:
            raise ValueError("model returned None")
        results = list(raw_results)
        if not results:
            return []

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return []
        names = getattr(result, "names", None) or getattr(self._model, "names", {})
        xyxy = boxes.xyxy.detach().cpu().tolist()
        confidences = boxes.conf.detach().cpu().tolist()
        class_ids = boxes.cls.detach().cpu().tolist()

        detections: list[Detection] = []
        for coordinates, confidence, raw_class_id in zip(
            xyxy, confidences, class_ids, strict=True
        ):
            class_id = int(raw_class_id)
            original_name = self._class_name(names, class_id)
            class_name = self.config.class_name_mapping.get(original_name, original_name)
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(confidence),
                    bbox=BoundingBox(
                        x1=max(0.0, float(coordinates[0])),
                        y1=max(0.0, float(coordinates[1])),
                        x2=float(coordinates[2]),
                        y2=float(coordinates[3]),
                    ),
                )
            )
        return detections

    @staticmethod
    def _class_name(names: Any, class_id: int) -> str:
        if isinstance(names, dict):
            return str(names.get(class_id, class_id))
        if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            return str(names[class_id])
        return str(class_id)
