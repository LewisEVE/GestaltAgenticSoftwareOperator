"""Identifier helpers for traceable Gestalt entities."""

from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a deterministic prefixed identifier."""

    return f"{prefix}_{uuid4().hex}"
