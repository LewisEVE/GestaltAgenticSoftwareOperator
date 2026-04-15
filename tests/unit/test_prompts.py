"""Prompt completeness tests for specialist agents and orchestrator."""

from gestalt.agents import (
    ANALYZER_AGENT_SYSTEM_PROMPT,
    KNOWLEDGE_AGENT_SYSTEM_PROMPT,
    MONITOR_AGENT_SYSTEM_PROMPT,
    OPTIMIZER_AGENT_SYSTEM_PROMPT,
    PLANNER_EXECUTOR_SYSTEM_PROMPT,
    SECURITY_AUDIT_AGENT_SYSTEM_PROMPT,
)
from gestalt.orchestrator import GESTALT_ORCHESTRATOR_SYSTEM_PROMPT


def test_prompts_contain_required_operational_sections() -> None:
    prompts = [
        GESTALT_ORCHESTRATOR_SYSTEM_PROMPT,
        MONITOR_AGENT_SYSTEM_PROMPT,
        ANALYZER_AGENT_SYSTEM_PROMPT,
        PLANNER_EXECUTOR_SYSTEM_PROMPT,
        OPTIMIZER_AGENT_SYSTEM_PROMPT,
        KNOWLEDGE_AGENT_SYSTEM_PROMPT,
        SECURITY_AUDIT_AGENT_SYSTEM_PROMPT,
    ]

    for prompt in prompts:
        lowered = prompt.lower()
        assert "tool" in lowered
        assert "blackboard" in lowered
        assert "align" in lowered or "safeguard" in lowered or "safety" in lowered


def test_security_prompt_contains_extended_checklist() -> None:
    checklist_terms = [
        "prompt injection",
        "jailbreak",
        "orchestrator bypass",
        "sandbox escape",
        "telemetry blind spot",
    ]
    lowered = SECURITY_AUDIT_AGENT_SYSTEM_PROMPT.lower()
    for term in checklist_terms:
        assert term in lowered
