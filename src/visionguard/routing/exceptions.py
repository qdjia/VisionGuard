"""Routing policy failures."""

from visionguard.core.exceptions import VisionGuardError


class RoutingError(VisionGuardError):
    """Base error for invalid or unavailable routing decisions."""
