"""Shared base class implementing the Gestalt agent lifecycle contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field

from gestalt.blackboard import GestaltBlackboard
from gestalt.config import GestaltSettings
from gestalt.events import BaseEventBus
from gestalt.protocol import (
    AgentContextEnvelope,
    AgentDecision,
    AgentExecutionReport,
    BlackboardMemoryRecord,
    BlackboardQuery,
    CommandStatus,
    GestaltAuditReport,
    GestaltCommand,
    GestaltGraphState,
    GestaltMessage,
    GestaltMessageRole,
    GestaltStatsReport,
    GestaltSummary,
    OptimizationProposal,
)
from gestalt.tools.base import ToolExecutionRequest
from gestalt.tools.implementations.blackboard import BlackboardQueryOutput
from gestalt.tools.implementations.http import HttpRequestOutput
from gestalt.tools.implementations.kubernetes import KubernetesPatchOutput, KubernetesReadOutput
from gestalt.tools.implementations.prometheus import PrometheusQueryOutput
from gestalt.tools.implementations.redis_admin import RedisInspectOutput
from gestalt.tools.implementations.sandbox import SandboxCommandOutput
from gestalt.tools.registry import ToolRegistry
from gestalt.utils import ModelGateway, get_logger, utc_now

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class AgentArtifacts(BaseModel):
    """Normalized outputs emitted by an agent invocation."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=8)
    commands: list[GestaltCommand] = Field(default_factory=list)
    memories: list[BlackboardMemoryRecord] = Field(default_factory=list)
    messages: list[GestaltMessage] = Field(default_factory=list)
    stats_report: GestaltStatsReport | None = None
    audit_report: GestaltAuditReport | None = None
    latest_summary: GestaltSummary | None = None
    optimization_proposals: list[OptimizationProposal] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    metadata_updates: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)


