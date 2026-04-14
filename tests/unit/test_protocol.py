"""Protocol model validation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gestalt.protocol import (
    AgentContextEnvelope,
    BlackboardQuery,
    EventApproval,
    GestaltCommand,
    GestaltCommandType,
    GestaltGraphState,
    SchedulerSource,
)
from gestalt.stats import GestaltStats


def test_event_approval_requires_future_expiry() -> None:
    """Approval tokens must expire in the future."""

    with pytest.raises(ValidationError):
        EventApproval(
            source_agent="monitor",
            target_agent="optimizer",
            permitted_event="peer_signal",
            rationale="Need to coordinate changes.",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )


def test_command_defaults_are_initialized() -> None:
    """Commands should initialize identifiers and pending status."""

    command = GestaltCommand(
        command_type=GestaltCommandType.ANALYZE,
        issued_by="orchestrator",
        target_agent="analyzer",
        rationale="Investigate the detected anomaly.",
    )

    assert command.status.value == "pending"
    assert command.trace_id is not None
    assert command.command_id is not None


def test_agent_context_requires_objective() -> None:
    """Agent context should reject empty objectives."""

    with pytest.raises(ValidationError):
        AgentContextEnvelope(
            objective="",
            source=SchedulerSource.API,
            latest_stats=GestaltStats(),
        )


def test_blackboard_query_limit_is_bounded() -> None:
    """Blackboard query limits should be clamped through validation."""

    with pytest.raises(ValidationError):
        BlackboardQuery(query="show everything", limit=0)


def test_graph_state_defaults_are_present() -> None:
    """The graph state should initialize core collections."""

    state = GestaltGraphState(objective="Maintain system stability")

    assert state.source is SchedulerSource.INTERNAL
    assert state.commands == []
    assert state.execution_reports == []
