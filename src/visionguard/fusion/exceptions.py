"""Fusion-specific failures."""

from visionguard.core.exceptions import VisionGuardError


class FusionError(VisionGuardError):
    """Base error for invalid fusion inputs or decisions."""
