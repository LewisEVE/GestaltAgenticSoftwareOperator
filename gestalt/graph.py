"""LangGraph super-graph definition for Gestalt Core."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from gestalt.agents.analyzer import AnalyzerAgent
from gestalt.agents.knowledge import KnowledgeAgent
from gestalt.agents.monitor import MonitorAgent
from gestalt.agents.optimizer import OptimizerAgent
from gestalt.agents.planner_executor import PlannerExecutorAgent
from gestalt.agents.security_audit import SecurityAuditAgent
from gestalt.orchestrator import GestaltOrchestrator
from gestalt.protocol import CycleRequest, GestaltGraphState, SchedulerSource
from gestalt.utils import GestaltRuntime


def _state_update_callable(
    runner: Callable[[GestaltGraphState], Awaitable[GestaltGraphState]],
) -> Callable[[GestaltGraphState], Awaitable[dict]]:
    async def _invoke(state: GestaltGraphState) -> dict:
        updated = await runner(state)
        return updated.model_dump(mode="python")

    return _invoke


def build_graph(runtime: GestaltRuntime):
    """Build and compile the single Gestalt StateGraph."""

    orchestrator = GestaltOrchestrator(
        settings=runtime.settings,
        blackboard=runtime.blackboard,
        event_bus=runtime.event_bus,
        tool_registry=runtime.tool_registry,
        model_gateway=runtime.model_gateway,
    )
    agents = {
        "monitor": MonitorAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
        "analyzer": AnalyzerAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
        "planner_executor": PlannerExecutorAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
        "optimizer": OptimizerAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
        "knowledge": KnowledgeAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
        "security_audit": SecurityAuditAgent(
            settings=runtime.settings,
            blackboard=runtime.blackboard,
            event_bus=runtime.event_bus,
            tool_registry=runtime.tool_registry,
            model_gateway=runtime.model_gateway,
        ),
    }
    runtime.metadata["orchestrator"] = orchestrator
    runtime.metadata["agents"] = agents

    builder = StateGraph(GestaltGraphState)
    builder.add_node("orchestrator", _state_update_callable(orchestrator.run))
    for name, agent in agents.items():
        builder.add_node(name, _state_update_callable(agent.run))

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "monitor": "monitor",
            "analyzer": "analyzer",
            "planner_executor": "planner_executor",
            "optimizer": "optimizer",
            "knowledge": "knowledge",
            "security_audit": "security_audit",
            "__end__": END,
        },
    )
    for name in agents:
        builder.add_edge(name, "orchestrator")
    graph = builder.compile(checkpointer=InMemorySaver())
    runtime.graph = graph
    return graph


def route_from_orchestrator(state: GestaltGraphState) -> str:
    """Route from the orchestrator to the next selected node."""

    return str(state.metadata.get("next_node", "__end__"))


def build_graph_state(request: CycleRequest) -> GestaltGraphState:
    """Create a fresh graph state for an inbound cycle request."""

    return GestaltGraphState(
        source=request.source,
        objective=request.objective,
        metadata=dict(request.metadata),
    )


async def run_cycle(runtime: GestaltRuntime, request: CycleRequest) -> GestaltGraphState:
    """Run a full graph cycle and return the finalized state."""

    if runtime.graph is None:
        build_graph(runtime)
    if runtime.graph is None:
        msg = "Gestalt graph failed to initialize."
        raise RuntimeError(msg)
    state = build_graph_state(request)
    result = await runtime.graph.ainvoke(
        state.model_dump(mode="python"),
        config={"configurable": {"thread_id": str(state.cycle_id)}},
    )
    return GestaltGraphState.model_validate(result)


def scheduler_request(objective: str, *, scheduled_agent: str) -> CycleRequest:
    """Create a scheduler-originated cycle request."""

    return CycleRequest(
        objective=objective,
        source=SchedulerSource.SCHEDULER,
        metadata={"scheduled_agent": scheduled_agent},
    )
