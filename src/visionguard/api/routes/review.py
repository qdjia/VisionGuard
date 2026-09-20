"""Versioned image review endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from visionguard.api.dependencies import ServiceContainer, get_container
from visionguard.api.schemas import APIErrorResponse, APIReviewResponse
from visionguard.api.services import ReviewService, decode_upload

router = APIRouter(prefix="/v1", tags=["inference"])


@router.post(
    "/review",
    response_model=APIReviewResponse,
    responses={
        400: {"model": APIErrorResponse},
        413: {"model": APIErrorResponse},
        415: {"model": APIErrorResponse},
        422: {"model": APIErrorResponse},
        500: {"model": APIErrorResponse},
        503: {"model": APIErrorResponse},
        504: {"model": APIErrorResponse},
    },
)
async def review_image(
    request: Request,
    file: Annotated[UploadFile, File(description="JPEG, PNG, or WebP image")],
    container: Annotated[ServiceContainer, Depends(get_container)],
    pipeline_mode: Annotated[str | None, Query()] = None,
    save_artifacts: Annotated[bool | None, Query()] = None,
    include_details: Annotated[bool, Query()] = False,
) -> APIReviewResponse:
    try:
        decoded, _ = await decode_upload(file, container)
    finally:
        await file.close()
    return await ReviewService(container).review(
        decoded,
        request_id=request.state.request_id,
        request_started=request.state.request_started,
        pipeline_mode=pipeline_mode,
        save_artifacts=save_artifacts,
        include_details=include_details,
    )
