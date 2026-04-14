"""Knowledge Agent implementation."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from gestalt.base_agent import AgentArtifacts, BaseGestaltAgent
from gestalt.protocol import (
    AgentContextEnvelope,
    BlackboardMemoryRecord,
    BlackboardRelation,
    GestaltGraphState,
    MemoryKind,
)
from gestalt.utils import utc_now

KNOWLEDGE_AGENT_SYSTEM_PROMPT = """
You are the Gestalt Core Knowledge Agent. Your role is to turn transient operational experience
into reusable organizational memory that future graph cycles can exploit without losing context.

Core duties:
1. Curate, compress, and connect blackboard memories into coherent knowledge artifacts.
2. Preserve relationships between incidents, commands, optimizations, and outcomes.
3. Remove duplication conceptually by summarizing recurring evidence into durable facts.

Tool instructions:
- Use blackboard_query to gather historical context.
- Persist durable memories through typed artifacts.
- Maintain graph relationships when a useful lineage is apparent.

Alignment rules:
- Never overwrite historical evidence; summarize it.
- Never claim certainty that the data does not support.
- Always optimize for future retrieval quality and cross-agent reuse.
""".strip()


class KnowledgeReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=16)


class KnowledgeAgent(BaseGestaltAgent):
    """Curate durable knowledge from operational history."""

    @property
    def agent_name(self) -> str:
        return "knowledge"

    @property
    def system_prompt(self) -> str:
        return KNOWLEDGE_AGENT_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        result = await self.query_blackboard(query=context.objective, state=state, limit=5)
        titles = [record.title for record in result.result.matches]
        reasoning = await self.model_gateway.complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=f"Curate knowledge for objective: {context.objective}",
            response_model=KnowledgeReasoning,
            stats=state.stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload={
                "summary": (
                    "Knowledge agent summarized the most relevant memories into a reusable "
                    "artifact spanning: "
                    f"{', '.join(titles) if titles else 'current cycle evidence only'}."
                ),
            },
        )
        reasoning = cast(KnowledgeReasoning, reasoning)
        memory = BlackboardMemoryRecord(
            trace_id=state.trace_id,
            memory_kind=MemoryKind.KNOWLEDGE,
            title="Curated Gestalt knowledge artifact",
            content=reasoning.summary,
            tags=["knowledge", "curation"],
            metadata={"source_titles": titles},
            created_at=utc_now(),
        )
        if result.result.matches:
            await self.blackboard.link_entities(
                [
                    BlackboardRelation(
                        source_type="memory",
                        source_id=str(result.result.matches[0].record_id),
                        relation_type="CURATED_INTO",
                        target_type="memory",
                        target_id=str(memory.record_id),
                    ),
                ],
            )
        return AgentArtifacts(summary=reasoning.summary, memories=[memory])
