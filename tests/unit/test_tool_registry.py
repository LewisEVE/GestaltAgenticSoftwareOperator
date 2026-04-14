"""Tool registry and allowlist enforcement tests."""

from __future__ import annotations

from pydantic import BaseModel

from gestalt.tools.base import BaseGestaltTool, ToolContext, ToolDescriptor, ToolExecutionRequest
from gestalt.tools.registry import ToolPermissionError, ToolRegistry


class DummyInput(BaseModel):
    """Input schema for the dummy tool."""

    value: str


class DummyOutput(BaseModel):
    """Output schema for the dummy tool."""

    echoed: str


class DummyTool(BaseGestaltTool[DummyInput, DummyOutput]):
    """Simple tool used by the tests."""

    descriptor = ToolDescriptor(name="dummy", description="Dummy tool used for tests.")
    input_model = DummyInput
    output_model = DummyOutput

    async def arun(self, payload: DummyInput, context: ToolContext) -> DummyOutput:
        return DummyOutput(echoed=f"{context.agent_name}:{payload.value}")


async def test_registry_executes_allowed_tool() -> None:
    """Allowed tools should execute successfully."""

    registry = ToolRegistry()
    registry.register(DummyTool())

    result = await registry.execute_allowed(
        tool_name="dummy",
        request=ToolExecutionRequest(
            trace_id="trace-1",
            agent_name="monitor",
            payload={"value": "hello"},
        ),
        allowlist=["dummy"],
    )

    assert result.echoed == "monitor:hello"


async def test_registry_rejects_forbidden_tool() -> None:
    """Forbidden tools should be blocked before execution."""

    registry = ToolRegistry()
    registry.register(DummyTool())

    try:
        await registry.execute_allowed(
            tool_name="dummy",
            request=ToolExecutionRequest(
                trace_id="trace-2",
                agent_name="analyzer",
                payload={"value": "blocked"},
            ),
            allowlist=[],
        )
    except ToolPermissionError as exc:
        assert "not allowed" in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError("Expected ToolPermissionError")
