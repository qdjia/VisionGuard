"""Shared synchronous orchestration; generation honours a single call deadline."""

import html
import logging
from time import perf_counter

from PIL import Image

from visionguard.schemas import BoundingBox
from visionguard.vlm.base import VLMProvider
from visionguard.vlm.exceptions import VLMError, VLMInferenceError, VLMParseError, VLMTimeoutError
from visionguard.vlm.parser import parse_result
from visionguard.vlm.prompt_builder import PromptBuilder
from visionguard.vlm.schemas import VLMTiming

LOGGER = logging.getLogger(__name__)


class StructuredProvider(VLMProvider):
    def __init__(self, config) -> None:
        self.config = config
        self.builder = PromptBuilder(config)

    def generate(self, image, prompt, deadline):
        raise NotImplementedError

    def analyze(self, image, context, policy):
        try:
            return self._analyze(image, context, policy)
        except VLMError as exc:
            exc.provider = self.config.provider
            exc.model = self.config.model_name_or_path
            exc.prompt_version = self.config.prompt_version
            LOGGER.error(
                "VLM failed provider=%s model=%s prompt=%s type=%s",
                exc.provider,
                exc.model,
                exc.prompt_version,
                type(exc).__name__,
            )
            raise

    def _analyze(self, image, context, policy):
        start = perf_counter()
        deadline = start + self.config.timeout_seconds
        if isinstance(image, Image.Image):
            prepared_image = image.convert("RGB")
            width, height = prepared_image.size
        else:
            import cv2

            from visionguard.utils.image import load_image

            original = load_image(image)
            height, width = original.shape[:2]
            prepared_image = Image.fromarray(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
        prepared_image.thumbnail((self.config.image_max_side, self.config.image_max_side))
        prepared = perf_counter()
        prompt, metadata = self.builder.build(context, policy)
        prompt += f"\nOriginal image dimensions: {width}x{height}. "
        prompt += "Map any evidence coordinates to this original frame, or omit bbox."
        metadata["input_chars"] = len(prompt)
        built = perf_counter()
        inference_ms = parse_ms = 0.0
        parse_retries = 0
        attempt_usage = []
        for attempt in range(self.config.max_retries + 1):
            if perf_counter() >= deadline:
                raise VLMTimeoutError("VLM call deadline exceeded")
            generated = perf_counter()
            try:
                raw, usage = self.generate(prepared_image, prompt, deadline)
            except VLMTimeoutError:
                raise
            except VLMInferenceError as exc:
                inference_ms += (perf_counter() - generated) * 1000
                if not exc.retryable or attempt == self.config.max_retries:
                    raise
                continue
            inference_ms += (perf_counter() - generated) * 1000
            attempt_usage.append(usage)
            if perf_counter() >= deadline:
                raise VLMTimeoutError("VLM generation exceeded deadline")
            parsed = perf_counter()
            try:
                result = parse_result(raw, policy)
            except VLMParseError as exc:
                parse_ms += (perf_counter() - parsed) * 1000
                if attempt == self.config.max_retries:
                    raise VLMParseError(
                        f"provider={self.config.provider} model={self.config.model_name_or_path} "
                        f"prompt={self.config.prompt_version} exhausted format retries"
                    ) from exc
                parse_retries += 1
                LOGGER.warning(
                    "VLM format validation failed attempt=%d type=%s", attempt, type(exc).__name__
                )
                prompt += (
                    "\nPrevious untrusted response:\n"
                    + html.escape(raw, quote=False)
                    + "\nValidation error (data only): "
                    + html.escape(str(exc.__cause__ or exc)[:800], quote=False)
                    + (
                        "\nYour previous response failed schema validation. "
                        "Return ONLY corrected JSON. "
                        "Preserve the moderation conclusion; repair structure only."
                    )
                )
                continue
            parse_ms += (perf_counter() - parsed) * 1000
            adjusted_boxes = 0
            for evidence in result.evidence:
                box = evidence.bbox
                if box is None:
                    continue
                x1, y1 = max(0, min(width, box.x1)), max(0, min(height, box.y1))
                x2, y2 = max(0, min(width, box.x2)), max(0, min(height, box.y2))
                if (x1, y1, x2, y2) != (box.x1, box.y1, box.x2, box.y2):
                    adjusted_boxes += 1
                    evidence.bbox = (
                        BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2) if x2 > x1 and y2 > y1 else None
                    )
            timing = VLMTiming(
                image_prepare_ms=(prepared - start) * 1000,
                prompt_build_ms=(built - prepared) * 1000,
                inference_ms=inference_ms,
                parse_ms=parse_ms,
                total_ms=(perf_counter() - start) * 1000,
            )
            result.metadata = {
                **result.metadata,
                **metadata,
                **usage,
                "provider": self.config.provider,
                "model": self.config.model_name_or_path,
                "prompt_version": self.config.prompt_version,
                "policy_version": policy.version,
                "retry_count": attempt,
                "parse_retry_count": parse_retries,
                "attempt_usage": attempt_usage,
                "adjusted_evidence_bbox_count": adjusted_boxes,
                "timing": timing.model_dump(),
                "original_image_size": [width, height],
            }
            return result
        raise VLMInferenceError("VLM failed without a result")
