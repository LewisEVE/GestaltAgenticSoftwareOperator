"""Integration tests for the event bus approval workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gestalt.config import EventConfig
from gestalt.events import EventApprovalError, build_event_bus
from gestalt.protocol import EventApproval, GestaltEvent, GestaltEventType


@pytest.mark.asyncio
async def test_memory_event_bus_enforces_approval() -> None:
    """Peer signals must carry a valid orchestrator approval."""

    bus = build_event_bus(
        EventConfig(
            backend="memory",
            redis_url="redis://localhost:6379/0",
        ),
    )
    await bus.initialize()
    try:
        with pytest.raises(EventApprovalError):
            await bus.publish(
                GestaltEvent(
                    source_agent="monitor",
                    target_agent="optimizer",
                    event_type=GestaltEventType.PEER_SIGNAL,
                    payload={"message": "unauthorized"},
                ),
            )

        approval = EventApproval(
            source_agent="monitor",
            target_agent="optimizer",
            permitted_event=GestaltEventType.PEER_SIGNAL,
            rationale="Monitor needs to notify optimizer about pressure changes.",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        await bus.approve(approval)
        event = await bus.publish(
            GestaltEvent(
                approval_id=approval.approval_id,
                source_agent="monitor",
                target_agent="optimizer",
                event_type=GestaltEventType.PEER_SIGNAL,
                payload={"message": "authorized"},
            ),
        )

        events = await bus.list_events()
        assert events[-1].event_id == event.event_id
    finally:
        await bus.close()
