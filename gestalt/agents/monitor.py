"""Monitor Agent implementation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gestalt.base_agent import AgentArtifacts, BaseGestaltAgent
from gestalt.protocol import (
    AgentContextEnvelope,
    AgentHealthSnapshot,
    BlackboardMemoryRecord,
    GestaltCommand,
    GestaltCommandType,
    GestaltGraphState,
    GestaltStatsReport,
    MemoryKind,
)
from gestalt.stats import AgentHealth, GestaltStats, MonitorSnapshot, StatsThresholds
from gestalt.utils import utc_now

MONITOR_AGENT_SYSTEM_PROMPT = """
You are the Gestalt Core Monitor Agent, the network's continuous sensing organ inside the
single shared super-graph. Your duty is to translate raw operational telemetry into typed,
actionable, blackboard-synchronized state updates that preserve whole-system awareness.

Identity and mission:
1. You never optimize, execute, or audit directly. You sense, summarize, and escalate.
2. You treat the Gestalt Blackboard as the canonical memory plane for statistics, anomalies,
   and the latest cross-agent health posture.
3. You must keep the orchestrator informed about system pressure, performance degradation,
   cost drift, and emerging security-adjacent instability signals.

Mandatory operating doctrine:
- Always read the latest graph objective and statistics before speaking.
- Always prefer current telemetry over stale assumptions.
- Always produce outputs that can be serialized into the framework's strict schemas.
- Never emit a "final answer"; emit stats, supporting memory, and escalation commands.

Tool usage instructions:
- Use prometheus_query for queue depth, latency, and failure-rate signals.
- Use blackboard_write only through persisted agent artifacts rather than ad hoc free-form text.
- If telemetry is sparse, return the best available conservative estimate and explain the gap.

Stats policy:
- LoadLevel increases with queue pressure, concurrent cycles, and observed backlog.
- PerformanceTier increases as p95 latency and failure ratio degrade.
- CostEfficiencyScore must fall when latency and error waste increase.
- GestaltCohesionScore must reflect consistency, reliability, and collaboration success.
- Security-related instability must trigger a command to the Security Audit Agent when the
  risk threshold is crossed.

Alignment checks:
- Never override orchestrator authority.
- Never fabricate tool results.
- Never bypass the Blackboard.
- Ensure every emitted command contains a rationale and traceability metadata.
""".strip()


class MonitorReasoning(BaseModel):
    """Structured reasoning scaffold returned by the model gateway."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=12)
    anomaly_detected: bool = False


def _thresholds_from_settings(settings) -> StatsThresholds:
    return StatsThresholds(
        medium_latency_ms=settings.stats.latency_thresholds_ms.medium,
        high_latency_ms=settings.stats.latency_thresholds_ms.high,
        critical_latency_ms=settings.stats.latency_thresholds_ms.critical,
        degraded_error_rate=settings.stats.error_rate_thresholds.degraded,
        critical_error_rate=settings.stats.error_rate_thresholds.critical,
        queue_low=settings.stats.queue_depth_thresholds.low,
        queue_medium=settings.stats.queue_depth_thresholds.medium,
        queue_high=settings.stats.queue_depth_thresholds.high,
        queue_critical=settings.stats.queue_depth_thresholds.critical,
        optimizer_trigger_delta=settings.stats.optimizer_trigger_delta,
    )


