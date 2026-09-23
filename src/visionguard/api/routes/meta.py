"""Non-sensitive runtime metadata for reproducibility and operations."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from visionguard.api.dependencies import ServiceContainer, get_container
from visionguard.api.schemas import MetaResponse

router = APIRouter(prefix="/v1", tags=["metadata"])


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return Path(text.replace("\\", "/")).name or None


@router.get("/meta", response_model=MetaResponse)
async def metadata(
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> MetaResponse:
    full = container.full_pipeline
    cascaded = container.cascaded_pipeline
    detector = getattr(full, "detector", None)
    ocr = getattr(full, "ocr_engine", None)
    baseline = getattr(full, "text_baseline", None)
    vlm = getattr(full, "vlm_provider", None)
    vlm_config = getattr(vlm, "config", None)
    routing = getattr(cascaded, "routing_policy", None)
    fusion = getattr(full, "fusion_engine", None)
    return MetaResponse(
        api_version=container.config.api.api_version,
        service_version=container.config.api.service_version,
        pipeline_versions={
            "full": getattr(getattr(full, "config", None), "pipeline_version", "unknown"),
            "cascaded": getattr(getattr(cascaded, "config", None), "pipeline_version", "unknown"),
        },
        routing_policy_version=getattr(routing, "version", None),
        fusion_policy_version=getattr(fusion, "version", None),
        prompt_version=getattr(vlm_config, "prompt_version", None),
        model_identifiers={
            "detector": _identifier(getattr(detector, "model_name", None)),
            "ocr": type(ocr).__name__ if ocr is not None else None,
            "baseline": _identifier(getattr(baseline, "experiment_name", None)),
            "vlm": _identifier(getattr(vlm_config, "model_name_or_path", None)),
        },
        max_concurrent_inference=container.config.api.max_concurrent_inference,
        runtime_version=container.config.api.runtime_version,
        model_bundle_version=container.config.api.model_bundle_version,
        capabilities=container.capabilities(),
    )
