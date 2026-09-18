from types import SimpleNamespace

import numpy as np

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.benchmarking import BatchReviewRunner
from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.moderation.policy import load_policy
from visionguard.moderation.schemas import ModerationResult
from visionguard.pipeline.cascaded import CascadedReviewPipeline
from visionguard.pipeline.config import PipelineConfig
from visionguard.pipeline.schemas import ReviewResult
from visionguard.routing import RoutingPolicy, load_routing_config
from visionguard.schemas import (
    BoundingBox,
    Detection,
    DetectionResult,
    OCRResult,
    OCRTextBlock,
    OCRTiming,
    TimingInfo,
)


class Detector:
    def __init__(self, *, risky=False, error=False):
        self.risky = risky
        self.error = error
        self.batch_calls = 0

    def predict(self, image):
        if self.error:
            raise RuntimeError("detector failed")
        detections = []
        if self.risky:
            detections.append(
                Detection(
                    class_id=0,
                    class_name="weapon",
                    confidence=0.9,
                    bbox=BoundingBox(x1=1, y1=1, x2=10, y2=10),
                )
            )
        return DetectionResult(
            image_width=20,
            image_height=20,
            detections=detections,
            timing=TimingInfo(),
            device="cpu",
            model_name="mock-detector",
        )

    def predict_batch(self, images):
        self.batch_calls += 1
        return [self.predict(image) for image in images]


class OCR:
    def __init__(self, *, text="safe text", confidence=0.9, error=False):
        self.text = text
        self.confidence = confidence
        self.error = error

    def recognize(self, image):
        if self.error:
            raise RuntimeError("ocr failed")
        blocks = []
        if self.text:
            blocks.append(
                OCRTextBlock(
                    text=self.text,
                    confidence=self.confidence,
                    polygon=[(1, 1), (10, 1), (10, 10), (1, 10)],
                    bbox=BoundingBox(x1=1, y1=1, x2=10, y2=10),
                )
            )
        return OCRResult(
            image_width=20,
            image_height=20,
            blocks=blocks,
            full_text=self.text,
            timing=OCRTiming(),
            device="cpu",
            engine_name="mock-ocr",
            raw_block_count=len(blocks),
            filtered_block_count=len(blocks),
        )


class Baseline:
    experiment_name = "mock-baseline"

    def __init__(self, probability=0.05, *, error=False):
        self.probability = probability
        self.error = error

    def predict(self, text):
        if self.error:
            raise RuntimeError("baseline failed")
        return TextModerationPrediction(
            text=text,
            label="sensitive" if self.probability >= 0.5 else "normal",
            probability=self.probability,
            threshold=0.5,
            source="ocr",
        )

    def predict_batch(self, texts):
        return [self.predict(text) for text in texts]


class VLM:
    def __init__(self, *, error=False):
        self.error = error
        self.calls = 0
        self.config = SimpleNamespace(
            provider="mock", model_name_or_path="mock-vlm", prompt_version="v1"
        )

    def analyze(self, image, context, policy):
        self.calls += 1
        if self.error:
            raise RuntimeError("vlm failed")
        return ModerationResult(
            risk_level="high",
            categories=[{"name": "sensitive_text", "score": 0.9}],
            reason="Mock risk evidence.",
            evidence=[{"type": "semantic", "description": "Mock evidence"}],
            confidence_score=0.9,
            requires_manual_review=True,
        )


def pipeline(
    tmp_path,
    *,
    detector=None,
    ocr=None,
    baseline=None,
    vlm=None,
    artifacts=False,
    routing_policy=None,
):
    config = PipelineConfig(
        save_artifacts=artifacts,
        save_visualizations=False,
        artifact_root=tmp_path / "routing",
    )
    provider = vlm or VLM()
    result = CascadedReviewPipeline(
        detector or Detector(),
        ocr or OCR(),
        baseline or Baseline(),
        provider,
        load_policy("configs/moderation_policy.yaml"),
        config,
        routing_policy=routing_policy or RoutingPolicy(load_routing_config("configs/routing.yaml")),
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    )
    return result, provider


def test_safe_consensus_skips_vlm_and_writes_routing_artifact(tmp_path):
    review, vlm = pipeline(tmp_path, artifacts=True)
    result = review.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert result.routing.route == "fast_path"
    assert result.decision_source == "fusion"
    assert result.final.risk_level == "low"
    assert result.vlm is None
    assert result.module_status["vlm"].status == "skipped"
    assert result.timing.vlm_ms == 0
    assert vlm.calls == 0
    assert (tmp_path / "routing" / result.run_id / "routing.json").is_file()
    assert (tmp_path / "routing" / result.run_id / "fusion.json").is_file()


