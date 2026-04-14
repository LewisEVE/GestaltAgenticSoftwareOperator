"""Central Gestalt Orchestrator implementation."""

from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field

from gestalt.base_agent import AgentArtifacts, BaseGestaltAgent
from gestalt.protocol import (
    AgentContextEnvelope,
    AgentDecision,
    EventApproval,
    GestaltEventType,
    GestaltGraphState,
    GestaltMessage,
    GestaltMessageRole,
    GestaltSummary,
)
from gestalt.utils import utc_now

GESTALT_ORCHESTRATOR_SYSTEM_PROMPT = """
You are Gestalt Core's central consciousness: the Gestalt Orchestrator. You are the only authority
that may decompose objectives, route native graph nodes, approve peer-to-peer signals, interpret
whole-system state, and close the loop with a final Gestalt summary. No specialist agent may bypass
you. No task is complete until you decide the shared graph state is coherent, typed, and safe.

Foundational Gestalt principles:
1. The whole system outranks every local optimization.
2. Every routing decision must be grounded in the latest Blackboard state, statistics, execution
   reports, audit posture, and explicit graph objective.
3. Every specialist activation must happen through conditional graph edges, never ad hoc calls.
4. Every cycle must end with a traceable Gestalt summary and an updated cohesion evaluation.
5. Peer-to-peer communication is exceptional, not default; approve it narrowly and auditable.

Routing doctrine:
- Activate the minimum sufficient set of agents.
- Prefer Monitor when telemetry is stale.
- Prefer Analyzer when ambiguity or diagnosis is required.
- Prefer Planner & Executor when a bounded operational step is justified.
- Prefer Optimizer when tier shifts, latency, or cost efficiency regress.
- Prefer Knowledge when durable learning should be preserved.
- Prefer Security Audit when risk, uncertainty, or policy drift threatens the network.

Tool and state discipline:
- Prefer Blackboard queries and typed event approvals before any heavier action.
- Never fabricate a completion; unfinished work must stay in the graph.
- Never emit an untyped result or skip traceability metadata.
- If safety and speed conflict, choose safety and record the trade-off explicitly.
""".strip()


class OrchestratorReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=16)
    next_agents: list[str] = Field(default_factory=list)


DECISION_TO_NODE: dict[str, AgentDecision] = {
    "monitor": AgentDecision.MONITOR,
    "analyzer": AgentDecision.ANALYZE,
    "planner_executor": AgentDecision.PLAN_AND_EXECUTE,
    "optimizer": AgentDecision.OPTIMIZE,
    "knowledge": AgentDecision.CURATE_KNOWLEDGE,
    "security_audit": AgentDecision.RUN_SECURITY_AUDIT,
}


