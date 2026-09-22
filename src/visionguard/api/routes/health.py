"""Liveness and dependency-aware readiness probes."""

from fastapi import APIRouter, Request

from visionguard.api.dependencies import get_container
from visionguard.api.schemas import LiveResponse, ReadyResponse

router = APIRouter(tags=["operations"])


@router.get("/health/live", response_model=LiveResponse)
async def liveness() -> LiveResponse:
    return LiveResponse()


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness(
    request: Request,
) -> ReadyResponse:
    container = get_container(request)
    return ReadyResponse(components=container.components())
