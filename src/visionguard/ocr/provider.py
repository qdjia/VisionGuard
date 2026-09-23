"""OCR provider protocol and PaddleOCR 3.x adapter."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from visionguard.config.models import OCRConfig
from visionguard.core.exceptions import OCREngineLoadError, OCRInferenceError


@dataclass(frozen=True)
class RawOCRBlock:
    text: str
    confidence: float
    polygon: list[tuple[float, float]]


class OCRProvider(Protocol):
    name: str
    device: str

    def predict(self, image: np.ndarray) -> list[RawOCRBlock]: ...


class PaddleOCRProvider:
    name = "PaddleOCR"

    def __init__(self, config: OCRConfig) -> None:
        try:
            if not config.det_enabled or not config.rec_enabled:
                raise ValueError(
                    "PaddleOCR 3.x general OCR pipeline requires det_enabled and rec_enabled"
                )
            # The cache is a fallback for source development. Packaged runtime configs
            # provide explicit, validated local model directories.
            os.environ.setdefault(
                "PADDLE_PDX_CACHE_HOME", str(Path("artifacts/paddlex_cache").resolve())
            )
            requested = config.device.lower()
            # GPU development/full builds initialize PyTorch first to avoid
            # overlapping Windows CUDA DLL issues. CPU core builds deliberately
            # do not depend on PyTorch.
            if requested != "cpu":
                try:
                    import torch  # noqa: F401, I001
                except ImportError:
                    pass
            import paddle
            from paddleocr import PaddleOCR

            gpu_available = paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
            self.device = "gpu:0" if requested == "auto" and gpu_available else requested
            if self.device == "auto" or (self.device.startswith("gpu") and not gpu_available):
                self.device = "cpu"
            local_model_args = {
                "text_detection_model_dir": (
                    str(config.text_detection_model_dir)
                    if config.text_detection_model_dir is not None
                    else None
                ),
                "text_recognition_model_dir": (
                    str(config.text_recognition_model_dir)
                    if config.text_recognition_model_dir is not None
                    else None
                ),
                "textline_orientation_model_dir": (
                    str(config.textline_orientation_model_dir)
                    if config.textline_orientation_model_dir is not None
                    else None
                ),
            }
            if config.local_models_only:
                missing = [
                    value
                    for value in local_model_args.values()
                    if value is None or not Path(value).is_dir()
                ]
                if missing:
                    raise FileNotFoundError(
                        "one or more configured PaddleOCR model directories are missing"
                    )
            self._backend = PaddleOCR(
                lang=config.lang,
                device=self.device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=config.use_textline_orientation,
                text_det_limit_side_len=config.max_side_len,
                text_det_limit_type="max",
                text_rec_score_thresh=0.0,
                **{key: value for key, value in local_model_args.items() if value is not None},
            )
        except Exception as exc:
            raise OCREngineLoadError(
                f"failed to initialize PaddleOCR lang={config.lang} device={config.device}"
            ) from exc

    def predict(self, image: np.ndarray) -> list[RawOCRBlock]:
        try:
            results = list(self._backend.predict(image))
            blocks: list[RawOCRBlock] = []
            for result in results:
                payload = self._payload(result)
                texts = payload.get("rec_texts", [])
                scores = payload.get("rec_scores", [])
                polygons = payload.get("rec_polys", payload.get("dt_polys", []))
                for text, score, polygon in zip(texts, scores, polygons, strict=False):
                    blocks.append(
                        RawOCRBlock(
                            text=str(text),
                            confidence=float(score),
                            polygon=[(float(x), float(y)) for x, y in polygon],
                        )
                    )
            return blocks
        except Exception as exc:
            raise OCRInferenceError("PaddleOCR prediction failed") from exc

    @staticmethod
    def _payload(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result.get("res", result)
        serialized = getattr(result, "json", None)
        if callable(serialized):
            serialized = serialized()
        if isinstance(serialized, dict):
            return serialized.get("res", serialized)
        data = getattr(result, "res", None)
        if isinstance(data, dict):
            return data
        raise TypeError(f"unsupported PaddleOCR result type: {type(result).__name__}")
