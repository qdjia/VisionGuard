"""Bounded file logging for the background packaged runtime."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_runtime_logging(
    directory: Path,
    *,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "visionguard-runtime.log"
    handler = RotatingFileHandler(
        target,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    return target
