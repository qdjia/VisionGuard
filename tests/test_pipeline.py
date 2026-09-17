from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.moderation.policy import load_policy
from visionguard.moderation.schemas import ModerationResult
from visionguard.pipeline import MultimodalReviewPipeline
from visionguard.pipeline.artifacts import PipelineArtifactStore
from visionguard.pipeline.config import PipelineConfig, load_pipeline_config
from visionguard.pipeline.evaluator import evaluate_pipeline
from visionguard.pipeline.exceptions import (
    ArtifactSaveError,
    PipelineExecutionError,
    PipelineFatalError,
)
from visionguard.pipeline.schemas import ReviewResult
from visionguard.schemas import DetectionResult, OCRResult, OCRTiming, TimingInfo


class FakeDetector:
    def __init__(self, calls, *, error=False):
        self.calls = calls
        self.error = error

    def predict(self, image):
        self.calls.append("detector")
        if self.error:
            raise RuntimeError("detector unavailable")
        return DetectionResult(
            image_width=image.shape[1],
            image_height=image.shape[0],
            detections=[],
            timing=TimingInfo(),
            device="cpu",
            model_name="mock-detector",
        )


class FakeOCR:
    def __init__(self, calls, *, text="risk text", error=False):
        self.calls = calls
        self.text = text
        self.error = error

    def recognize(self, image):
        self.calls.append("ocr")
        if self.error:
            raise RuntimeError("ocr unavailable")
        return OCRResult(
            image_width=image.shape[1],
            image_height=image.shape[0],
            full_text=self.text,
            timing=OCRTiming(),
            device="cpu",
            engine_name="mock-ocr",
        )


class FakeBaseline:
    experiment_name = "mock-baseline-v1"

    def __init__(self, calls, *, error=False):
        self.calls = calls
        self.error = error

    def predict(self, text):
        self.calls.append("baseline")
        if self.error:
            raise RuntimeError("baseline unavailable")
        return TextModerationPrediction(
            text=text,
            label="sensitive",
            probability=0.75,
            threshold=0.5,
            source="ocr",
        )


class FakeVLM:
    def __init__(self, calls, *, error=False):
        self.calls = calls
        self.error = error
        self.context = None
        self.config = SimpleNamespace(
            provider="mock", model_name_or_path="mock-vlm", prompt_version="v1"
        )

    def analyze(self, image, context, policy):
        self.calls.append("vlm")
        self.context = context
        if self.error:
            raise RuntimeError("vlm unavailable")
        return ModerationResult(
            risk_level="low",
            categories=[],
            reason="Mock review completed.",
            evidence=[],
            confidence_score=0.8,
            requires_manual_review=False,
        )


@pytest.fixture
def policy():
    return load_policy("configs/moderation_policy.yaml")


def make_pipeline(policy, tmp_path, *, failures=(), text="risk text", **changes):
    calls = []
    config = PipelineConfig(
        save_artifacts=False,
        artifact_root=tmp_path / "artifacts",
        save_visualizations=False,
        **changes,
    )
    detector = FakeDetector(calls, error="detector" in failures)
    ocr = FakeOCR(calls, text=text, error="ocr" in failures)
    baseline = FakeBaseline(calls, error="baseline" in failures)
    vlm = FakeVLM(calls, error="vlm" in failures)
    pipeline = MultimodalReviewPipeline(
        detector,
        ocr,
        baseline,
        vlm,
        policy,
        config,
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    )
    return pipeline, calls, vlm


def image():
    return np.full((40, 80, 3), 255, dtype=np.uint8)