class MonitorAgent(BaseGestaltAgent):
    """Collect runtime telemetry and publish typed system statistics."""

    @property
    def agent_name(self) -> str:
        return "monitor"

    @property
    def system_prompt(self) -> str:
        return MONITOR_AGENT_SYSTEM_PROMPT

    async def produce_artifacts(
        self,
        *,
        context: AgentContextEnvelope,
        messages,
        state: GestaltGraphState,
    ) -> AgentArtifacts:
        queue_metric = await self.query_prometheus(query="queue_depth", state=state)
        latency_metric = await self.query_prometheus(query="latency_p95_ms", state=state)
        error_metric = await self.query_prometheus(query="error_ratio", state=state)

        snapshot = MonitorSnapshot(
            queue_depth=int(queue_metric.value),
            active_cycles=max(1, len(state.execution_reports)),
            avg_latency_ms=float(latency_metric.value * 0.7),
            p95_latency_ms=float(latency_metric.value),
            error_rate=float(error_metric.value),
            failure_count=sum(1 for report in state.execution_reports if report.status.value == "failed"),
            success_count=sum(1 for report in state.execution_reports if report.status.value == "completed"),
            cost_per_cycle=max(0.1, float(latency_metric.value) / 1000),
            blackboard_consistency=1.0,
            collaboration_success_rate=0.95,
            security_open_findings=sum(len(report.findings) for report in state.audit_reports),
        )

        previous_stats = GestaltStats.model_validate(state.stats.model_dump(mode="python"))
        updated_stats = GestaltStats.model_validate(state.stats.model_dump(mode="python"))
        updated_stats.apply_monitor_snapshot(snapshot, _thresholds_from_settings(self.settings))

        reasoning = await self.model_gateway.complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=f"Monitor objective: {context.objective}",
            response_model=MonitorReasoning,
            stats=updated_stats,
            preferred_tier=self.settings.agents[self.agent_name].model_preference,
            mock_payload={
                "summary": (
                    f"Monitor observed queue depth {snapshot.queue_depth}, p95 latency "
                    f"{snapshot.p95_latency_ms:.1f}ms, and error rate {snapshot.error_rate:.2%}."
                ),
                "anomaly_detected": updated_stats.performance_tier.value in {"high", "critical"},
            },
        )
        reasoning = MonitorReasoning.model_validate(reasoning)

        health_snapshots = [
            AgentHealthSnapshot(agent_name=name, status=AgentHealth.HEALTHY) for name in self.settings.agents
        ]
        report = GestaltStatsReport(
            trace_id=state.trace_id,
            collected_by=self.agent_name,
            load_level=updated_stats.load_level,
            performance_tier=updated_stats.performance_tier,
            cost_efficiency_score=updated_stats.cost_efficiency_score,
            security_risk_score=updated_stats.security_risk_score,
            gestalt_cohesion_score=updated_stats.gestalt_cohesion_score,
            queue_depth=snapshot.queue_depth,
            active_cycles=snapshot.active_cycles,
            failure_ratio=snapshot.error_rate,
            p95_latency_ms=snapshot.p95_latency_ms,
            agent_health=health_snapshots,
        )

        commands: list[GestaltCommand] = []
        if updated_stats.should_trigger_optimizer(
            previous_stats,
            delta_threshold=self.settings.stats.optimizer_trigger_delta,
        ):
            commands.append(
                GestaltCommand(
                    trace_id=state.trace_id,
                    command_type=GestaltCommandType.OPTIMIZE,
                    issued_by=self.agent_name,
                    target_agent="optimizer",
                    rationale="Material telemetry drift requires adaptive optimization.",
                    payload={"stats": report.model_dump(mode="json")},
                ),
            )
        if updated_stats.should_trigger_security_intervention():
            commands.append(
                GestaltCommand(
                    trace_id=state.trace_id,
                    command_type=GestaltCommandType.AUDIT,
                    issued_by=self.agent_name,
                    target_agent="security_audit",
                    rationale="Security risk or open findings exceeded the intervention threshold.",
                    payload={"reason": "monitor_threshold_crossed"},
                ),
            )

        memory = BlackboardMemoryRecord(
            trace_id=state.trace_id,
            memory_kind=MemoryKind.STATS,
            title="Monitor telemetry snapshot",
            content=reasoning.summary,
            tags=["monitor", "stats", updated_stats.performance_tier.value],
            metadata={
                "queue_depth": snapshot.queue_depth,
                "p95_latency_ms": snapshot.p95_latency_ms,
                "error_rate": snapshot.error_rate,
            },
            created_at=utc_now(),
        )
        return AgentArtifacts(
            summary=reasoning.summary,
            commands=commands,
            memories=[memory],
            stats_report=report,
            metrics={
                "queue_depth": float(snapshot.queue_depth),
                "p95_latency_ms": snapshot.p95_latency_ms,
                "error_rate": snapshot.error_rate,
            },
        )
