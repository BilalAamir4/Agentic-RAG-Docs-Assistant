"""Logging setup for ragdocs."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with a single stream handler.

    Never logs secret values.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