def test_mixed_batch_preserves_order_and_selectively_calls_vlm(tmp_path):
    class SelectiveDetector(Detector):
        def predict_batch(self, images):
            self.batch_calls += 1
            return [Detector(risky=bool(image[0, 0, 0])).predict(image) for image in images]

    detector = SelectiveDetector()
    review, vlm = pipeline(tmp_path, detector=detector)
    safe = np.zeros((20, 20, 3), dtype=np.uint8)
    risky = np.ones((20, 20, 3), dtype=np.uint8)

    results = BatchReviewRunner(review).run([safe, risky])

    assert detector.batch_calls == 1
    assert [result.routing.call_vlm for result in results] == [False, True]
    assert [result.image.sha256 for result in results] == [
        results[0].image.sha256,
        results[1].image.sha256,
    ]
    assert results[0].image.sha256 != results[1].image.sha256
    assert vlm.calls == 1


def test_high_risk_detection_routes_to_vlm(tmp_path):
    review, vlm = pipeline(tmp_path, detector=Detector(risky=True))
    result = review.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert result.routing.route == "vlm_path"
    assert "high_risk_detection" in result.routing.reason_codes
    assert result.decision_source == "fusion"
    assert result.final.risk_level == "high"
    assert vlm.calls == 1


def test_stage_one_failure_cannot_fast_pass(tmp_path):
    for dependency in ("detector", "ocr", "baseline"):
        kwargs = {
            "detector": Detector(error=dependency == "detector"),
            "ocr": OCR(error=dependency == "ocr"),
            "baseline": Baseline(error=dependency == "baseline"),
        }
        review, vlm = pipeline(tmp_path, **kwargs)
        result = review.run(np.zeros((20, 20, 3), dtype=np.uint8))
        assert result.routing.call_vlm
        assert "module_failure" in result.routing.reason_codes
        assert vlm.calls == 1


def test_vlm_failure_is_partial_manual_review_not_low(tmp_path):
    review, _ = pipeline(tmp_path, baseline=Baseline(0.5), vlm=VLM(error=True))
    result = review.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert result.routing.call_vlm
    assert result.review_status == "partial"
    assert result.final.risk_level == "medium"
    assert result.final.requires_manual_review


def test_low_confidence_and_empty_ocr_route_to_vlm(tmp_path):
    low_quality, _ = pipeline(tmp_path, ocr=OCR(confidence=0.3))
    low_result = low_quality.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert "ocr_low_confidence" in low_result.routing.reason_codes
    empty, _ = pipeline(tmp_path, ocr=OCR(text=""))
    empty_result = empty.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert {"no_text", "insufficient_evidence"}.issubset(empty_result.routing.reason_codes)


def test_fast_path_fusion_safety_guard_overrides_route(tmp_path):
    routing_config = load_routing_config("configs/routing.yaml")
    relaxed_detector = routing_config.detector.model_copy(
        update={"high_risk_conf_threshold": 0.99, "suspicious_conf_threshold": 0.99}
    )
    relaxed_policy = RoutingPolicy(routing_config.model_copy(update={"detector": relaxed_detector}))
    review, vlm = pipeline(
        tmp_path,
        detector=Detector(risky=True),
        routing_policy=relaxed_policy,
    )
    result = review.run(np.zeros((20, 20, 3), dtype=np.uint8))
    assert result.routing.original_route == "fast_path"
    assert result.routing.routing_overridden_by_fusion
    assert result.routing.route == "vlm_path"
    assert "fusion_safety_guard" in result.routing.reason_codes
    assert result.fusion.metadata.routing_overridden_by_fusion
    assert result.fusion.requires_manual_review
    assert vlm.calls == 1


def test_phase_seven_result_json_remains_loadable(tmp_path):
    review, _ = pipeline(tmp_path)
    payload = review.run(np.zeros((20, 20, 3), dtype=np.uint8)).model_dump(mode="json")
    payload.pop("decision_source")
    payload.pop("routing")
    payload.pop("fusion")
    payload["timing"].pop("routing_ms")
    payload["timing"].pop("fusion_ms")
    payload["metadata"].pop("routing_policy_version")
    payload["metadata"].pop("fusion_policy_version")
    payload["final"] = {
        "risk_level": "low",
        "categories": [],
        "reason": "Historical Phase 7 result.",
        "confidence_score": None,
        "requires_manual_review": False,
    }
    for field in (
        "mean_detection_confidence",
        "high_risk_detection_count",
        "suspicious_high_risk_detection_count",
        "has_high_risk_class",
        "ocr_text_length",
        "detector_status",
        "ocr_status",
        "baseline_status",
        "evidence_conflict",
        "insufficient_evidence",
    ):
        payload["routing_signals"].pop(field)
    restored = ReviewResult.model_validate(payload)
    assert restored.routing is None
    assert restored.fusion is None
    assert restored.decision_source == "full_pipeline"
