"""Structured logging helpers for Gestalt Core."""

from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger.json import JsonFormatter


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once using JSON output."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(cycle_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        ),
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter[logging.Logger]:
    """Return a context-aware logger adapter."""

    return logging.LoggerAdapter(logging.getLogger(name), extra=context)
