"""End-to-end graph cycle integration tests."""

from __future__ import annotations

from pathlib import Path

from gestalt.blackboard import GestaltBlackboard
from gestalt.events import MemoryEventBus
from gestalt.graph import build_graph, run_cycle
from gestalt.protocol import CycleRequest
from gestalt.tools import ToolRegistry
from gestalt.tools.implementations import (
    BlackboardQueryTool,
    BlackboardWriteTool,
    HttpRequestTool,
    KubernetesPatchTool,
    KubernetesReadTool,
    PrometheusQueryTool,
    RedisStreamInspectTool,
    SandboxCommandTool,
)
from gestalt.utils import GestaltRuntime, ModelGateway
from tests.conftest import build_test_settings


async def test_end_to_end_cycle_produces_summary(tmp_path: Path) -> None:
    """A full graph cycle should converge and produce a typed summary."""

    settings = build_test_settings(tmp_path / "end-to-end.db")
    blackboard = GestaltBlackboard(settings.blackboard)
    await blackboard.initialize()
    event_bus = MemoryEventBus(settings.events)
    await event_bus.initialize()
    try:
        runtime = GestaltRuntime(
            settings=settings,
            blackboard=blackboard,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            model_gateway=ModelGateway(settings.models),
        )
        runtime.tool_registry.bulk_register(
            [
                BlackboardQueryTool(runtime.blackboard),
                BlackboardWriteTool(runtime.blackboard),
                PrometheusQueryTool(),
                HttpRequestTool(runtime.settings.security),
                SandboxCommandTool(),
                RedisStreamInspectTool(),
                KubernetesReadTool(),
                KubernetesPatchTool(),
            ]
        )
        build_graph(runtime)

        result = await run_cycle(
            runtime,
            CycleRequest(
                objective="Analyze latency regression and preserve reusable knowledge",
                metadata={},
            ),
        )

        assert result.latest_summary is not None
        assert result.latest_summary.cohesion_score >= 0
        assert result.execution_reports
        assert any(report.agent_name == "orchestrator" for report in result.execution_reports)
    finally:
        await event_bus.close()
        await blackboard.close()
