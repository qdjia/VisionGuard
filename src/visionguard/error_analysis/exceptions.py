"""Error-analysis-specific exceptions."""


class ErrorAnalysisError(RuntimeError):
    """Base exception for Phase 11 analysis failures."""


class ErrorRecordError(ErrorAnalysisError):
    """Raised when a stored inference record cannot be analysed safely."""


class RegressionError(ErrorAnalysisError):
    """Raised when a hard-case regression run cannot be completed."""
