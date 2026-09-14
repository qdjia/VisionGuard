"""Consistent application logging configuration."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once; preserve handlers installed by a host app."""

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
