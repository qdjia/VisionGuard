"""Backend-independent full-image and ROI OCR orchestration."""

import logging
from collections.abc import Callable
from time import perf_counter

import numpy as np

from visionguard.config.models import OCRConfig
from visionguard.core.exceptions import OCRInferenceError
from visionguard.ocr.geometry import offset_polygon, polygon_to_bbox, sanitize_bbox
from visionguard.ocr.preprocessing import OCRPreprocessor
from visionguard.ocr.provider import OCRProvider, PaddleOCRProvider, RawOCRBlock
from visionguard.schemas import BoundingBox, OCRResult, OCRScope, OCRTextBlock, OCRTiming
from visionguard.utils.image import ImageInput, load_image

LOGGER = logging.getLogger(__name__)


class OCREngine:
    def __init__(
        self,
        config: OCRConfig,
        provider_factory: Callable[[OCRConfig], OCRProvider] | None = None,
    ) -> None:
        self.config = config
        factory = provider_factory or PaddleOCRProvider
        LOGGER.info("Loading OCR engine provider=%s lang=%s", config.provider, config.lang)
        self._provider = factory(config)
        self.device = self._provider.device
        self._preprocessor = OCRPreprocessor(config.preprocessing, config.max_side_len)
        self._warmed_up = False
        if config.warmup_enabled:
            self.warmup()
        LOGGER.info("OCR engine loaded provider=%s device=%s", self._provider.name, self.device)

    @property
    def is_warmed_up(self) -> bool:
        return self._warmed_up

    def warmup(self) -> None:
        if self._warmed_up:
            return
        started = perf_counter()
        self._provider.predict(np.full((64, 192, 3), 255, dtype=np.uint8))
        self._warmed_up = True
        LOGGER.info("OCR warmup completed in %.2f ms", (perf_counter() - started) * 1000)

    def recognize(self, image: ImageInput) -> OCRResult:
        original = load_image(image)
        return self._recognize_array(
            original, original.shape[1], original.shape[0], OCRScope.FULL_IMAGE
        )

    def recognize_roi(self, image: ImageInput, bbox: BoundingBox) -> OCRResult:
        original = load_image(image)
        height, width = original.shape[:2]
        x1, y1, x2, y2 = sanitize_bbox(bbox, width, height)
        LOGGER.info("OCR ROI=(%d,%d,%d,%d)", x1, y1, x2, y2)
        result = self._recognize_array(
            original[y1:y2, x1:x2], width, height, OCRScope.ROI, (x1, y1)
        )
        if not result.blocks and self.config.fallback_full_image:
            full = self._recognize_array(original, width, height, OCRScope.ROI)
            inside = [
                block
                for block in full.blocks
                if x1 <= (block.bbox.x1 + block.bbox.x2) / 2 <= x2
                and y1 <= (block.bbox.y1 + block.bbox.y2) / 2 <= y2
            ]
            return full.model_copy(
                update={
                    "blocks": inside,
                    "full_text": self._full_text(inside),
                    "filtered_block_count": len(inside),
                }
            )
        return result

    def _recognize_array(
        self,
        image: np.ndarray,
        output_width: int,
        output_height: int,
        scope: OCRScope,
        offset: tuple[int, int] = (0, 0),
    ) -> OCRResult:
        total_started = perf_counter()
        preprocess_started = perf_counter()
        processed = self._preprocessor.process(image)
        preprocess_ms = (perf_counter() - preprocess_started) * 1000
        scale_x = image.shape[1] / processed.shape[1]
        scale_y = image.shape[0] / processed.shape[0]
        ocr_started = perf_counter()
        try:
            raw = self._provider.predict(processed)
        except OCRInferenceError:
            raise
        except Exception as exc:
            raise OCRInferenceError(
                f"OCR failed provider={self._provider.name} device={self.device}"
            ) from exc
        ocr_ms = (perf_counter() - ocr_started) * 1000
        post_started = perf_counter()
        blocks = self._blocks(raw, scope, offset, scale_x, scale_y)
        filtered = [b for b in blocks if b.confidence >= self.config.confidence_threshold]
        filtered.sort(key=lambda block: (round(block.bbox.y1 / 10), block.bbox.x1))
        postprocess_ms = (perf_counter() - post_started) * 1000
        result = OCRResult(
            image_width=output_width,
            image_height=output_height,
            blocks=filtered,
            full_text=self._full_text(filtered),
            timing=OCRTiming(
                preprocess_ms=preprocess_ms,
                ocr_ms=ocr_ms,
                postprocess_ms=postprocess_ms,
                total_ms=(perf_counter() - total_started) * 1000,
            ),
            device=self.device,
            engine_name=self._provider.name,
            raw_block_count=len(raw),
            filtered_block_count=len(filtered),
        )
        LOGGER.info(
            "OCR finished raw=%d filtered=%d total_ms=%.2f",
            len(raw),
            len(filtered),
            result.timing.total_ms,
        )
        return result

    @staticmethod
    def _blocks(
        raw: list[RawOCRBlock],
        scope: OCRScope,
        offset: tuple[int, int],
        scale_x: float,
        scale_y: float,
    ) -> list[OCRTextBlock]:
        blocks = []
        for item in raw:
            scaled = [(x * scale_x, y * scale_y) for x, y in item.polygon]
            polygon = offset_polygon(scaled, *offset)
            blocks.append(
                OCRTextBlock(
                    text=item.text,
                    confidence=item.confidence,
                    polygon=polygon,
                    bbox=polygon_to_bbox(polygon),
                    scope=scope,
                )
            )
        return blocks

    @staticmethod
    def _full_text(blocks: list[OCRTextBlock]) -> str:
        return "\n".join(block.text for block in blocks)
