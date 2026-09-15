"""VLM provider adapters (implemented in Phase 6)."""

from visionguard.vlm.base import VLMProvider
from visionguard.vlm.config import load_vlm_config
from visionguard.vlm.context import build_context


def create_provider(config) -> VLMProvider:
    if config.provider == "mock":
        from visionguard.vlm.providers.mock import MockVLMProvider

        return MockVLMProvider(config)
    from visionguard.vlm.providers.local import LocalVLMProvider

    return LocalVLMProvider(config)


__all__ = ["VLMProvider", "load_vlm_config", "build_context", "create_provider"]
