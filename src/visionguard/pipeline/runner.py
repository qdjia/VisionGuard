"""Application bootstrap that initializes every enabled model exactly once."""

from pathlib import Path

from visionguard.baseline import TextModerationBaseline, load_baseline_config
from visionguard.config import load_config
from visionguard.detection import YOLODetector
from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.moderation.policy import load_policy
from visionguard.ocr import OCREngine, load_ocr_config
from visionguard.pipeline.adapters import TextBaselineAdapter
from visionguard.pipeline.cascaded import CascadedReviewPipeline
from visionguard.pipeline.config import load_pipeline_config
from visionguard.pipeline.review import MultimodalReviewPipeline
from visionguard.routing import RoutingPolicy, load_routing_config
from visionguard.vlm import create_provider, load_vlm_config


def build_pipeline(
    *,
    pipeline_config: str | Path,
    detector_config: str | Path,
    ocr_config: str | Path,
    baseline_config: str | Path,
    vlm_config: str | Path,
    policy: str | Path,
    fusion_config: str | Path = "configs/fusion.yaml",
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
        fusion_engine=RiskFusionEngine(load_fusion_config(fusion_config)),
    )


def build_cascaded_pipeline(
    *,
    pipeline_config: str | Path,
    routing_config: str | Path,
    detector_config: str | Path,
    ocr_config: str | Path,
    baseline_config: str | Path,
    vlm_config: str | Path,
    policy: str | Path,
    fusion_config: str | Path = "configs/fusion.yaml",
) -> CascadedReviewPipeline:
    """Load one shared model set and add a pure rule-based routing policy."""

    full = build_pipeline(
        pipeline_config=pipeline_config,
        detector_config=detector_config,
        ocr_config=ocr_config,
        baseline_config=baseline_config,
        vlm_config=vlm_config,
        policy=policy,
        fusion_config=fusion_config,
    )
    return CascadedReviewPipeline(
        full.detector,
        full.ocr_engine,
        full.text_baseline,
        full.vlm_provider,
        full.policy,
        full.config,
        routing_policy=RoutingPolicy(load_routing_config(routing_config)),
        fusion_engine=full.fusion_engine,
    )


def build_pipeline_pair(
    *,
    full_pipeline_config: str | Path,
    cascaded_pipeline_config: str | Path,
    routing_config: str | Path,
    detector_config: str | Path,
    ocr_config: str | Path,
    baseline_config: str | Path,
    vlm_config: str | Path,
    policy: str | Path,
    fusion_config: str | Path = "configs/fusion.yaml",
) -> tuple[MultimodalReviewPipeline, CascadedReviewPipeline]:
    """Build full/cascaded modes over the exact same initialized model instances."""

    full = build_pipeline(
        pipeline_config=full_pipeline_config,
        detector_config=detector_config,
        ocr_config=ocr_config,
        baseline_config=baseline_config,
        vlm_config=vlm_config,
        policy=policy,
        fusion_config=fusion_config,
    )
    cascaded_config = load_pipeline_config(cascaded_pipeline_config)
    cascaded = CascadedReviewPipeline(
        full.detector,
        full.ocr_engine,
        full.text_baseline,
        full.vlm_provider,
        full.policy,
        cascaded_config,
        routing_policy=RoutingPolicy(load_routing_config(routing_config)),
        fusion_engine=full.fusion_engine,
    )
    return full, cascaded
