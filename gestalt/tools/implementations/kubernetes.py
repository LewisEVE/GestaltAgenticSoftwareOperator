"""Kubernetes inspection and safe patch tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gestalt.tools.base import BaseTool, ToolContext, ToolDescriptor
from gestalt.protocol import ToolExecutionMode


class KubernetesReadInput(BaseModel):
    """Input payload for read-only Kubernetes inspection."""

    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)


class KubernetesReadOutput(BaseModel):
    """Output payload for Kubernetes inspection."""

    model_config = ConfigDict(extra="forbid")

    namespace: str
    kind: str
    name: str
    status: Literal["mocked"] = "mocked"
    details: dict[str, str] = Field(default_factory=dict)


class KubernetesPatchInput(BaseModel):
    """Input payload for a tightly scoped Kubernetes patch."""

    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    patch: dict[str, str] = Field(default_factory=dict)


class KubernetesPatchOutput(BaseModel):
    """Output payload for a mock patch operation."""

    model_config = ConfigDict(extra="forbid")

    namespace: str
    kind: str
    name: str
    applied: bool = True
    patch_summary: dict[str, str] = Field(default_factory=dict)


class KubernetesReadTool(BaseTool):
    """Read-only kubernetes inspection stub for production wiring."""

    descriptor = ToolDescriptor(
        name="kubernetes_read",
        description="Inspect Kubernetes resources in an allowed namespace.",
        execution_mode=ToolExecutionMode.READ_ONLY,
    )
    input_model = KubernetesReadInput
    output_model = KubernetesReadOutput

    async def arun(self, payload: KubernetesReadInput, context: ToolContext) -> KubernetesReadOutput:
        """Return mocked Kubernetes state until a cluster client is injected."""

        return KubernetesReadOutput(
            namespace=payload.namespace,
            kind=payload.kind,
            name=payload.name,
            details={
                "inspected_by": context.agent_name,
                "trace_id": context.trace_id,
            },
        )


class KubernetesPatchTool(BaseTool):
    """Restricted mutating Kubernetes patch stub."""

    descriptor = ToolDescriptor(
        name="kubernetes_patch",
        description="Apply a restricted patch to an allowed Kubernetes resource.",
        execution_mode=ToolExecutionMode.MUTATING,
        requires_approval=True,
    )
    input_model = KubernetesPatchInput
    output_model = KubernetesPatchOutput

    async def arun(self, payload: KubernetesPatchInput, context: ToolContext) -> KubernetesPatchOutput:
        """Return a mocked patch result."""

        return KubernetesPatchOutput(
            namespace=payload.namespace,
            kind=payload.kind,
            name=payload.name,
            patch_summary={**payload.patch, "applied_by": context.agent_name},
        )
