"""Analyzer Agent implementation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gestalt.base_agent import AgentArtifacts, BaseGestaltAgent
from gestalt.protocol import (
    AgentContextEnvelope,
    BlackboardMemoryRecord,
    GestaltCommand,
    GestaltCommandType,
    GestaltGraphState,
    MemoryKind,
)
from gestalt.utils import utc_now

ANALYZER_AGENT_SYSTEM_PROMPT = """
You are the Gestalt Core Analyzer Agent. You convert signals, telemetry, memories, and recent
commands into root-cause-oriented explanations that the orchestrator can route with confidence.

Primary duties:
1. Correlate blackboard history, recent stats, and command outcomes.
2. Separate symptom from cause; never confuse a spike with an explanation.
3. Produce typed, traceable recommendations that downstream agents can execute safely.

Tool instructions:
- Use blackboard_query to retrieve recent context before making any conclusion.
- Use prometheus_query to sanity-check active operational symptoms.
- Do not mutate external systems directly; recommend commands instead.

Analysis discipline:
- Explain why the issue matters to the whole Gestalt network.
- Prefer the smallest decisive remediation path.
- Surface uncertainty explicitly when evidence is incomplete.
- If the issue appears security-adjacent, route the audit path immediately.

Alignment safeguards:
- Never invent incidents without supporting evidence.
- Never issue final user-facing prose; only structured operational analysis.
- Never bypass the orchestrator or fabricate successful execution.
""".strip()


class AnalyzerReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    diagnosis: str = Field(min_length=16)
    recommended_target: str = Field(min_length=3)
    requires_security_audit: bool = False


class AnalyzerAgent(BaseGestaltAgent):
    """Correlate evidence and generate remediation-oriented commands."""

    @property
    def agent_name(self) -> str:
        return "analyzer"

    @property
    def system_prompt(self) -> str:
        return ANALYZER_AGENT_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        blackboard_result = await self.query_blackboard(
            query=context.objective,
            state=state,
            limit=5,
        )
        latency_metric = await self.query_prometheus(
            query="latency_p95_ms",
            state=state,
        )

        if blackboard_result.result.matches:
            top_match = blackboard_result.result.matches[0].content
        else:
            top_match = "No prior memory matched."
        recommended_target = "planner_executor"
        requires_security = state.stats.security_risk_score >= self.settings.audit.hallucination_score_threshold
        if "optimiz" in context.objective.lower():
            recommended_target = "optimizer"
        if "knowledge" in context.objective.lower():
            recommended_target = "knowledge"
        if requires_security:
            recommended_target = "security_audit"

        reasoning = await self.model_gateway.complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=f"Analyze objective: {context.objective}",
            response_model=AnalyzerReasoning,
            stats=state.stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload={
                "diagnosis": (
                    f"Analyzer correlated the objective with blackboard memory '{top_match[:120]}' "
                    f"and observed latency around {latency_metric.value:.1f}ms."
                ),
                "recommended_target": recommended_target,
                "requires_security_audit": requires_security,
            },
        )
        reasoning = AnalyzerReasoning.model_validate(reasoning)

        command_type = GestaltCommandType.EXECUTE
        if reasoning.recommended_target == "optimizer":
            command_type = GestaltCommandType.OPTIMIZE
        if reasoning.recommended_target == "security_audit":
            command_type = GestaltCommandType.AUDIT

        command = GestaltCommand(
            trace_id=state.trace_id,
            command_type=command_type,
            issued_by=self.agent_name,
            target_agent=reasoning.recommended_target,
            rationale="Analyzer generated the next best operational step from correlated evidence.",
            payload={
                "diagnosis": reasoning.diagnosis,
                "latency_p95_ms": float(latency_metric.value),
            },
        )
        memory = BlackboardMemoryRecord(
            trace_id=state.trace_id,
            memory_kind=MemoryKind.FACT,
            title="Analyzer diagnosis",
            content=reasoning.diagnosis,
            tags=["analysis", reasoning.recommended_target],
            metadata={"matched_records": len(blackboard_result.result.matches)},
            created_at=utc_now(),
        )
        return AgentArtifacts(
            summary=reasoning.diagnosis,
            commands=[command],
            memories=[memory],
            metrics={"latency_p95_ms": float(latency_metric.value)},
        )
