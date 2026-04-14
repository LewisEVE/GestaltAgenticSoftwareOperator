"""Prometheus-adjacent metric query tool implementations."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from gestalt.protocol import ToolExecutionMode
from gestalt.tools.base import BaseTool, ToolContext, ToolDescriptor


class PrometheusQueryInput(BaseModel):
    """Input payload for metrics queries."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class PrometheusQueryOutput(BaseModel):
    """Synthetic metrics response used in local and test environments."""

    model_config = ConfigDict(extra="forbid")

    query: str
    value: float
    sampled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PrometheusQueryTool(BaseTool):
    """Very small metrics tool used by monitor, analyzer, and optimizer agents."""

    descriptor = ToolDescriptor(
        name="prometheus_query",
        description="Query operational metrics used by Gestalt agents.",
        execution_mode=ToolExecutionMode.READ_ONLY,
    )
    input_model = PrometheusQueryInput
    output_model = PrometheusQueryOutput

    async def arun(self, payload: PrometheusQueryInput, context: ToolContext) -> PrometheusQueryOutput:
        """Return a deterministic synthetic value for the requested metric."""

        query = payload.query.lower()
        if "queue" in query:
            value = 3.0
        elif "latency" in query:
            value = 420.0
        elif "error" in query:
            value = 0.01
        else:
            value = 1.0
        return PrometheusQueryOutput(query=payload.query, value=value)
