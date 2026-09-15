from visionguard.core.exceptions import VisionGuardError


class VLMError(VisionGuardError):
    pass


class VLMProviderLoadError(VLMError):
    pass


class VLMInferenceError(VLMError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class VLMTimeoutError(VLMInferenceError):
    pass


class VLMParseError(VLMError):
    pass


class VLMValidationError(VLMParseError):
    pass
