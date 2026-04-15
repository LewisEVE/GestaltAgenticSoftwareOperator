"""Tests for orchestrator routing and cohesion decisions."""

from __future__ import annotations

from pydantic import SecretStr

from gestalt.blackboard import GestaltBlackboard
from gestalt.config import (
    AgentPolicyConfig,
    AppConfig,
    AuditConfig,
    BlackboardConfig,
    CohesionPenalties,
    ErrorRateThresholds,
    EventConfig,
    GestaltSettings,
    LatencyThresholds,
    ModelRouteConfig,
    ModelsConfig,
    QueueDepthThresholds,
    SchedulerConfig,
    SecurityConfig,
    StatsConfig,
    TelemetryConfig,
)
from gestalt.events import MemoryEventBus
from gestalt.graph import build_graph_state
from gestalt.orchestrator import GestaltOrchestrator
from gestalt.protocol import CycleRequest
from gestalt.tools import ToolRegistry
from gestalt.utils import ModelGateway


def build_test_settings() -> GestaltSettings:
    """Create a compact test settings object."""

    agents = {
        name: AgentPolicyConfig(
            enabled=True,
            model_preference="medium",
            max_retries=2,
            tool_allowlist=[],
        )
        for name in (
            "orchestrator",
            "monitor",
            "analyzer",
            "planner_executor",
            "optimizer",
            "knowledge",
            "security_audit",
        )
    }
    return GestaltSettings.model_validate(
        {
            "app": AppConfig(admin_token=SecretStr("change-me")),
            "models": ModelsConfig(
                enable_mock_llm=True,
                default_alias="mock://default",
                routes=ModelRouteConfig(
                    low="mock://low",
                    medium="mock://medium",
                    high="mock://high",
                    critical="mock://critical",
                ),
                embedding_alias="mock://embedding",
            ),
            "blackboard": BlackboardConfig(
                database_url="sqlite+aiosqlite:///./orchestrator-test.db",
                neo4j_uri="bolt://localhost:7687",
                neo4j_username="neo4j",
                neo4j_password=SecretStr("secret"),
                use_sqlite_fallback_for_tests=True,
            ),
            "events": EventConfig(backend="memory", redis_url="redis://localhost:6379/0"),
            "scheduler": SchedulerConfig(),
            "stats": StatsConfig(
                latency_thresholds_ms=LatencyThresholds(),
                error_rate_thresholds=ErrorRateThresholds(),
                queue_depth_thresholds=QueueDepthThresholds(),
                cohesion_penalties=CohesionPenalties(),
            ),
            "audit": AuditConfig(),
            "telemetry": TelemetryConfig(),
            "security": SecurityConfig(),
            "agents": agents,
        }
    )


async def test_orchestrator_routes_monitor_first() -> None:
    """The orchestrator should start with monitor when no work has run yet."""

    settings = build_test_settings()
    blackboard = GestaltBlackboard(settings.blackboard)
    await blackboard.initialize()
    try:
        orchestrator = GestaltOrchestrator(
            settings=settings,
            blackboard=blackboard,
            event_bus=MemoryEventBus(settings.events),
            tool_registry=ToolRegistry(),
            model_gateway=ModelGateway(settings.models),
        )
        state = build_graph_state(CycleRequest(objective="Investigate latency regression"))

        next_agents = orchestrator.determine_next_agents(state)

        assert next_agents[0] == "monitor"
        assert "analyzer" in next_agents
    finally:
        await blackboard.close()


async def test_orchestrator_honors_force_audit() -> None:
    """force_audit should route directly to the security audit agent."""

    settings = build_test_settings()
    blackboard = GestaltBlackboard(settings.blackboard)
    await blackboard.initialize()
    try:
        orchestrator = GestaltOrchestrator(
            settings=settings,
            blackboard=blackboard,
            event_bus=MemoryEventBus(settings.events),
            tool_registry=ToolRegistry(),
            model_gateway=ModelGateway(settings.models),
        )
        state = build_graph_state(
            CycleRequest(
                objective="Run emergency audit",
                metadata={"force_audit": True},
            )
        )

        next_agents = orchestrator.determine_next_agents(state)

        assert next_agents == ["security_audit"]
    finally:
        await blackboard.close()
