"""Small model-free fixtures shared by Phase 12 API tests."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import cv2
import numpy as np

from visionguard.api import create_app, load_api_config
from visionguard.api.dependencies import ServiceContainer
from visionguard.moderation.schemas import ModerationCategory
from visionguard.pipeline.schemas import (
    ArtifactState,
    ArtifactStatus,
    FinalReview,
    ModuleState,
    PipelineTiming,
    ReviewImage,
    ReviewMetadata,
    ReviewModuleStatus,
    ReviewResult,
    ReviewStatus,
)
from visionguard.routing.schemas import (
    DecisionSource,
    Route,
    RoutingDecision,
    RoutingReasonCode,
    RoutingSignals,
)
from visionguard.schemas import (
    BoundingBox,
    Detection,
    DetectionResult,
    OCRResult,
    OCRScope,
    OCRTextBlock,
    OCRTiming,
    TimingInfo,
)

ROOT = Path(__file__).resolve().parents[1]


def image_bytes() -> bytes:
    image = np.full((32, 48, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def make_result(*, partial: bool = False, artifact_saved: bool = False) -> ReviewResult:
    signals = RoutingSignals(
        detection_count=1,
        ocr_block_count=1,
        ocr_text_length=4,
        detector_status="success",
        ocr_status="success",
        baseline_status="success",
    )
    statuses = {
        name: ReviewModuleStatus(status=ModuleState.SUCCESS, latency_ms=1)
        for name in ("detector", "ocr", "baseline", "vlm")
    }
    if partial:
        statuses["vlm"] = ReviewModuleStatus(
            status=ModuleState.FAILED,
            latency_ms=1,
            error_type="MockFailure",
            error_message="mock failure",
        )
    return ReviewResult(
        run_id=uuid4().hex,
        image=ReviewImage(
            input_type="ndarray",
            width=48,
            height=32,
            sha256="0" * 64,
        ),
        detection=DetectionResult(
            image_width=48,
            image_height=32,
            detections=[
                Detection(
                    class_id=0,
                    class_name="watermark",
                    confidence=0.8,
                    bbox=BoundingBox(x1=1, y1=2, x2=10, y2=12),
                )
            ],
            timing=TimingInfo(total_ms=1),
            device="mock",
            model_name="mock.pt",
        ),
        ocr=OCRResult(
            image_width=48,
            image_height=32,
            blocks=[
                OCRTextBlock(
                    text="test",
                    confidence=0.9,
                    polygon=[(1, 1), (9, 1), (9, 8), (1, 8)],
                    bbox=BoundingBox(x1=1, y1=1, x2=9, y2=8),
                    scope=OCRScope.FULL_IMAGE,
                )
            ],
            full_text="test",
            timing=OCRTiming(total_ms=1),
            device="mock",
            engine_name="MockOCR",
            raw_block_count=1,
            filtered_block_count=1,
        ),
        final=FinalReview(
            risk_level="low",
            categories=[ModerationCategory(name="watermark", score=0.2)],
            reason="Mock structured review.",
            confidence_score=0.9,
            requires_manual_review=partial,
        ),
        review_status=ReviewStatus.PARTIAL if partial else ReviewStatus.COMPLETED,
        decision_source=DecisionSource.FUSION,
        routing=RoutingDecision(
            route=Route.FAST_PATH,
            call_vlm=False,
            reason_codes=[RoutingReasonCode.SAFE_CONSENSUS],
            explanation="Mock routing decision.",
            signals=signals,
            policy_version="routing_v1",
        ),
        module_status=statuses,
        timing=PipelineTiming(total_ms=7, detector_ms=1, ocr_ms=1, fusion_ms=1),
        routing_signals=signals,
        artifacts=ArtifactStatus(
            status=ArtifactState.SUCCESS if artifact_saved else ArtifactState.SKIPPED
        ),
        metadata=ReviewMetadata(
            pipeline_version="v1",
            policy_version="policy_v1",
            prompt_version="v1",
            routing_policy_version="routing_v1",
            fusion_policy_version="fusion_v1",
            timestamp=datetime.now(UTC),
        ),
    )


class FakePipeline:
    def __init__(
        self,
        *,
        mode: str = "cascaded",
        delay: float = 0,
        partial: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.mode = mode
        self.delay = delay
        self.partial = partial
        self.error = error
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.detector = SimpleNamespace(model_name="models/mock.pt")
        self.ocr_engine = SimpleNamespace()
        self.text_baseline = SimpleNamespace(experiment_name="baseline_v1")
        self.vlm_provider = SimpleNamespace(
            config=SimpleNamespace(prompt_version="v1", model_name_or_path="models/mock-vlm")
        )
        self.fusion_engine = SimpleNamespace(version="fusion_v1")
        self.routing_policy = SimpleNamespace(version="routing_v1")
        self.config = SimpleNamespace(pipeline_version="v1")

    def run(self, image, *, save_artifacts=None):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.error is not None:
                raise self.error
            return make_result(partial=self.partial, artifact_saved=bool(save_artifacts))
        finally:
            with self.lock:
                self.active -= 1


def make_test_app(
    *,
    full: FakePipeline | None = None,
    cascaded: FakePipeline | None = None,
    api_updates: dict | None = None,
):
    config = load_api_config(ROOT / "configs" / "api.yaml")
    updates = {
        "warmup_on_startup": False,
        "save_artifacts": False,
        "request_timeout_seconds": 2,
        "shutdown_grace_seconds": 2,
        **(api_updates or {}),
    }
    config = config.model_copy(update={"api": config.api.model_copy(update=updates)})
    full_pipeline = full or FakePipeline(mode="full")
    cascaded_pipeline = cascaded or FakePipeline(mode="cascaded")
    state = {"initializations": 0, "container": None}

    def factory(api_config):
        state["initializations"] += 1
        container = ServiceContainer(
            config=api_config,
            full_pipeline=full_pipeline,
            cascaded_pipeline=cascaded_pipeline,
            semaphore=asyncio.Semaphore(api_config.api.max_concurrent_inference),
        )
        state["container"] = container
        return container

    return create_app(config=config, container_factory=factory), state


def upload(client, *, params=None, content: bytes | None = None, mime="image/png"):
    return client.post(
        "/v1/review",
        params=params or {},
        files={"file": ("sample.png", content if content is not None else image_bytes(), mime)},
    )
