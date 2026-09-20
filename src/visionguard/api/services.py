"""Upload validation, bounded inference execution, and public response adaptation."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from time import perf_counter

import anyio
import cv2
import numpy as np
from fastapi import UploadFile

from visionguard.api.dependencies import ServiceContainer
from visionguard.api.errors import (
    APIErrorCode,
    APIServiceError,
    ImageValidationError,
    InferenceTimeoutError,
    ServiceNotReadyError,
    UnsupportedMediaTypeError,
    UploadTooLargeError,
)
from visionguard.api.schemas import (
    APICategory,
    APIDetails,
    APIDetectionDetail,
    APIResponseMetadata,
    APIReviewDecision,
    APIReviewResponse,
    APIRoutingSummary,
    APITiming,
)
from visionguard.pipeline.exceptions import PipelineError
from visionguard.pipeline.schemas import ReviewResult

LOGGER = logging.getLogger(__name__)


async def decode_upload(upload: UploadFile, container: ServiceContainer) -> tuple[np.ndarray, int]:
    settings = container.config.api
    if upload.content_type not in settings.allowed_image_types:
        raise UnsupportedMediaTypeError()
    content = bytearray()
    while True:
        chunk = await upload.read(settings.upload_chunk_bytes)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.max_upload_bytes:
            raise UploadTooLargeError()
    if not content:
        raise ImageValidationError("Uploaded file is empty.")
    encoded = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ImageValidationError()
    height, width = image.shape[:2]
    if (
        max(width, height) > settings.max_image_dimension
        or width * height > settings.max_image_pixels
    ):
        raise ImageValidationError("Decoded image dimensions exceed the configured limit.")
    return np.ascontiguousarray(image), len(content)


class ReviewService:
    def __init__(self, container: ServiceContainer) -> None:
        self.container = container

    async def review(
        self,
        image: np.ndarray,
        *,
        request_id: str,
        request_started: float,
        pipeline_mode: str | None,
        save_artifacts: bool | None,
        include_details: bool,
    ) -> APIReviewResponse:
        container = self.container
        settings = container.config.api
        if not container.ready or not container.accepting_requests:
            raise ServiceNotReadyError()
        mode = pipeline_mode or settings.default_pipeline_mode
        if mode not in settings.allowed_pipeline_modes:
            raise APIServiceError(
                APIErrorCode.INVALID_PIPELINE_MODE,
                "Requested pipeline mode is not allowed.",
                400,
            )
        save = settings.save_artifacts if save_artifacts is None else save_artifacts
        pipeline = container.pipeline_for(mode)
        queued_at = perf_counter()
        state = {"acquired": False, "queue_wait_ms": 0.0, "inference_ms": 0.0}

        async def guarded_run() -> ReviewResult:
            async with container.semaphore:
                state["acquired"] = True
                state["queue_wait_ms"] = (perf_counter() - queued_at) * 1000
                started = perf_counter()
                operation = partial(pipeline.run, image, save_artifacts=save)
                try:
                    return await anyio.to_thread.run_sync(operation)
                finally:
                    state["inference_ms"] = (perf_counter() - started) * 1000

        task = asyncio.create_task(guarded_run(), name=f"review-{request_id}")
        container.track(task)
        try:
            result = await asyncio.wait_for(
                asyncio.shield(task),
                timeout=settings.request_timeout_seconds,
            )
        except TimeoutError as exc:
            phase = "inference" if state["acquired"] else "queue"
            if not state["acquired"]:
                task.cancel()
            LOGGER.warning("request_id=%s inference timeout phase=%s", request_id, phase)
            raise InferenceTimeoutError(phase) from exc
        except PipelineError as exc:
            raise APIServiceError(
                APIErrorCode.PIPELINE_FAILURE,
                "Pipeline could not complete the review.",
                500,
                run_id=exc.run_id,
            ) from exc

        serialization_started = perf_counter()
        response = adapt_review_result(
            result,
            request_id=request_id,
            pipeline_mode=mode,
            queue_wait_ms=state["queue_wait_ms"],
            inference_ms=state["inference_ms"],
            include_details=include_details,
        )
        # FastAPI performs final encoding after this method returns. A dry
        # serialization keeps this timing observable without bypassing its schema layer.
        response.model_dump_json()
        response.timing.response_serialization_ms = (perf_counter() - serialization_started) * 1000
        response.timing.request_total_ms = (perf_counter() - request_started) * 1000
        LOGGER.info(
            "request_id=%s run_id=%s endpoint=/v1/review mode=%s status=%s total_ms=%.2f",
            request_id,
            result.run_id,
            mode,
            result.review_status,
            response.timing.request_total_ms,
        )
        return response


def adapt_review_result(
    review: ReviewResult,
    *,
    request_id: str,
    pipeline_mode: str,
    queue_wait_ms: float,
    inference_ms: float,
    include_details: bool,
) -> APIReviewResponse:
    final = review.final
    categories = [APICategory(name=item.name, score=item.score) for item in final.categories]
    routing = None
    if review.routing is not None:
        routing = APIRoutingSummary(
            route=review.routing.route,
            call_vlm=review.routing.call_vlm,
            reason_codes=[str(item) for item in review.routing.reason_codes],
        )
    details = _details(review) if include_details else None
    timing = review.timing
    return APIReviewResponse(
        request_id=request_id,
        run_id=review.run_id,
        status=review.review_status,
        result=APIReviewDecision(
            risk_level=final.risk_level,
            risk_score=getattr(final, "risk_score", None),
            categories=categories,
            requires_manual_review=final.requires_manual_review,
            reason=final.reason,
            decision_source=review.decision_source,
        ),
        routing=routing,
        modules={name: status.status for name, status in review.module_status.items()},
        timing=APITiming(
            request_total_ms=0,
            queue_wait_ms=queue_wait_ms,
            inference_ms=inference_ms,
            response_serialization_ms=0,
            pipeline_total_ms=timing.total_ms,
            detector_ms=timing.detector_ms,
            ocr_ms=timing.ocr_ms,
            baseline_ms=timing.baseline_ms,
            routing_ms=timing.routing_ms,
            vlm_ms=timing.vlm_ms,
            fusion_ms=timing.fusion_ms,
        ),
        metadata=APIResponseMetadata(
            pipeline_mode=pipeline_mode,
            pipeline_version=review.metadata.pipeline_version,
            routing_policy_version=review.metadata.routing_policy_version,
            fusion_policy_version=review.metadata.fusion_policy_version,
            prompt_version=review.metadata.prompt_version,
        ),
        artifact_saved=str(review.artifacts.status) == "success",
        artifact_id=review.run_id if str(review.artifacts.status) == "success" else None,
        details=details,
    )


def _details(review: ReviewResult) -> APIDetails:
    detections = review.detection.detections if review.detection else []
    blocks = review.ocr.blocks if review.ocr else []
    confidences = [item.confidence for item in blocks]
    fusion_sources = sorted(
        {evidence.source for evidence in (review.fusion.evidence_summary if review.fusion else [])}
    )
    return APIDetails(
        detections=[
            APIDetectionDetail(
                class_name=item.class_name,
                confidence=item.confidence,
                bbox=item.bbox,
            )
            for item in detections
        ],
        ocr_block_count=len(blocks),
        ocr_text_length=len(review.ocr.full_text) if review.ocr else 0,
        mean_ocr_confidence=(sum(confidences) / len(confidences) if confidences else None),
        baseline_label=review.baseline.label if review.baseline else None,
        baseline_probability=review.baseline.probability if review.baseline else None,
        vlm_risk_level=review.vlm.risk_level if review.vlm else None,
        vlm_categories=[item.name for item in review.vlm.categories] if review.vlm else [],
        vlm_confidence=review.vlm.confidence_score if review.vlm else None,
        fusion_sources=fusion_sources,
    )