def test_config_and_complete_pipeline_data_flow(policy, tmp_path):
    assert load_pipeline_config("configs/pipeline.yaml").enable_vlm
    pipeline, calls, vlm = make_pipeline(policy, tmp_path)
    result = pipeline.run(image())
    assert calls == ["detector", "ocr", "baseline", "vlm"]
    assert result.review_status == "completed"
    assert result.final.risk_level == "low"
    assert result.baseline.source == "ocr"
    assert vlm.context.ocr_full_text == "risk text"
    assert vlm.context.baseline_prediction == result.baseline
    assert vlm.context.detections == []
    assert len(result.run_id) == 32
    assert len(result.image.sha256) == 64
    assert pipeline.run(image()).image.sha256 == result.image.sha256
    assert result.timing.total_ms >= result.timing.context_build_ms
    assert result.routing_signals.baseline_probability == 0.75
    assert result.metadata.component_versions["detector_model"] == "mock-detector"
    ReviewResult.model_validate_json(result.model_dump_json())


def test_detector_failure_isolated_and_empty_detections_are_normal(policy, tmp_path):
    pipeline, calls, vlm = make_pipeline(policy, tmp_path, failures={"detector"})
    result = pipeline.run(image())
    assert calls == ["detector", "ocr", "baseline", "vlm"]
    assert result.module_status["detector"].status == "failed"
    assert result.review_status == "partial"
    assert vlm.context.detections == []
    normal, _, _ = make_pipeline(policy, tmp_path)
    assert normal.run(image()).module_status["detector"].status == "success"


def test_ocr_failure_skips_baseline_but_vlm_continues(policy, tmp_path):
    pipeline, calls, vlm = make_pipeline(policy, tmp_path, failures={"ocr"})
    result = pipeline.run(image())
    assert calls == ["detector", "ocr", "vlm"]
    assert result.module_status["baseline"].status == "skipped"
    assert result.module_status["baseline"].error_message == "OCR result unavailable"
    assert vlm.context.ocr_full_text == ""
    assert result.review_status == "partial"


def test_empty_ocr_skips_baseline_without_failure(policy, tmp_path):
    pipeline, calls, _ = make_pipeline(policy, tmp_path, text="  ")
    result = pipeline.run(image())
    assert calls == ["detector", "ocr", "vlm"]
    assert result.module_status["baseline"].status == "skipped"
    assert result.module_status["baseline"].error_message == "empty OCR text"
    assert result.review_status == "completed"


def test_baseline_failure_does_not_block_vlm(policy, tmp_path):
    pipeline, calls, vlm = make_pipeline(policy, tmp_path, failures={"baseline"})
    result = pipeline.run(image())
    assert calls == ["detector", "ocr", "baseline", "vlm"]
    assert vlm.context.baseline_prediction is None
    assert result.module_status["baseline"].error_type == "RuntimeError"
    assert result.review_status == "partial"


def test_vlm_failure_never_defaults_to_low(policy, tmp_path):
    pipeline, _, _ = make_pipeline(policy, tmp_path, failures={"vlm"})
    result = pipeline.run(image())
    assert result.review_status == "partial"
    assert result.final.risk_level == "medium"
    assert result.final.categories == []
    assert result.final.requires_manual_review
    assert result.vlm is None


def test_image_load_is_fatal_and_fail_fast_stops(policy, tmp_path):
    pipeline, _, _ = make_pipeline(policy, tmp_path)
    with pytest.raises(PipelineFatalError) as fatal:
        pipeline.run(tmp_path / "missing.jpg")
    assert len(fatal.value.run_id) == 32
    fail_fast, calls, _ = make_pipeline(policy, tmp_path, failures={"detector"}, fail_fast=True)
    with pytest.raises(PipelineExecutionError) as stopped:
        fail_fast.run(image())
    assert stopped.value.module == "detector"
    assert calls == ["detector"]


