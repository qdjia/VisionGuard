"""Liveness and dependency-aware readiness probes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from visionguard.api.dependencies import ServiceContainer, get_container
from visionguard.api.schemas import LiveResponse, ReadyResponse

router = APIRouter(tags=["operations"])


@router.get("/health/live", response_model=LiveResponse)
async def liveness() -> LiveResponse:
    return LiveResponse()


@router.get("/health/ready", response_model=ReadyResponse)
async def readiness(
    container: Annotated[ServiceContainer, Depends(get_container)],
) -> ReadyResponse:
    return ReadyResponse(components=container.components())
