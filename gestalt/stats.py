"""Gestalt runtime statistics, thresholds, and adaptive policy logic."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoadLevel(IntEnum):
    """Discrete system load tier used for routing and model downgrades."""

    VERY_LOW = 1
    LOW = 2
    MODERATE = 3
    HIGH = 4
    EXTREME = 5


class PerformanceTier(StrEnum):
    """Observed performance posture based on historical execution quality."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentHealth(StrEnum):
    """Health status of an individual agent worker."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class StatsThresholds(BaseModel):
    """Configuration thresholds used to translate measurements into tiers."""

    model_config = ConfigDict(extra="forbid")

    medium_latency_ms: int = 800
    high_latency_ms: int = 2_000
    critical_latency_ms: int = 5_000
    degraded_error_rate: float = 0.05
    critical_error_rate: float = 0.15
    queue_low: int = 5
    queue_medium: int = 20
    queue_high: int = 50
    queue_critical: int = 100
    optimizer_trigger_delta: int = 10


class MonitorSnapshot(BaseModel):
    """Metrics captured by the Monitor Agent during a sampling cycle."""

    model_config = ConfigDict(extra="forbid")

    queue_depth: int = 0
    active_cycles: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    cost_per_cycle: float = 0.0
    blackboard_consistency: float = 1.0
    collaboration_success_rate: float = 1.0
    security_open_findings: int = 0

    @field_validator("error_rate", "blackboard_consistency", "collaboration_success_rate")
    @classmethod
    def validate_ratio(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "ratio fields must be between 0 and 1 inclusive"
            raise ValueError(msg)
        return value


class GestaltStats(BaseModel):
    """Adaptive operational state for the Gestalt runtime."""

    model_config = ConfigDict(extra="forbid")

    load_level: LoadLevel = LoadLevel.VERY_LOW
    performance_tier: PerformanceTier = PerformanceTier.LOW
    cost_efficiency_score: int = 100
    security_risk_score: int = 0
    gestalt_cohesion_score: int = 100
    agent_health: dict[str, AgentHealth] = Field(default_factory=dict)
    queue_depth: int = 0
    active_cycles: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    cost_per_cycle: float = 0.0
    blackboard_consistency: float = 1.0
    collaboration_success_rate: float = 1.0
    open_security_findings: int = 0
    optimizer_triggered: bool = False
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("cost_efficiency_score", "security_risk_score", "gestalt_cohesion_score")
    @classmethod
    def clamp_score(cls, value: int) -> int:
        return max(0, min(100, value))

    def promote_load(self) -> LoadLevel:
        self.load_level = LoadLevel(min(int(self.load_level) + 1, int(LoadLevel.EXTREME)))
        return self.load_level

    def demote_load(self) -> LoadLevel:
        self.load_level = LoadLevel(max(int(self.load_level) - 1, int(LoadLevel.VERY_LOW)))
        return self.load_level

    def promote_performance(self) -> PerformanceTier:
        order = [
            PerformanceTier.LOW,
            PerformanceTier.MEDIUM,
            PerformanceTier.HIGH,
            PerformanceTier.CRITICAL,
        ]
        self.performance_tier = order[min(order.index(self.performance_tier) + 1, len(order) - 1)]
        return self.performance_tier

    def demote_performance(self) -> PerformanceTier:
        order = [
            PerformanceTier.LOW,
            PerformanceTier.MEDIUM,
            PerformanceTier.HIGH,
            PerformanceTier.CRITICAL,
        ]
        self.performance_tier = order[max(order.index(self.performance_tier) - 1, 0)]
        return self.performance_tier

    def adjust_cost_efficiency(self, delta: int) -> int:
        self.cost_efficiency_score = max(0, min(100, self.cost_efficiency_score + delta))
        return self.cost_efficiency_score

    def adjust_security_risk(self, delta: int) -> int:
        self.security_risk_score = max(0, min(100, self.security_risk_score + delta))
        return self.security_risk_score

    def adjust_cohesion(self, delta: int) -> int:
        self.gestalt_cohesion_score = max(0, min(100, self.gestalt_cohesion_score + delta))
        return self.gestalt_cohesion_score

    def set_agent_health(self, agent_name: str, health: AgentHealth) -> None:
        self.agent_health[agent_name] = health

    def apply_monitor_snapshot(
        self,
        snapshot: MonitorSnapshot,
        thresholds: StatsThresholds | None = None,
    ) -> GestaltStats:
        thresholds = thresholds or StatsThresholds()
        self.queue_depth = snapshot.queue_depth
        self.active_cycles = snapshot.active_cycles
        self.average_latency_ms = snapshot.avg_latency_ms
        self.p95_latency_ms = snapshot.p95_latency_ms
        self.error_rate = snapshot.error_rate
        self.failure_count = snapshot.failure_count
        self.success_count = snapshot.success_count
        self.cost_per_cycle = snapshot.cost_per_cycle
        self.blackboard_consistency = snapshot.blackboard_consistency
        self.collaboration_success_rate = snapshot.collaboration_success_rate
        self.open_security_findings = snapshot.security_open_findings
        self.load_level = self._derive_load_level(snapshot.queue_depth, snapshot.active_cycles, thresholds)
        self.performance_tier = self._derive_performance_tier(
            snapshot.p95_latency_ms,
            snapshot.error_rate,
            thresholds,
        )
        self._refresh_cost_efficiency()
        self._refresh_security_risk()
        self._refresh_cohesion()
        self.last_updated = datetime.now(UTC)
        return self

    def derive_model_policy(self) -> dict[str, Any]:
        downgrade_to_small_model = self.load_level >= LoadLevel.HIGH and (
            self.cost_efficiency_score < 50 or self.performance_tier == PerformanceTier.CRITICAL
        )
        require_heightened_guardrails = self.security_risk_score >= 60
        return {
            "load_level": int(self.load_level),
            "performance_tier": self.performance_tier.value,
            "downgrade_to_small_model": downgrade_to_small_model,
            "require_heightened_guardrails": require_heightened_guardrails,
            "preferred_route": self._preferred_model_route(),
        }

    def should_trigger_optimizer(
        self,
        previous: GestaltStats | None = None,
        *,
        delta_threshold: int = 10,
    ) -> bool:
        if previous is None:
            return self.performance_tier in {PerformanceTier.HIGH, PerformanceTier.CRITICAL}
        score_deltas = [
            abs(self.cost_efficiency_score - previous.cost_efficiency_score),
            abs(self.security_risk_score - previous.security_risk_score),
            abs(self.gestalt_cohesion_score - previous.gestalt_cohesion_score),
        ]
        tier_changed = self.performance_tier != previous.performance_tier
        load_changed = self.load_level != previous.load_level
        self.optimizer_triggered = tier_changed or load_changed or max(score_deltas) >= delta_threshold
        return self.optimizer_triggered

    def should_trigger_security_intervention(self) -> bool:
        return self.security_risk_score >= 70 or self.open_security_findings >= 5

    def summary(self) -> dict[str, Any]:
        return {
            "load_level": int(self.load_level),
            "performance_tier": self.performance_tier.value,
            "cost_efficiency_score": self.cost_efficiency_score,
            "security_risk_score": self.security_risk_score,
            "gestalt_cohesion_score": self.gestalt_cohesion_score,
            "agent_health": {key: value.value for key, value in self.agent_health.items()},
            "optimizer_triggered": self.optimizer_triggered,
        }

    @staticmethod
    def _derive_load_level(
        queue_depth: int,
        active_cycles: int,
        thresholds: StatsThresholds,
    ) -> LoadLevel:
        effective_pressure = max(queue_depth, active_cycles * 5)
        if effective_pressure >= thresholds.queue_critical:
            return LoadLevel.EXTREME
        if effective_pressure >= thresholds.queue_high:
            return LoadLevel.HIGH
        if effective_pressure >= thresholds.queue_medium:
            return LoadLevel.MODERATE
        if effective_pressure >= thresholds.queue_low:
            return LoadLevel.LOW
        return LoadLevel.VERY_LOW

    @staticmethod
    def _derive_performance_tier(
        p95_latency_ms: float,
        error_rate: float,
        thresholds: StatsThresholds,
    ) -> PerformanceTier:
        if p95_latency_ms >= thresholds.critical_latency_ms or error_rate >= thresholds.critical_error_rate:
            return PerformanceTier.CRITICAL
        if p95_latency_ms >= thresholds.high_latency_ms or error_rate >= thresholds.degraded_error_rate:
            return PerformanceTier.HIGH
        if p95_latency_ms >= thresholds.medium_latency_ms:
            return PerformanceTier.MEDIUM
        return PerformanceTier.LOW

    def _refresh_cost_efficiency(self) -> None:
        latency_penalty = min(int(self.average_latency_ms / 100), 40)
        failure_penalty = min(int(self.error_rate * 100), 40)
        cost_penalty = min(int(self.cost_per_cycle * 10), 30)
        self.cost_efficiency_score = max(0, 100 - latency_penalty - failure_penalty - cost_penalty)

    def _refresh_security_risk(self) -> None:
        findings_penalty = min(self.open_security_findings * 10, 60)
        reliability_penalty = min(int(self.error_rate * 100), 20)
        cohesion_penalty = max(0, 20 - int(self.blackboard_consistency * 20))
        self.security_risk_score = max(0, min(100, findings_penalty + reliability_penalty + cohesion_penalty))

    def _refresh_cohesion(self) -> None:
        consistency_score = int(self.blackboard_consistency * 40)
        collaboration_score = int(self.collaboration_success_rate * 40)
        reliability_score = max(0, 20 - int(self.error_rate * 100))
        self.gestalt_cohesion_score = max(
            0,
            min(100, consistency_score + collaboration_score + reliability_score),
        )

    def _preferred_model_route(self) -> str:
        if self.performance_tier == PerformanceTier.CRITICAL:
            return "critical"
        if self.performance_tier == PerformanceTier.HIGH or self.load_level >= LoadLevel.HIGH:
            return "high"
        if self.performance_tier == PerformanceTier.MEDIUM or self.load_level == LoadLevel.MODERATE:
            return "medium"
        return "low"