def test_truncation_signal_and_disabled_dependency_validation(policy, tmp_path):
    pipeline, _, _ = make_pipeline(policy, tmp_path, text="x" * 10, max_ocr_chars_for_baseline=4)
    result = pipeline.run(image())
    assert result.baseline.text == "xxxx"
    assert result.routing_signals.ocr_text_truncated_for_baseline
    with pytest.raises(ValueError, match="detector"):
        MultimodalReviewPipeline(
            None,
            FakeOCR([]),
            FakeBaseline([]),
            FakeVLM([]),
            policy,
            PipelineConfig(save_artifacts=False),
            fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
        )
    disabled = MultimodalReviewPipeline(
        None,
        None,
        None,
        None,
        policy,
        PipelineConfig(
            save_artifacts=False,
            enable_detector=False,
            enable_ocr=False,
            enable_text_baseline=False,
            enable_vlm=False,
        ),
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    ).run(image())
    assert disabled.review_status == "failed"
    assert disabled.final.risk_level == "medium"
    assert disabled.final.requires_manual_review


def test_artifacts_and_input_copy(policy, tmp_path):
    calls = []
    config = PipelineConfig(
        artifact_root=tmp_path / "runs",
        save_visualizations=True,
        save_input_copy=True,
    )
    pipeline = MultimodalReviewPipeline(
        FakeDetector(calls),
        FakeOCR(calls),
        FakeBaseline(calls),
        FakeVLM(calls),
        policy,
        config,
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    )
    result = pipeline.run(image())
    directory = tmp_path / "runs" / result.run_id
    expected = {
        "input_metadata.json",
        "detection.json",
        "ocr.json",
        "baseline.json",
        "vlm.json",
        "fusion.json",
        "review_result.json",
        "timing.json",
        "input.jpg",
    }
    assert expected.issubset({path.name for path in directory.iterdir()})
    assert (directory / "visualizations" / "detection.jpg").is_file()
    assert (directory / "visualizations" / "ocr.jpg").is_file()
    saved = ReviewResult.model_validate_json(
        (directory / "review_result.json").read_text(encoding="utf-8")
    )
    assert saved.artifacts.status == "success"
    assert saved.timing.artifact_save_ms > 0

    failed_calls = []
    failed_pipeline = MultimodalReviewPipeline(
        FakeDetector(failed_calls, error=True),
        FakeOCR(failed_calls),
        FakeBaseline(failed_calls),
        FakeVLM(failed_calls),
        policy,
        config.model_copy(update={"save_visualizations": False}),
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    )
    partial = failed_pipeline.run(image())
    error_file = tmp_path / "runs" / partial.run_id / "error.json"
    assert error_file.is_file()
    assert "detector" in error_file.read_text(encoding="utf-8")


class FailingArtifactStore(PipelineArtifactStore):
    def save(self, result, image):
        raise ArtifactSaveError("disk unavailable", run_id=result.run_id, cause=OSError("full"))


def test_artifact_failure_does_not_erase_review(policy, tmp_path):
    calls = []
    config = PipelineConfig(artifact_root=tmp_path / "runs", save_visualizations=False)
    pipeline = MultimodalReviewPipeline(
        FakeDetector(calls),
        FakeOCR(calls),
        FakeBaseline(calls),
        FakeVLM(calls),
        policy,
        config,
        fusion_engine=RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
        artifact_store=FailingArtifactStore(config),
    )
    result = pipeline.run(image())
    assert result.review_status == "completed"
    assert result.artifacts.status == "failed"
    assert result.artifacts.error_type == "OSError"


def test_evaluation_outputs_engineering_metrics(policy, tmp_path):
    pipeline, _, _ = make_pipeline(policy, tmp_path)
    assert cv2.imwrite(str(tmp_path / "safe.png"), image())
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        '{"image":"safe.png","risk_level":"low","categories":[]}\n', encoding="utf-8"
    )
    summary = evaluate_pipeline(pipeline, manifest, tmp_path / "evaluation")
    assert summary["metrics"]["risk_level_accuracy"] == 1
    assert summary["metrics"]["pipeline_failure_rate"] == 0
    assert "Engineering-chain" in summary["scope_note"]
    assert (tmp_path / "evaluation" / "summary.json").is_file()
