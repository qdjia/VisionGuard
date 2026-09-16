"""Pipeline-specific failures with traceable run identifiers."""

from visionguard.core.exceptions import VisionGuardError


class PipelineError(VisionGuardError):
    def __init__(self, message: str, *, run_id: str) -> None:
        super().__init__(message)
        self.run_id = run_id


class PipelineFatalError(PipelineError):
    """Raised when the input cannot be normalized at all."""


class PipelineExecutionError(PipelineError):
    """Raised for fail-fast module failures without inventing a final result."""

    def __init__(self, message: str, *, run_id: str, module: str, cause: Exception) -> None:
        super().__init__(message, run_id=run_id)
        self.module = module
        self.cause = cause


class ArtifactSaveError(PipelineError):
    def __init__(self, message: str, *, run_id: str, cause: Exception) -> None:
        super().__init__(message, run_id=run_id)
        self.cause = cause


def safe_error(exc: BaseException) -> tuple[str, str]:
    """Return bounded single-line diagnostics; full tracebacks stay in logs."""

    message = " ".join(str(exc).split())[:500] or "No error details"
    return type(exc).__name__, message
