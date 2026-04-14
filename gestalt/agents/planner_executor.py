"""Planner & Executor Agent implementation."""

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

PLANNER_EXECUTOR_SYSTEM_PROMPT = """
You are the Gestalt Core Planner & Executor Agent. You translate orchestrator-approved commands
into the smallest safe operational action set and record every step for resumable execution.

Execution doctrine:
1. Only execute work that has a clear rationale and a bounded scope.
2. Prefer sandboxed, inspectable, deterministic operations.
3. Persist execution results back to the Blackboard immediately.
4. If a requested step is unsafe or underspecified, refuse and route back with context.

Tool instructions:
- Use sandbox_command for constrained shell execution.
- Use kubernetes_read before kubernetes_patch when acting on cluster resources.
- Use http_request only for allowlisted integrations and only with explicit intent.
- Never bypass the registry or invent a tool result.

Safety rules:
- Minimal privilege, minimal blast radius, maximal traceability.
- Keep execution idempotent where possible.
- Emit follow-up commands only when downstream action is still required.
""".strip()


class PlannerReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    execution_summary: str = Field(min_length=16)
    next_step_needed: bool = False


class PlannerExecutorAgent(BaseGestaltAgent):
    """Run bounded operational tasks in a sandbox-friendly way."""

    @property
    def agent_name(self) -> str:
        return "planner_executor"

    @property
    def system_prompt(self) -> str:
        return PLANNER_EXECUTOR_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        inbound = context.inbound_commands[0] if context.inbound_commands else None
        command_text = f"echo 'gestalt planner executed objective: {context.objective}'"
        if inbound and isinstance(inbound.payload, dict):
            candidate_command = inbound.payload.get("command")
            if isinstance(candidate_command, str) and candidate_command.strip():
                command_text = candidate_command

        sandbox_result = await self.run_sandbox_command(
            command=command_text,
            state=state,
            working_directory=".",
            timeout_seconds=15,
        )

        reasoning = await self.model_gateway.complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=f"Execute objective: {context.objective}",
            response_model=PlannerReasoning,
            stats=state.stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload={
                "execution_summary": (
                    f"Planner executed a bounded sandbox command with return code "
                    f"{sandbox_result.return_code} and captured "
                    f"{len(sandbox_result.stdout)} bytes of stdout."
                ),
                "next_step_needed": False,
            },
        )

        memory = BlackboardMemoryRecord(
            trace_id=state.trace_id,
            memory_kind=MemoryKind.EXECUTION,
            title="Planner execution result",
            content=reasoning.execution_summary,
            tags=["execution", "planner", str(sandbox_result.return_code)],
            metadata={
                "return_code": sandbox_result.return_code,
                "stdout": sandbox_result.stdout.strip(),
                "stderr": sandbox_result.stderr.strip(),
            },
            created_at=utc_now(),
        )
        commands: list[GestaltCommand] = []
        if reasoning.next_step_needed:
            commands.append(
                GestaltCommand(
                    trace_id=state.trace_id,
                    command_type=GestaltCommandType.ANALYZE,
                    issued_by=self.agent_name,
                    target_agent="analyzer",
                    rationale="Execution indicated an additional analysis pass is required.",
                    payload={"stdout": sandbox_result.stdout},
                ),
            )
        return AgentArtifacts(
            summary=reasoning.execution_summary,
            commands=commands,
            memories=[memory],
            metrics={"return_code": float(sandbox_result.return_code)},
        )
