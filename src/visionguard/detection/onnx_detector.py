"""Ultralytics-free ONNX Runtime detector for release deployments."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from visionguard.config.models import DetectionConfig
from visionguard.detection.exceptions import DetectorLoadError, InferenceError
from visionguard.schemas import BoundingBox, Detection, DetectionResult, TimingInfo
from visionguard.utils.image import ImageInput, load_image

LOGGER = logging.getLogger(__name__)
SessionFactory = Callable[[str, list[str]], Any]


def _execution_providers(requested: str, available: list[str]) -> list[str]:
    has_cuda = "CUDAExecutionProvider" in available
    if requested == "cuda" and not has_cuda:
        raise DetectorLoadError("ONNX Runtime CUDAExecutionProvider is unavailable")
    if requested == "cpu":
        return ["CPUExecutionProvider"]
    if has_cuda:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _default_session_factory(model_path: str, providers: list[str]) -> Any:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise DetectorLoadError(
            "ONNX Runtime is not installed; install the release detector dependencies"
        ) from exc
    if "CUDAExecutionProvider" in providers and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    return ort.InferenceSession(model_path, providers=providers)


def _letterbox(
    image: np.ndarray, size: int, *, auto: bool = False, stride: int = 32
) -> tuple[np.ndarray, float, tuple[float, float]]:
    """Resize with YOLO-style aspect-ratio padding and return reverse mapping."""

    height, width = image.shape[:2]
    scale = min(size / height, size / width)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_width = size - resized_width
    pad_height = size - resized_height
    if auto:
        pad_width %= stride
        pad_height %= stride
    pad_x = pad_width / 2
    pad_y = pad_height / 2
    left = round(pad_x - 0.1)
    right = round(pad_x + 0.1)
    top = round(pad_y - 0.1)
    bottom = round(pad_y + 0.1)
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    tensor = padded[:, :, ::-1].transpose(2, 0, 1)
    return np.ascontiguousarray(tensor, dtype=np.float32) / 255.0, scale, (left, top)


class OnnxYoloDetector:
    """Run an ONNX detector exported with embedded NMS and no Ultralytics import."""

    def __init__(
        self,
        config: DetectionConfig,
        *,
        session_factory: SessionFactory | None = None,
        available_providers: list[str] | None = None,
    ) -> None:
        self.config = config
        self.model_name = Path(config.model_path).name
        self._warmed_up = False
        try:
            if available_providers is None:
                import onnxruntime as ort

                available_providers = ort.get_available_providers()
            providers = _execution_providers(config.onnx_execution_provider, available_providers)
            factory = session_factory or _default_session_factory
            self._session = factory(str(config.model_path), providers)
            self._input_name = self._session.get_inputs()[0].name
            active = self._session.get_providers()
            self.device = f"onnx:{active[0]}"
        except DetectorLoadError:
            raise
        except Exception as exc:
            raise DetectorLoadError(f"failed to load ONNX detector: {config.model_path}") from exc
        if config.warmup_enabled:
            self.warmup()

    @property
    def is_warmed_up(self) -> bool:
        return self._warmed_up

    def warmup(self) -> None:
        if self._warmed_up:
            return
        dummy = np.zeros((1, 3, self.config.image_size, self.config.image_size), dtype=np.float32)
        try:
            for _ in range(self.config.warmup_runs):
                self._session.run(None, {self._input_name: dummy})
        except Exception as exc:
            raise InferenceError(f"ONNX detector warmup failed: {self.model_name}") from exc
        self._warmed_up = True

    def predict(self, image: ImageInput) -> DetectionResult:
        return self._predict_loaded([load_image(image)], auto_letterbox=True)[0]

    def predict_batch(self, images: list[ImageInput]) -> list[DetectionResult]:
        if not images:
            return []
        return self._predict_loaded([load_image(image) for image in images], auto_letterbox=False)

    def _predict_loaded(
        self, normalized: list[np.ndarray], *, auto_letterbox: bool
    ) -> list[DetectionResult]:
        total_started = perf_counter()
        preprocess_started = perf_counter()
        prepared = [
            _letterbox(image, self.config.image_size, auto=auto_letterbox) for image in normalized
        ]
        batch = np.stack([item[0] for item in prepared])
        preprocess_ms = (perf_counter() - preprocess_started) * 1000

        inference_started = perf_counter()
        try:
            outputs = self._session.run(None, {self._input_name: batch})
        except Exception as exc:
            raise InferenceError(f"ONNX detector inference failed: {self.model_name}") from exc
        inference_ms = (perf_counter() - inference_started) * 1000

        postprocess_started = perf_counter()
        try:
            predictions = np.asarray(outputs[0])
            if predictions.ndim == 2:
                predictions = predictions[None, ...]
            if predictions.ndim != 3 or predictions.shape[-1] != 6:
                raise ValueError(
                    "expected embedded-NMS output [batch, detections, 6], "
                    f"received {predictions.shape}"
                )
            if predictions.shape[0] != len(normalized):
                raise ValueError("ONNX output batch size does not match input batch")
            parsed = [
                self._parse_rows(rows, image.shape[1], image.shape[0], scale, padding)
                for rows, image, (_, scale, padding) in zip(
                    predictions, normalized, prepared, strict=True
                )
            ]
        except Exception as exc:
            raise InferenceError(
                f"failed to parse ONNX detector output: {self.model_name}"
            ) from exc
        postprocess_ms = (perf_counter() - postprocess_started) * 1000
        total_ms = (perf_counter() - total_started) * 1000
        count = len(normalized)
        timing = TimingInfo(
            preprocess_ms=preprocess_ms / count,
            inference_ms=inference_ms / count,
            postprocess_ms=postprocess_ms / count,
            total_ms=total_ms / count,
        )
        return [
            DetectionResult(
                image_width=image.shape[1],
                image_height=image.shape[0],
                detections=detections,
                timing=timing,
                device=self.device,
                model_name=self.model_name,
            )
            for image, detections in zip(normalized, parsed, strict=True)
        ]

    def _parse_rows(
        self,
        rows: np.ndarray,
        width: int,
        height: int,
        scale: float,
        padding: tuple[float, float],
    ) -> list[Detection]:
        pad_x, pad_y = padding
        detections = []
        for x1, y1, x2, y2, confidence, raw_class_id in rows.tolist():
            if confidence < self.config.conf_threshold or x2 <= x1 or y2 <= y1:
                continue
            class_id = int(raw_class_id)
            original_name = (
                self.config.class_names[class_id]
                if 0 <= class_id < len(self.config.class_names)
                else str(class_id)
            )
            class_name = self.config.class_name_mapping.get(original_name, original_name)
            mapped = (
                max(0.0, min(width, (float(x1) - pad_x) / scale)),
                max(0.0, min(height, (float(y1) - pad_y) / scale)),
                max(0.0, min(width, (float(x2) - pad_x) / scale)),
                max(0.0, min(height, (float(y2) - pad_y) / scale)),
            )
            if mapped[2] <= mapped[0] or mapped[3] <= mapped[1]:
                continue
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(confidence),
                    bbox=BoundingBox(x1=mapped[0], y1=mapped[1], x2=mapped[2], y2=mapped[3]),
                )
            )
        return detections[: self.config.max_det]
