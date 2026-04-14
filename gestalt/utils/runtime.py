"""Runtime helpers and service container for the Gestalt application."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from langgraph.graph.state import CompiledStateGraph

    from gestalt.blackboard import GestaltBlackboard
    from gestalt.config import GestaltSettings
    from gestalt.events.bus import BaseEventBus
    from gestalt.tools.registry import ToolRegistry
    from gestalt.utils.model_gateway import ModelGateway


@dataclass(slots=True)
class GestaltRuntime:
    """Shared runtime dependencies initialized during app startup."""

    settings: GestaltSettings
    blackboard: GestaltBlackboard
    event_bus: BaseEventBus
    tool_registry: ToolRegistry
    model_gateway: ModelGateway
    graph: CompiledStateGraph | None = None
    scheduler: AsyncIOScheduler | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def is_sqlite_url(database_url: str) -> bool:
    """Return whether a SQLAlchemy URL targets SQLite."""

    return database_url.startswith("sqlite")


def to_langgraph_postgres_dsn(database_url: str) -> str:
    """Convert a SQLAlchemy asyncpg URL into a psycopg-compatible DSN."""

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database_url.startswith("postgresql://"):
        return database_url
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("postgresql"):
        return database_url
    msg = f"Unsupported Postgres URL for LangGraph checkpointing: {database_url}"
    raise ValueError(msg)


def import_async_postgres_saver() -> type[Any]:
    """Import the async Postgres saver lazily to tolerate missing libpq locally."""

    module = import_module("langgraph.checkpoint.postgres.aio")
    return module.AsyncPostgresSaver
