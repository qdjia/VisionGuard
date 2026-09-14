"""Shared domain exceptions that do not depend on heavyweight modules."""


class VisionGuardError(RuntimeError):
    """Base exception for expected VisionGuard runtime failures."""


class DetectorError(VisionGuardError):
    """Base exception for detector failures."""


class DetectorLoadError(DetectorError):
    """Raised when model initialization fails."""


class ImageLoadError(VisionGuardError):
    """Raised when an image cannot be loaded or normalized."""


class InferenceError(DetectorError):
    """Raised when model inference or output parsing fails."""


class OCRError(VisionGuardError):
    """Base exception for OCR failures."""


class OCREngineLoadError(OCRError):
    """Raised when an OCR backend cannot be initialized."""


class OCRInferenceError(OCRError):
    """Raised when OCR inference or result parsing fails."""


class InvalidROIError(OCRError):
    """Raised when a region cannot produce a valid image crop."""
