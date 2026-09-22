"""Self-contained local runtime primitives for the VisionGuard desktop app."""

from visionguard.runtime.config import RuntimeConfig, load_runtime_config
from visionguard.runtime.manifest import ModelBundleManifest, ModelValidationResult

RUNTIME_VERSION = "0.1.0"
RUNTIME_API_VERSION = "v1"

__all__ = [
    "RUNTIME_API_VERSION",
    "RUNTIME_VERSION",
    "ModelBundleManifest",
    "ModelValidationResult",
    "RuntimeConfig",
    "load_runtime_config",
]
