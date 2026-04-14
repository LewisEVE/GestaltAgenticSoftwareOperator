"""Graph routing tests for the Gestalt super-graph."""

from __future__ import annotations

from gestalt.graph import route_from_orchestrator
from gestalt.protocol import CycleRequest, SchedulerSource


def test_route_from_orchestrator_defaults_to_end() -> None:
    """Missing next-node metadata should end the graph."""

    state = CycleRequest(
        objective="Keep the system healthy",
        source=SchedulerSource.INTERNAL,
        metadata={},
    )

    from gestalt.graph import build_graph_state

    graph_state = build_graph_state(state)
    assert route_from_orchestrator(graph_state) == "__end__"


def test_route_from_orchestrator_uses_next_node() -> None:
    """The orchestrator metadata should drive the conditional edge."""

    from gestalt.graph import build_graph_state

    graph_state = build_graph_state(
        CycleRequest(
            objective="Run monitoring",
            source=SchedulerSource.INTERNAL,
            metadata={"next_node": "monitor"},
        )
    )
    assert route_from_orchestrator(graph_state) == "monitor"
