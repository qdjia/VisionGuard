"""Application bootstrap that initializes every enabled model exactly once."""

from pathlib import Path

from visionguard.baseline import TextModerationBaseline, load_baseline_config
from visionguard.config import load_config
from visionguard.detection import YOLODetector
from visionguard.moderation.policy import load_policy
from visionguard.ocr import OCREngine, load_ocr_config
from visionguard.pipeline.adapters import TextBaselineAdapter
from visionguard.pipeline.config import load_pipeline_config
from visionguard.pipeline.review import MultimodalReviewPipeline
from visionguard.vlm import create_provider, load_vlm_config


def build_pipeline(
    *,
    pipeline_config: str | Path,
    detector_config: str | Path,
    ocr_config: str | Path,
    baseline_config: str | Path,
    vlm_config: str | Path,
    policy: str | Path,
) -> MultimodalReviewPipeline:
    """Load enabled dependencies in the bootstrap layer, never inside the pipeline."""

    config = load_pipeline_config(pipeline_config)
    detector = (
        YOLODetector(load_config(detector_config).detection) if config.enable_detector else None
    )
    ocr_engine = OCREngine(load_ocr_config(ocr_config)) if config.enable_ocr else None
    baseline = None
    if config.enable_text_baseline:
        baseline_settings = load_baseline_config(baseline_config)
        experiment = baseline_settings.artifacts_dir / baseline_settings.experiment_name
        baseline = TextBaselineAdapter(TextModerationBaseline.load(experiment))
    provider = create_provider(load_vlm_config(vlm_config)) if config.enable_vlm else None
    return MultimodalReviewPipeline(
        detector,
        ocr_engine,
        baseline,
        provider,
        load_policy(policy),
        config,
    )
