"""Blackboard tool implementations for querying and writing memory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gestalt.blackboard import GestaltBlackboard
from gestalt.protocol import BlackboardMemoryRecord, BlackboardQuery, BlackboardQueryResult
from gestalt.tools.base import BaseTool, ToolContext, ToolDescriptor


class BlackboardQueryInput(BaseModel):
    """Input payload for querying the blackboard."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class BlackboardQueryOutput(BaseModel):
    """Output payload for blackboard query tool execution."""

    model_config = ConfigDict(extra="forbid")

    result: BlackboardQueryResult


class BlackboardWriteInput(BaseModel):
    """Input payload for writing memory into the blackboard."""

    model_config = ConfigDict(extra="forbid")

    record: BlackboardMemoryRecord


class BlackboardWriteOutput(BaseModel):
    """Output payload for memory write operations."""

    model_config = ConfigDict(extra="forbid")

    record: BlackboardMemoryRecord


class BlackboardQueryTool(BaseTool):
    """Read-only blackboard query tool."""

    descriptor = ToolDescriptor(
        name="blackboard_query",
        description="Query the shared Gestalt blackboard memory.",
    )
    input_model = BlackboardQueryInput
    output_model = BlackboardQueryOutput

    def __init__(self, blackboard: GestaltBlackboard) -> None:
        self._blackboard = blackboard

    async def arun(self, payload: BlackboardQueryInput, context: ToolContext) -> BlackboardQueryOutput:
        """Execute a blackboard query."""

        result = await self._blackboard.query_memory(
            BlackboardQuery(
                query=payload.query,
                limit=payload.limit,
                filters=payload.filters,
            ),
        )
        return BlackboardQueryOutput(result=result)


class BlackboardWriteTool(BaseTool):
    """Mutating blackboard write tool."""

    descriptor = ToolDescriptor(
        name="blackboard_write",
        description="Write a memory record into the shared Gestalt blackboard.",
        execution_mode="mutating",
    )
    input_model = BlackboardWriteInput
    output_model = BlackboardWriteOutput

    def __init__(self, blackboard: GestaltBlackboard) -> None:
        self._blackboard = blackboard

    async def arun(self, payload: BlackboardWriteInput, context: ToolContext) -> BlackboardWriteOutput:
        """Persist a memory record via the blackboard service."""

        record = await self._blackboard.write_memory(payload.record)
        return BlackboardWriteOutput(record=record)
