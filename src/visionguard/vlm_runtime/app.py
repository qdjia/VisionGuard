from __future__ import annotations

import json
import os
from io import BytesIO
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from visionguard.moderation.policy import ModerationPolicy
from visionguard.vlm.schemas import VLMContext
from visionguard.vlm_runtime import VLM_API_VERSION, VLM_RUNTIME_VERSION
from visionguard.vlm_runtime.schemas import VLMAnalyzeResponse, VLMHealth, VLMRuntimeMeta
from visionguard.vlm_runtime.security import SessionSecurity


def create_vlm_app(config, service, token: str, shutdown=None) -> FastAPI:
    app = FastAPI(title="VisionGuard VLM Runtime", docs_url=None, redoc_url=None)
    security = SessionSecurity(token)
    protected = [Depends(security.dependency)]

    @app.exception_handler(Exception)
    async def structured_error(_request: Request, exc: Exception):
        code = "VLM_INFERENCE_FAILED"
        text = str(exc)
        for candidate in (
            "VLM_MODEL_LOAD_FAILED",
            "VLM_LOAD_TIMEOUT",
            "VLM_INFERENCE_TIMEOUT",
            "VLM_MODEL_INVALID",
        ):
            if candidate in text:
                code = candidate
                break
        return JSONResponse(
            status_code=504 if code.endswith("TIMEOUT") else 500,
            content={"error": {"code": code, "message": type(exc).__name__}},
        )

    @app.get("/health/live", response_model=VLMHealth)
    async def live():
        return VLMHealth(
            status="ok",
            model_loaded=service.loaded,
            model_init_count=service.model_init_count,
        )

    @app.get("/health/ready", response_model=VLMHealth, dependencies=protected)
    async def ready():
        return VLMHealth(
            status="ready" if service.loaded else service.state,
            model_loaded=service.loaded,
            model_init_count=service.model_init_count,
        )

    @app.get("/v1/meta", response_model=VLMRuntimeMeta, dependencies=protected)
    async def meta():
        return VLMRuntimeMeta(
            api_version=VLM_API_VERSION,
            runtime_version=VLM_RUNTIME_VERSION,
            model_bundle_version=config.model_bundle_version,
            model_identifier=config.model_path.name,
            prompt_version=config.prompt_version,
            model_loaded=service.loaded,
            model_init_count=service.model_init_count,
            pid=os.getpid(),
        )

    @app.post("/v1/analyze", response_model=VLMAnalyzeResponse, dependencies=protected)
    async def analyze(
        image: Annotated[UploadFile, File()],
        context_json: Annotated[str, Form()],
        policy_json: Annotated[str, Form()],
        prompt_version: Annotated[str, Form()],
        request_metadata_json: Annotated[str, Form()] = "{}",
    ):
        if prompt_version != config.prompt_version:
            raise HTTPException(status_code=409, detail={"code": "VLM_VERSION_INCOMPATIBLE"})
        payload = await image.read()
        try:
            frame = Image.open(BytesIO(payload)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE"}) from exc
        context = VLMContext.model_validate_json(context_json)
        policy = ModerationPolicy.model_validate_json(policy_json)
        metadata = json.loads(request_metadata_json)
        started = perf_counter()
        result = service.analyze(frame, context, policy)
        total_ms = (perf_counter() - started) * 1000
        return VLMAnalyzeResponse(
            result=result,
            timing={"total_ms": total_ms, "model_load_ms": service.model_load_ms},
            metadata={"request": metadata, "model_init_count": service.model_init_count},
        )

    if shutdown is not None:

        @app.post("/_runtime/shutdown", include_in_schema=False, dependencies=protected)
        async def stop():
            shutdown()
            return {"status": "stopping"}

    return app