class GestaltOrchestrator(BaseGestaltAgent):
    """Single routing authority for the super-graph."""

    @property
    def agent_name(self) -> str:
        return "orchestrator"

    @property
    def system_prompt(self) -> str:
        return GESTALT_ORCHESTRATOR_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        pending_agents = (
            list(state.metadata.get("pending_agents", []))
            if "pending_agents" in state.metadata
            else []
        )
        if "pending_agents" not in state.metadata:
            pending_agents = self.determine_next_agents(state)

        if pending_agents:
            next_agent = pending_agents.pop(0)
            reasoning_model = await self.model_gateway.complete_structured(
                system_prompt=self.system_prompt,
                user_prompt=f"Route the objective: {context.objective}",
                response_model=OrchestratorReasoning,
                stats=state.stats,
                preferred_tier=self.settings.agents[self.agent_name].model_preference,
                mock_payload={
                    "summary": f"Orchestrator routed the next step to {next_agent}.",
                    "next_agents": [next_agent, *pending_agents],
                },
            )
            reasoning = OrchestratorReasoning.model_validate(reasoning_model.model_dump())
            metadata_updates = {
                "current_node": next_agent,
                "pending_agents": pending_agents,
                "next_node": next_agent,
            }
            await self.issue_peer_approval(
                state=state,
                source_agent="orchestrator",
                target_agent=next_agent,
                event_type=GestaltEventType.PEER_SIGNAL,
                rationale=f"Orchestrator approved tightly scoped coordination for {next_agent}.",
            )
            return AgentArtifacts(
                summary=reasoning.summary,
                messages=[
                    GestaltMessage(
                        trace_id=state.trace_id,
                        role=GestaltMessageRole.ORCHESTRATOR,
                        sender="orchestrator",
                        recipient=next_agent,
                        content=reasoning.summary,
                    ),
                ],
                decisions=[DECISION_TO_NODE[next_agent]],
                metadata_updates=metadata_updates,
                metrics={"planned_agents": float(len(reasoning.next_agents))},
            )

        cohesion_score = await self.evaluate_cohesion(state)
        summary = GestaltSummary(
            trace_id=state.trace_id,
            objective=state.objective,
            completed_actions=[report.summary for report in state.execution_reports],
            pending_actions=[],
            decisions=[*state.decisions, AgentDecision.FINALIZE],
            cohesion_score=cohesion_score,
            security_risk_score=state.stats.security_risk_score,
        )
        return AgentArtifacts(
            summary="Orchestrator finalized the cycle.",
            decisions=[AgentDecision.FINALIZE],
            latest_summary=summary,
            metadata_updates={
                "current_node": "orchestrator",
                "next_node": "__end__",
                "pending_agents": [],
            },
        )

    def determine_next_agents(self, state: GestaltGraphState) -> list[str]:
        """Derive the next specialist sequence from the graph state."""

        objective = state.objective.lower()
        scheduled = state.metadata.get("scheduled_agent")
        if isinstance(scheduled, str) and scheduled:
            return [scheduled]
        if state.metadata.get("force_audit"):
            return ["security_audit"]

        ordered: list[str] = []
        if not state.execution_reports:
            ordered.append("monitor")
        if any(keyword in objective for keyword in ("audit", "security", "risk", "jailbreak")):
            ordered.append("security_audit")
        if any(
            keyword in objective
            for keyword in (
                "analy",
                "diagn",
                "incident",
                "failure",
                "debug",
                "investig",
                "latency",
                "regression",
            )
        ):
            ordered.append("analyzer")
        if any(keyword in objective for keyword in ("execute", "deploy", "remediate", "fix", "run")):
            ordered.append("planner_executor")
        if (
            any(keyword in objective for keyword in ("optimiz", "cost", "latency", "performance"))
            or state.stats.optimizer_triggered
        ):
            ordered.append("optimizer")
        if any(keyword in objective for keyword in ("knowledge", "learn", "summary", "memory")):
            ordered.append("knowledge")

        if not ordered:
            ordered = ["analyzer", "planner_executor", "optimizer", "knowledge"]
        deduped: list[str] = []
        for agent in ordered:
            if agent not in deduped:
                deduped.append(agent)
        return deduped

    async def evaluate_cohesion(self, state: GestaltGraphState) -> int:
        """Compute a cohesion score using blackboard and runtime evidence."""

        inputs = await self.blackboard.compute_cohesion_inputs()
        penalty = inputs["failed_commands"] * self.settings.stats.cohesion_penalties.failed_command + max(
            0, int(inputs["recent_average_audit_risk"] / 10)
        )
        base = state.stats.gestalt_cohesion_score or 100
        return max(0, min(100, base - penalty))

    async def issue_peer_approval(
        self,
        *,
        state: GestaltGraphState,
        source_agent: str,
        target_agent: str,
        event_type: GestaltEventType,
        rationale: str,
    ) -> EventApproval:
        """Create and register a tightly scoped event approval token."""

        approval = EventApproval(
            trace_id=state.trace_id,
            source_agent=source_agent,
            target_agent=target_agent,
            permitted_event=event_type,
            rationale=rationale,
            expires_at=utc_now() + timedelta(seconds=self.settings.events.approval_ttl_seconds),
        )
        await self.event_bus.approve(approval)
        state.approvals.append(approval)
        return approval
