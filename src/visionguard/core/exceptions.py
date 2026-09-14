"""Shared domain exceptions that do not depend on heavyweight modules."""


class VisionGuardError(RuntimeError):
    """Base exception for expected VisionGuard runtime failures."""


class DetectorError(VisionGuardError):
    """Base exception for detector failures."""


class DetectorLoadError(DetectorError):
    """Raised when model initialization fails."""


class ImageLoadError(DetectorError):
    """Raised when an image cannot be loaded or normalized."""


class InferenceError(DetectorError):
    """Raised when model inference or output parsing fails."""

