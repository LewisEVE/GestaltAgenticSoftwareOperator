"""Redis Streams and in-memory event buses with orchestrator approval enforcement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from gestalt.config import EventConfig
from gestalt.protocol import EventApproval, GestaltEvent, GestaltEventType
from gestalt.utils.logging import get_logger

logger = get_logger(__name__)


class EventApprovalError(PermissionError):
    """Raised when an event is emitted without a valid orchestrator approval."""


class BaseEventBus(ABC):
    """Abstract event bus contract used by the orchestrator and agents."""

    def __init__(self, config: EventConfig) -> None:
        self._config = config

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the event bus backend."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources."""

    @abstractmethod
    async def approve(self, approval: EventApproval) -> EventApproval:
        """Register an orchestrator approval token."""

    @abstractmethod
    async def publish(self, event: GestaltEvent) -> GestaltEvent:
        """Publish a typed event after approval validation."""

    @abstractmethod
    async def list_events(self, limit: int = 25) -> list[GestaltEvent]:
        """Return recent events for observability and tests."""


class MemoryEventBus(BaseEventBus):
    """Simple in-memory event bus used in tests and local development."""

    def __init__(self, config: EventConfig) -> None:
        super().__init__(config)
        self._approvals: dict[UUID, EventApproval] = {}
        self._events: list[GestaltEvent] = []

    async def initialize(self) -> None:
        """No-op for in-memory operation."""

    async def close(self) -> None:
        """Drop in-memory state."""

        self._approvals.clear()
        self._events.clear()

    async def approve(self, approval: EventApproval) -> EventApproval:
        """Store an approval token in memory."""

        self._approvals[approval.approval_id] = approval
        return approval

    async def publish(self, event: GestaltEvent) -> GestaltEvent:
        """Append an approved event to the in-memory stream."""

        self._validate_event(event)
        self._events.append(event)
        return event

    async def list_events(self, limit: int = 25) -> list[GestaltEvent]:
        """Return recent events in insertion order."""

        return self._events[-limit:]

    def _validate_event(self, event: GestaltEvent) -> None:
        if event.event_type == GestaltEventType.PEER_SIGNAL:
            if event.approval_id is None:
                raise EventApprovalError("Peer signals require an orchestrator approval token.")
            approval = self._approvals.get(event.approval_id)
            if approval is None:
                raise EventApprovalError("Approval token is unknown.")
            if approval.expires_at <= datetime.now(UTC):
                raise EventApprovalError("Approval token is expired.")
            if approval.permitted_event != event.event_type:
                raise EventApprovalError("Approval token does not permit this event type.")
            if approval.source_agent != event.source_agent:
                raise EventApprovalError("Approval token source does not match the event source.")
            if approval.target_agent != (event.target_agent or ""):
                raise EventApprovalError("Approval token target does not match the event target.")


class RedisEventBus(BaseEventBus):
    """Redis Streams-backed event bus for production deployments."""

    def __init__(self, config: EventConfig) -> None:
        super().__init__(config)
        self._redis: Redis | None = None
        self._approvals: dict[UUID, EventApproval] = {}

    async def initialize(self) -> None:
        """Connect to Redis."""

        self._redis = Redis.from_url(self._config.redis_url, decode_responses=True)
        ping_result = self._redis.ping()
        if isinstance(ping_result, Awaitable):
            await ping_result

    async def close(self) -> None:
        """Close the Redis client if it exists."""

        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._approvals.clear()

    async def approve(self, approval: EventApproval) -> EventApproval:
        """Register an approval both in memory and Redis."""

        self._approvals[approval.approval_id] = approval
        if self._redis is not None:
            key = f"{self._config.stream_name}:approval:{approval.approval_id}"
            await self._redis.set(
                key,
                approval.model_dump_json(),
                ex=self._config.approval_ttl_seconds,
            )
        return approval

    async def publish(self, event: GestaltEvent) -> GestaltEvent:
        """Publish an event into Redis Streams."""

        self._validate_event(event)
        if self._redis is None:
            msg = "Redis event bus is not initialized."
            raise RuntimeError(msg)
        await self._redis.xadd(
            self._config.stream_name,
            {"payload": event.model_dump_json()},
            maxlen=self._config.max_stream_length,
            approximate=True,
        )
        return event

    async def list_events(self, limit: int = 25) -> list[GestaltEvent]:
        """Read recent events from the Redis stream."""

        if self._redis is None:
            return []
        records = await self._redis.xrevrange(self._config.stream_name, count=limit)
        return [
            GestaltEvent.model_validate_json(entry[1]["payload"])
            for entry in reversed(records)
            if "payload" in entry[1]
        ]

    def _validate_event(self, event: GestaltEvent) -> None:
        if event.event_type != GestaltEventType.PEER_SIGNAL:
            return
        if event.approval_id is None:
            raise EventApprovalError("Peer signals require an approval id.")
        approval = self._approvals.get(event.approval_id)
        if approval is None:
            raise EventApprovalError("Approval token is unknown.")
        if approval.expires_at <= datetime.now(UTC):
            raise EventApprovalError("Approval token is expired.")
        if approval.permitted_event != event.event_type:
            raise EventApprovalError("Approval token does not permit this event type.")


def build_event_bus(config: EventConfig) -> BaseEventBus:
    """Create the configured event bus implementation."""

    if config.backend == "memory":
        return MemoryEventBus(config)
    return RedisEventBus(config)
