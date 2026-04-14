"""Base tool abstractions for the Gestalt runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from gestalt.protocol import ToolExecutionMode

InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


class ToolContext(BaseModel):
    """Execution context supplied to each tool invocation."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    agent_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolDescriptor(BaseModel):
    """Metadata describing a registered tool."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2)
    description: str = Field(min_length=8)
    execution_mode: ToolExecutionMode = ToolExecutionMode.READ_ONLY
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    retries: int = Field(default=0, ge=0, le=5)
    requires_approval: bool = False


class ToolExecutionRequest(BaseModel):
    """Normalized request passed to a tool through the registry."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    agent_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def context(self) -> ToolContext:
        """Derive the lightweight tool context from the request."""

        return ToolContext(
            trace_id=self.trace_id,
            agent_name=self.agent_name,
            metadata=self.metadata,
        )


class BaseGestaltTool(ABC, Generic[InputModelT, OutputModelT]):
    """Abstract asynchronous tool contract used throughout Gestalt Core."""

    descriptor: ToolDescriptor
    input_model: type[InputModelT]
    output_model: type[OutputModelT]

    @property
    def name(self) -> str:
        """Return the canonical tool name."""

        return self.descriptor.name

    def validate_input(self, payload: dict[str, Any] | InputModelT) -> InputModelT:
        """Validate input payloads using the configured schema."""

        if isinstance(payload, self.input_model):
            return payload
        return self.input_model.model_validate(payload)

    @abstractmethod
    async def arun(self, payload: InputModelT, context: ToolContext) -> OutputModelT:
        """Execute the tool asynchronously."""

    async def execute(self, request: ToolExecutionRequest) -> OutputModelT:
        """Validate and run the tool for a registry request."""

        payload = self.validate_input(request.payload)
        return await self.arun(payload, request.context())
