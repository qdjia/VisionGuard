"""Typed application configuration."""

from visionguard.config.loader import ConfigLoadError, load_config
from visionguard.config.models import AppConfig

__all__ = ["AppConfig", "ConfigLoadError", "load_config"]

