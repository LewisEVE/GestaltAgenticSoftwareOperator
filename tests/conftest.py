"""Shared test helpers for Gestalt Core."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import SecretStr

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


def build_test_settings(
    database_path: str | Path,
    *,
    event_backend: Literal["memory", "redis"] = "memory",
) -> GestaltSettings:
    """Create a compact settings object suitable for unit and integration tests."""

    agents = {
        name: AgentPolicyConfig(
            enabled=True,
            model_preference="medium",
            max_retries=2,
            tool_allowlist=[
                "blackboard_query",
                "blackboard_write",
                "prometheus_query",
                "sandbox_command",
                "redis_stream_inspect",
                "kubernetes_read",
                "kubernetes_patch",
                "http_request",
            ],
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
                database_url=f"sqlite+aiosqlite:///{Path(database_path)}",
                neo4j_uri="bolt://localhost:7687",
                neo4j_username="neo4j",
                neo4j_password=SecretStr("secret"),
                use_sqlite_fallback_for_tests=True,
            ),
            "events": EventConfig(
                backend=event_backend,
                redis_url="redis://localhost:6379/0",
            ),
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
