"""Redis stream inspection tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gestalt.protocol import ToolExecutionMode
from gestalt.tools.base import BaseTool, ToolContext, ToolDescriptor


class RedisInspectInput(BaseModel):
    """Payload for Redis stream inspection."""

    model_config = ConfigDict(extra="forbid")

    stream_name: str = Field(min_length=1)
    count: int = Field(default=10, ge=1, le=100)


class RedisInspectOutput(BaseModel):
    """Redis stream inspection result."""

    model_config = ConfigDict(extra="forbid")

    stream_name: str
    count: int
    entries: list[dict[str, str]] = Field(default_factory=list)


class RedisStreamInspectTool(BaseTool):
    """Stub-safe Redis stream inspection tool."""

    descriptor = ToolDescriptor(
        name="redis_stream_inspect",
        description="Inspect Redis Streams entries for audit and debugging.",
        execution_mode=ToolExecutionMode.READ_ONLY,
        timeout_seconds=10,
    )
    input_model = RedisInspectInput
    output_model = RedisInspectOutput

    async def arun(self, payload: RedisInspectInput, context: ToolContext) -> RedisInspectOutput:
        """Return a deterministic inspection payload when Redis is unavailable."""

        return RedisInspectOutput(stream_name=payload.stream_name, count=payload.count, entries=[])
