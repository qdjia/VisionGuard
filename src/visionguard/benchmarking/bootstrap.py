"""Shared CLI bootstrap kept outside the benchmark measurement boundary."""

from pathlib import Path
from time import perf_counter

from visionguard.pipeline.artifacts import PipelineArtifactStore
from visionguard.pipeline.runner import build_cascaded_pipeline, build_pipeline, build_pipeline_pair

DEFAULT_PATHS = {
    "detector_config": "configs/detector.yaml",
    "ocr_config": "configs/ocr.yaml",
    "baseline_config": "configs/baseline_text.yaml",
    "vlm_config": "configs/vlm.yaml",
    "policy": "configs/moderation_policy.yaml",
    "fusion_config": "configs/fusion.yaml",
    "routing_config": "configs/routing.yaml",
    "full_pipeline_config": "configs/pipeline.yaml",
    "cascaded_pipeline_config": "configs/pipeline_cascaded.yaml",
}


def add_model_arguments(parser) -> None:
    for name, default in DEFAULT_PATHS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", default=default)


def _disable_artifacts(pipeline) -> None:
    pipeline.config = pipeline.config.model_copy(
        update={
            "save_artifacts": False,
            "save_input_copy": False,
            "save_intermediate_json": False,
            "save_visualizations": False,
            "trace": pipeline.config.trace.model_copy(update={"enabled": False}),
        }
    )
    pipeline.artifact_store = PipelineArtifactStore(pipeline.config)


def build_one(args, mode: str):
    started = perf_counter()
    components = {}
    common = {
        "detector_config": args.detector_config,
        "ocr_config": args.ocr_config,
        "baseline_config": args.baseline_config,
        "vlm_config": args.vlm_config,
        "policy": args.policy,
        "fusion_config": args.fusion_config,
    }
    if mode == "full":
        pipeline = build_pipeline(
            pipeline_config=args.full_pipeline_config,
            startup_timings=components,
            **common,
        )
    else:
        pipeline = build_cascaded_pipeline(
            pipeline_config=args.cascaded_pipeline_config,
            routing_config=args.routing_config,
            startup_timings=components,
            **common,
        )
    startup_ms = (perf_counter() - started) * 1000
    _disable_artifacts(pipeline)
    return pipeline, startup_ms, components


def build_pair(args):
    started = perf_counter()
    components = {}
    full, cascaded = build_pipeline_pair(
        full_pipeline_config=args.full_pipeline_config,
        cascaded_pipeline_config=args.cascaded_pipeline_config,
        routing_config=args.routing_config,
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
        fusion_config=args.fusion_config,
        startup_timings=components,
    )
    startup_ms = (perf_counter() - started) * 1000
    _disable_artifacts(full)
    _disable_artifacts(cascaded)
    return full, cascaded, startup_ms, components


def ensure_new_output(path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"benchmark output already exists: {output}")
    return output
