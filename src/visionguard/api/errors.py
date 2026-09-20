"""Stable API errors and HTTP mappings without internal exception leakage."""

from enum import StrEnum
from typing import Any


class APIErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_IMAGE = "INVALID_IMAGE"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    INVALID_PIPELINE_MODE = "INVALID_PIPELINE_MODE"
    PIPELINE_NOT_READY = "PIPELINE_NOT_READY"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    PIPELINE_FAILURE = "PIPELINE_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIServiceError(RuntimeError):
    def __init__(
        self,
        code: APIErrorCode,
        message: str,
        status_code: int,
        *,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.run_id = run_id
        self.details = details


class ImageValidationError(APIServiceError):
    def __init__(self, message: str = "Uploaded file is not a valid image.") -> None:
        super().__init__(APIErrorCode.INVALID_IMAGE, message, 400)


class UnsupportedMediaTypeError(APIServiceError):
    def __init__(self) -> None:
        super().__init__(
            APIErrorCode.UNSUPPORTED_MEDIA_TYPE,
            "Uploaded media type is not supported.",
            415,
        )


class UploadTooLargeError(APIServiceError):
    def __init__(self) -> None:
        super().__init__(
            APIErrorCode.UPLOAD_TOO_LARGE,
            "Uploaded file exceeds the configured size limit.",
            413,
        )


class ServiceNotReadyError(APIServiceError):
    def __init__(self) -> None:
        super().__init__(
            APIErrorCode.PIPELINE_NOT_READY,
            "Inference service is not ready.",
            503,
        )


class InferenceTimeoutError(APIServiceError):
    def __init__(self, phase: str) -> None:
        super().__init__(
            APIErrorCode.INFERENCE_TIMEOUT,
            "Inference request exceeded the service timeout.",
            504,
            details={"phase": phase},
        )
