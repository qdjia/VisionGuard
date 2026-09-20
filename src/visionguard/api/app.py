"""FastAPI application factory and stable exception boundary."""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from visionguard.api.config import APIConfig, load_api_config
from visionguard.api.errors import APIErrorCode, APIServiceError
from visionguard.api.lifespan import build_service_container, create_lifespan
from visionguard.api.middleware import RequestContextMiddleware
from visionguard.api.routes import health_router, meta_router, review_router
from visionguard.api.schemas import APIErrorBody, APIErrorResponse
from visionguard.pipeline.exceptions import PipelineError

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "api.yaml"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    run_id: str | None = None,
    details: dict | None = None,
) -> JSONResponse:
    body = APIErrorResponse(
        error=APIErrorBody(
            code=code,
            message=message,
            request_id=_request_id(request),
            run_id=run_id,
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app(
    config_path: str | Path | None = None,
    *,
    config: APIConfig | None = None,
    container_factory=build_service_container,
) -> FastAPI:
    resolved = config or load_api_config(config_path or DEFAULT_CONFIG)
    docs_url = "/docs" if resolved.api.docs_enabled else None
    app = FastAPI(
        title=resolved.api.service_name,
        version=resolved.api.service_version,
        docs_url=docs_url,
        redoc_url="/redoc" if resolved.api.docs_enabled else None,
        openapi_url="/openapi.json" if resolved.api.docs_enabled else None,
        lifespan=create_lifespan(resolved, container_factory),
    )
    app.state.api_config = resolved
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(meta_router)
    app.include_router(review_router)

    @app.exception_handler(APIServiceError)
    async def handle_service_error(request: Request, exc: APIServiceError):
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code.value,
            message=exc.message,
            run_id=exc.run_id,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        fields = [{"location": list(item["loc"]), "type": item["type"]} for item in exc.errors()]
        return _error_response(
            request,
            status_code=422,
            code=APIErrorCode.INVALID_REQUEST.value,
            message="Request parameters could not be validated.",
            details={"fields": fields},
        )

    @app.exception_handler(PipelineError)
    async def handle_pipeline_error(request: Request, exc: PipelineError):
        LOGGER.exception("request_id=%s unhandled pipeline failure", _request_id(request))
        return _error_response(
            request,
            status_code=500,
            code=APIErrorCode.PIPELINE_FAILURE.value,
            message="Pipeline could not complete the review.",
            run_id=exc.run_id,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        return _error_response(
            request,
            status_code=exc.status_code,
            code=APIErrorCode.INVALID_REQUEST.value,
            message="HTTP request could not be completed.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        LOGGER.exception("request_id=%s unexpected API failure", _request_id(request))
        message = "Internal inference service error."
        if resolved.api.expose_internal_errors:
            message = f"Internal inference service error ({type(exc).__name__})."
        return _error_response(
            request,
            status_code=500,
            code=APIErrorCode.INTERNAL_ERROR.value,
            message=message,
        )

    return app
