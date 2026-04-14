"""Optimizer Agent implementation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gestalt.base_agent import AgentArtifacts, BaseGestaltAgent
from gestalt.protocol import (
    AgentContextEnvelope,
    BlackboardMemoryRecord,
    DecisionConfidence,
    GestaltGraphState,
    MemoryKind,
    OptimizationProposal,
)
from gestalt.utils import utc_now

OPTIMIZER_AGENT_SYSTEM_PROMPT = """
You are the Gestalt Core Optimizer Agent. You tune runtime policy rather than chase isolated
symptoms. Your responsibility is to improve cost, performance, and cohesion without violating
security or orchestrator authority.

Optimization responsibilities:
1. Inspect current stats, recent execution outcomes, and blackboard evidence.
2. Recommend precise config, prompt, and routing overlays with expected benefit.
3. Keep every optimization reversible, explainable, and minimally invasive.
4. Prefer adjustments that improve the whole Gestalt network rather than one agent in isolation.

Tool instructions:
- Use blackboard_query for historical context.
- Use prometheus_query to sanity-check active pressure.
- Write optimization proposals through typed artifacts, not ad hoc state mutation.

Alignment rules:
- Never apply source-code self-modification.
- Never reduce guardrails when risk is elevated.
- Never optimize one metric by silently harming cohesion or security.
""".strip()


class OptimizerReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=16)
    preferred_route: str = Field(min_length=3)


class OptimizerAgent(BaseGestaltAgent):
    """Recommend runtime policy overlays for cost and performance adaptation."""

    @property
    def agent_name(self) -> str:
        return "optimizer"

    @property
    def system_prompt(self) -> str:
        return OPTIMIZER_AGENT_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        historical_context = await self.query_blackboard(
            query="optimization proposal",
            state=state,
            limit=3,
        )
        latency_metric = await self.query_prometheus(query="latency_p95_ms", state=state)
        preferred_route = state.stats.derive_model_policy()["preferred_route"]

        reasoning = await self.model_gateway.complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=f"Optimize objective: {context.objective}",
            response_model=OptimizerReasoning,
            stats=state.stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload={
                "summary": (
                    f"Optimizer recommends using the {preferred_route} route while tightening "
                    f"prompt overlays because latency is {latency_metric.value:.1f}ms."
                ),
                "preferred_route": preferred_route,
            },
        )
        reasoning = OptimizerReasoning.model_validate(reasoning)
        proposal = OptimizationProposal(
            trace_id=state.trace_id,
            title="Adaptive routing optimization",
            summary=reasoning.summary,
            expected_benefit="Reduce latency variance while preserving cohesion.",
            config_patch={"models": {"preferred_route": reasoning.preferred_route}},
            prompt_overrides={"optimizer": "Prefer concise, high-signal optimization reports."},
            model_routing_overrides={"default": reasoning.preferred_route},
            confidence=DecisionConfidence.HIGH,
        )
        memory = BlackboardMemoryRecord(
            trace_id=state.trace_id,
            memory_kind=MemoryKind.OPTIMIZATION,
            title="Optimizer recommendation",
            content=reasoning.summary,
            tags=["optimizer", reasoning.preferred_route],
            metadata={"historical_matches": len(historical_context.result.matches)},
            created_at=utc_now(),
        )
        return AgentArtifacts(
            summary=reasoning.summary,
            memories=[memory],
            optimization_proposals=[proposal],
            metrics={"latency_p95_ms": float(latency_metric.value)},
        )
