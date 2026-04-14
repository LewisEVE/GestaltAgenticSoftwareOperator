"""Scheduler integration tests."""

from __future__ import annotations

from pathlib import Path

from gestalt.blackboard import GestaltBlackboard
from gestalt.events import MemoryEventBus
from gestalt.main import build_scheduler
from gestalt.tools import ToolRegistry
from gestalt.utils import GestaltRuntime, ModelGateway
from tests.conftest import build_test_settings


async def test_scheduler_registers_expected_jobs(tmp_path: Path) -> None:
    """The runtime scheduler should register all periodic maintenance jobs."""

    settings = build_test_settings(tmp_path / "scheduler.db")
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

        scheduler = build_scheduler(runtime)

        assert scheduler.get_job("monitor") is not None
        assert scheduler.get_job("security_audit") is not None
        assert scheduler.get_job("knowledge_maintenance") is not None
        assert scheduler.get_job("optimizer_maintenance") is not None
    finally:
        await event_bus.close()
        await blackboard.close()