class BaseGestaltAgent(ABC):
    """Uniform lifecycle used by every Gestalt specialist agent."""

    def __init__(
        self,
        *,
        settings: GestaltSettings,
        blackboard: GestaltBlackboard,
        event_bus: BaseEventBus,
        tool_registry: ToolRegistry,
        model_gateway: ModelGateway,
    ) -> None:
        self.settings = settings
        self.blackboard = blackboard
        self.event_bus = event_bus
        self.tool_registry = tool_registry
        self.model_gateway = model_gateway
        self.logger = get_logger(__name__, agent=self.agent_name)

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the canonical runtime name for the agent."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the finalized system prompt for the agent."""

    def allowed_tools(self) -> list[str]:
        """Resolve the per-agent tool allowlist from settings."""

        return list(self.settings.agents[self.agent_name].tool_allowlist)

    async def prepare_context(self, state: GestaltGraphState) -> AgentContextEnvelope:
        """Hydrate blackboard context and normalize the incoming graph state."""

        context_records: list[BlackboardMemoryRecord] = []
        if state.objective:
            query = BlackboardQuery(
                query=state.objective,
                limit=self.settings.blackboard.semantic_top_k,
            )
            result = await self.blackboard.query_memory(query)
            context_records = result.matches
        return AgentContextEnvelope(
            trace_id=state.trace_id,
            cycle_id=state.cycle_id,
            objective=state.objective,
            source=state.source,
            latest_stats=state.stats,
            blackboard_context=context_records,
            inbound_commands=[
                command
                for command in state.commands
                if command.target_agent == self.agent_name and command.status != CommandStatus.COMPLETED
            ],
            approvals=state.approvals,
            metadata=state.metadata,
        )

    async def run_alignment_checks(self, context: AgentContextEnvelope, state: GestaltGraphState) -> None:
        """Perform shared Gestalt alignment checks before work starts."""

        if not context.objective.strip():
            raise ValueError("Agent objective must not be empty.")
        if self.agent_name not in self.settings.agents:
            raise ValueError(f"Agent '{self.agent_name}' is not configured.")
        if str(context.trace_id) != str(state.trace_id):
            raise ValueError("Trace id mismatch between state and normalized context.")

    def build_input_messages(
        self,
        context: AgentContextEnvelope,
        state: GestaltGraphState,
    ) -> list[GestaltMessage]:
        """Construct the standard system and task messages for the invocation."""

        context_titles = ", ".join(record.title for record in context.blackboard_context[:5]) or "none"
        return [
            GestaltMessage(
                trace_id=context.trace_id,
                role=GestaltMessageRole.SYSTEM,
                sender="system",
                recipient=self.agent_name,
                content=self.system_prompt,
                metadata={"allowed_tools": self.allowed_tools()},
            ),
            GestaltMessage(
                trace_id=context.trace_id,
                role=GestaltMessageRole.ORCHESTRATOR,
                sender="orchestrator",
                recipient=self.agent_name,
                content=(
                    f"Objective: {context.objective}\n"
                    f"Blackboard context titles: {context_titles}\n"
                    f"Current stats: {state.stats.summary()}"
                ),
            ),
        ]

    async def invoke_model(
        self,
        context: AgentContextEnvelope,
        messages: list[GestaltMessage],
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        """Invoke the subclass-specific planning logic."""

        return await self.produce_artifacts(context=context, messages=messages, state=state)

    @abstractmethod
    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages: list[GestaltMessage],
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        """Return the normalized artifacts produced by the agent."""

    async def persist_outputs(self, artifacts: AgentArtifacts) -> None:
        """Persist emitted artifacts through the blackboard."""

        for memory in artifacts.memories:
            await self.blackboard.write_memory(memory)
        for command in artifacts.commands:
            await self.blackboard.write_command(command)
        if artifacts.stats_report is not None:
            await self.blackboard.write_stats_report(artifacts.stats_report)
        if artifacts.audit_report is not None:
            await self.blackboard.write_audit_report(artifacts.audit_report)
        for proposal in artifacts.optimization_proposals:
            await self.blackboard.write_optimization_proposal(proposal)

    async def execute_tool(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        state: GestaltGraphState,
    ) -> BaseModel:
        """Execute a registered tool under the agent's allowlist."""

        return await self.tool_registry.execute_allowed(
            tool_name=tool_name,
            request=ToolExecutionRequest(
                trace_id=str(state.trace_id),
                agent_name=self.agent_name,
                payload=payload,
                metadata={"cycle_id": str(state.cycle_id)},
            ),
            allowlist=self.allowed_tools(),
        )

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        state: GestaltGraphState,
        mock_payload: dict[str, Any],
    ) -> ModelT:
        """Execute a typed structured completion through the shared model gateway."""

        result = await self.model_gateway.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            stats=state.stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload=mock_payload,
        )
        return cast(ModelT, result)

    async def query_blackboard(
        self,
        *,
        query: str,
        state: GestaltGraphState,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> BlackboardQueryOutput:
        """Execute the typed blackboard query tool."""

        result = await self.execute_tool(
            tool_name="blackboard_query",
            payload={"query": query, "limit": limit, "filters": filters or {}},
            state=state,
        )
        return cast(BlackboardQueryOutput, result)

    async def query_prometheus(self, *, query: str, state: GestaltGraphState) -> PrometheusQueryOutput:
        """Execute the typed Prometheus query tool."""

        result = await self.execute_tool(
            tool_name="prometheus_query",
            payload={"query": query},
            state=state,
        )
        return cast(PrometheusQueryOutput, result)

    async def run_sandbox_command(
        self,
        *,
        command: str,
        state: GestaltGraphState,
        working_directory: str = ".",
        timeout_seconds: int = 15,
    ) -> SandboxCommandOutput:
        """Execute the typed sandbox command tool."""

        result = await self.execute_tool(
            tool_name="sandbox_command",
            payload={
                "command": command,
                "working_directory": working_directory,
                "timeout_seconds": timeout_seconds,
            },
            state=state,
        )
        return cast(SandboxCommandOutput, result)

    async def inspect_redis_stream(
        self,
        *,
        stream_name: str,
        state: GestaltGraphState,
        count: int = 10,
    ) -> RedisInspectOutput:
        """Execute the typed Redis stream inspection tool."""

        result = await self.execute_tool(
            tool_name="redis_stream_inspect",
            payload={"stream_name": stream_name, "count": count},
            state=state,
        )
        return cast(RedisInspectOutput, result)

    async def http_request(
        self,
        *,
        method: str,
        url: str,
        state: GestaltGraphState,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_seconds: int = 15,
    ) -> HttpRequestOutput:
        """Execute the typed outbound HTTP tool."""

        result = await self.execute_tool(
            tool_name="http_request",
            payload={
                "method": method,
                "url": url,
                "headers": headers or {},
                "params": params or {},
                "json_body": json_body,
                "timeout_seconds": timeout_seconds,
            },
            state=state,
        )
        return cast(HttpRequestOutput, result)

    async def read_kubernetes_resource(
        self,
        *,
        namespace: str,
        kind: str,
        name: str,
        state: GestaltGraphState,
    ) -> KubernetesReadOutput:
        """Execute the typed Kubernetes read tool."""

        result = await self.execute_tool(
            tool_name="kubernetes_read",
            payload={"namespace": namespace, "kind": kind, "name": name},
            state=state,
        )
        return cast(KubernetesReadOutput, result)

    async def patch_kubernetes_resource(
        self,
        *,
        namespace: str,
        kind: str,
        name: str,
        patch: dict[str, str],
        state: GestaltGraphState,
    ) -> KubernetesPatchOutput:
        """Execute the typed Kubernetes patch tool."""

        result = await self.execute_tool(
            tool_name="kubernetes_patch",
            payload={"namespace": namespace, "kind": kind, "name": name, "patch": patch},
            state=state,
        )
        return cast(KubernetesPatchOutput, result)

    def build_execution_report(
        self,
        *,
        state: GestaltGraphState,
        artifacts: AgentArtifacts,
        started_at,
        status: CommandStatus = CommandStatus.COMPLETED,
    ) -> AgentExecutionReport:
        """Create a standardized execution report for the invocation."""

        return AgentExecutionReport(
            trace_id=state.trace_id,
            agent_name=self.agent_name,
            status=status,
            summary=artifacts.summary,
            emitted_commands=artifacts.commands,
            emitted_memories=artifacts.memories,
            metrics=artifacts.metrics,
            started_at=started_at,
            finished_at=utc_now(),
        )

    async def run(self, state: GestaltGraphState) -> GestaltGraphState:
        """Run the complete shared agent lifecycle and return the updated state."""

        started_at = utc_now()
        try:
            context = await self.prepare_context(state)
            await self.run_alignment_checks(context, state)
            messages = self.build_input_messages(context, state)
            artifacts = await self.invoke_model(context, messages, state)
            await self.persist_outputs(artifacts)
            report = self.build_execution_report(state=state, artifacts=artifacts, started_at=started_at)
            return self._apply_state_update(
                state=state,
                messages=messages + artifacts.messages,
                artifacts=artifacts,
                report=report,
            )
        except Exception as exc:
            self.logger.exception("agent invocation failed", extra={"agent_name": self.agent_name})
            failure_artifacts = AgentArtifacts(summary=f"{self.agent_name} failed: {exc}")
            report = self.build_execution_report(
                state=state,
                artifacts=failure_artifacts,
                started_at=started_at,
                status=CommandStatus.FAILED,
            )
            failed_state = self._apply_state_update(
                state=state,
                messages=[],
                artifacts=failure_artifacts,
                report=report,
            )
            failed_state.metadata["last_error"] = str(exc)
            return failed_state

    def _apply_state_update(
        self,
        *,
        state: GestaltGraphState,
        messages: list[GestaltMessage],
        artifacts: AgentArtifacts,
        report: AgentExecutionReport,
    ) -> GestaltGraphState:
        """Merge agent artifacts into a fresh graph state instance."""

        updated = state.model_copy(deep=True)
        updated.messages.extend(messages)
        updated.commands.extend(artifacts.commands)
        updated.memories.extend(artifacts.memories)
        updated.decisions.extend(artifacts.decisions)
        updated.execution_reports.append(report)
        updated.optimization_proposals.extend(artifacts.optimization_proposals)
        if artifacts.audit_report is not None:
            updated.audit_reports.append(artifacts.audit_report)
        if artifacts.latest_summary is not None:
            updated.latest_summary = artifacts.latest_summary
        if artifacts.stats_report is not None:
            updated.stats.load_level = artifacts.stats_report.load_level
            updated.stats.performance_tier = artifacts.stats_report.performance_tier
            updated.stats.cost_efficiency_score = artifacts.stats_report.cost_efficiency_score
            updated.stats.security_risk_score = artifacts.stats_report.security_risk_score
            updated.stats.gestalt_cohesion_score = artifacts.stats_report.gestalt_cohesion_score
            for snapshot in artifacts.stats_report.agent_health:
                updated.stats.set_agent_health(snapshot.agent_name, snapshot.status)
        updated.metadata.update(artifacts.metadata_updates)
        return updated
