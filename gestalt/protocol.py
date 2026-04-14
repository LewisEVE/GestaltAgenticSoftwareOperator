"""Strict Pydantic protocols for the Gestalt Core framework."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gestalt.stats import AgentHealth, GestaltStats, LoadLevel, PerformanceTier
from gestalt.utils.time import utc_now


class GestaltBaseModel(BaseModel):
    """Common model configuration for all framework protocol models."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=False,
        validate_assignment=True,
    )


class GestaltMessageRole(StrEnum):
    """Supported message roles inside the Gestalt graph."""

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    AUDIT = "audit"
    ORCHESTRATOR = "orchestrator"


class GestaltCommandType(StrEnum):
    """Canonical command categories understood by the orchestrator."""

    ANALYZE = "analyze"
    EXECUTE = "execute"
    OPTIMIZE = "optimize"
    AUDIT = "audit"
    UPDATE_STATS = "update_stats"
    UPDATE_MEMORY = "update_memory"
    APPROVE_EVENT = "approve_event"
    REMEDIATE = "remediate"
    ESCALATE = "escalate"
    HALT = "halt"


class GestaltEventType(StrEnum):
    """Event bus event categories."""

    PEER_SIGNAL = "peer_signal"
    COMMAND_PUBLISHED = "command_published"
    AUDIT_ALERT = "audit_alert"
    STATS_UPDATED = "stats_updated"
    OPTIMIZATION_PROPOSED = "optimization_proposed"
    INCIDENT_DETECTED = "incident_detected"
    EXECUTION_PROGRESS = "execution_progress"


class AuditSeverity(StrEnum):
    """Severity level for audit findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditCategory(StrEnum):
    """Audit finding taxonomy."""

    PROMPT_INJECTION = "prompt_injection"
    HALLUCINATION = "hallucination"
    PERMISSION = "permission"
    BLACKBOARD = "blackboard"
    EVENT_BUS = "event_bus"
    CHECKPOINT = "checkpoint"
    TOOLING = "tooling"
    DEADLOCK = "deadlock"
    OBSERVABILITY = "observability"
    SANDBOX = "sandbox"
    CONFIGURATION = "configuration"
    COST = "cost"


class ToolExecutionMode(StrEnum):
    """Execution modes available for registered tools."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"
    SANDBOXED = "sandboxed"


class DecisionConfidence(StrEnum):
    """Confidence level for orchestrator or agent decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandStatus(StrEnum):
    """Lifecycle status for a command."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class MemoryKind(StrEnum):
    """Blackboard memory classification."""

    INCIDENT = "incident"
    FACT = "fact"
    PLAN = "plan"
    EXECUTION = "execution"
    OPTIMIZATION = "optimization"
    AUDIT = "audit"
    STATS = "stats"
    KNOWLEDGE = "knowledge"


class BlackboardQueryMode(StrEnum):
    """Supported blackboard query strategies."""

    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"
    EXACT = "exact"


class SchedulerSource(StrEnum):
    """Origin of a graph execution request."""

    API = "api"
    SCHEDULER = "scheduler"
    EVENT = "event"
    INTERNAL = "internal"


class AgentDecision(StrEnum):
    """High-level orchestrator routing decision."""

    MONITOR = "monitor"
    ANALYZE = "analyze"
    PLAN_AND_EXECUTE = "plan_and_execute"
    OPTIMIZE = "optimize"
    CURATE_KNOWLEDGE = "curate_knowledge"
    RUN_SECURITY_AUDIT = "run_security_audit"
    FINALIZE = "finalize"


class AuditEvidence(GestaltBaseModel):
    """Evidence supporting an audit finding."""

    source: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemediationInstruction(GestaltBaseModel):
    """Machine-readable remediation instruction."""

    instruction_id: UUID = Field(default_factory=uuid4)
    command_type: GestaltCommandType
    title: str = Field(min_length=3)
    rationale: str = Field(min_length=10)
    priority: Literal["low", "medium", "high", "urgent"]
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditFinding(GestaltBaseModel):
    """Single finding emitted by the security audit agent."""

    finding_id: UUID = Field(default_factory=uuid4)
    category: AuditCategory
    severity: AuditSeverity
    summary: str = Field(min_length=8)
    detail: str = Field(min_length=16)
    evidence: list[AuditEvidence] = Field(default_factory=list)
    remediation: list[RemediationInstruction] = Field(default_factory=list)
    hypothesis_id: str | None = None


class AgentHealthSnapshot(GestaltBaseModel):
    """Per-agent health information captured in a stats report."""

    agent_name: str = Field(min_length=2)
    status: AgentHealth
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)


class GestaltMessage(GestaltBaseModel):
    """Typed message exchanged inside the super-graph."""

    message_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    role: GestaltMessageRole
    sender: str = Field(min_length=2)
    recipient: str = Field(min_length=2)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class GestaltCommand(GestaltBaseModel):
    """Typed command issued by the orchestrator or a trusted agent."""

    command_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    command_type: GestaltCommandType
    issued_by: str = Field(min_length=2)
    target_agent: str = Field(min_length=2)
    rationale: str = Field(min_length=8)
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM
    status: CommandStatus = CommandStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class GestaltCommandResult(GestaltBaseModel):
    """Result produced after a command has been processed."""

    command_id: UUID
    trace_id: UUID
    status: CommandStatus
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    completed_at: datetime = Field(default_factory=utc_now)


class GestaltSummary(GestaltBaseModel):
    """Summary generated at the end of a graph cycle."""

    cycle_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    objective: str = Field(min_length=3)
    completed_actions: list[str] = Field(default_factory=list)
    pending_actions: list[str] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    cohesion_score: int = Field(ge=0, le=100)
    security_risk_score: int = Field(ge=0, le=100)
    produced_at: datetime = Field(default_factory=utc_now)


class GestaltEvent(GestaltBaseModel):
    """Event published onto Redis Streams."""

    event_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    approval_id: UUID | None = None
    event_type: GestaltEventType
    source_agent: str = Field(min_length=2)
    target_agent: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class BlackboardMemoryRecord(GestaltBaseModel):
    """Memory record persisted in the blackboard."""

    record_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    memory_kind: MemoryKind
    title: str = Field(min_length=3)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class BlackboardRelation(GestaltBaseModel):
    """Graph edge stored in the Neo4j relationship layer."""

    relation_id: UUID = Field(default_factory=uuid4)
    source_type: str = Field(min_length=2)
    source_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=2)
    target_type: str = Field(min_length=2)
    target_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BlackboardQuery(GestaltBaseModel):
    """Typed query against the blackboard."""

    query: str = Field(min_length=1)
    mode: BlackboardQueryMode = BlackboardQueryMode.HYBRID
    limit: int = Field(default=5, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class BlackboardQueryResult(GestaltBaseModel):
    """Result set returned from a blackboard query."""

    query: BlackboardQuery
    matches: list[BlackboardMemoryRecord] = Field(default_factory=list)
    relations: list[BlackboardRelation] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, ge=0.0)


class GestaltStatsReport(GestaltBaseModel):
    """Structured system statistics emitted by the monitor agent."""

    report_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    collected_by: str = Field(default="monitor")
    load_level: LoadLevel
    performance_tier: PerformanceTier
    cost_efficiency_score: int = Field(ge=0, le=100)
    security_risk_score: int = Field(ge=0, le=100)
    gestalt_cohesion_score: int = Field(ge=0, le=100)
    queue_depth: int = Field(default=0, ge=0)
    active_cycles: int = Field(default=0, ge=0)
    failure_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    agent_health: list[AgentHealthSnapshot] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=utc_now)


class AgentExecutionReport(GestaltBaseModel):
    """Standard execution report emitted by every agent invocation."""

    report_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    agent_name: str = Field(min_length=2)
    command_id: UUID | None = None
    status: CommandStatus
    summary: str = Field(min_length=8)
    emitted_commands: list[GestaltCommand] = Field(default_factory=list)
    emitted_memories: list[BlackboardMemoryRecord] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_timing(self) -> AgentExecutionReport:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be greater than or equal to started_at")
        return self


class OptimizationProposal(GestaltBaseModel):
    """Optimization recommendation proposed by the optimizer agent."""

    proposal_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=5)
    summary: str = Field(min_length=12)
    expected_benefit: str = Field(min_length=8)
    config_patch: dict[str, Any] = Field(default_factory=dict)
    prompt_overrides: dict[str, str] = Field(default_factory=dict)
    model_routing_overrides: dict[str, str] = Field(default_factory=dict)
    confidence: DecisionConfidence
    created_at: datetime = Field(default_factory=utc_now)


class GestaltAuditReport(GestaltBaseModel):
    """Comprehensive security and integrity report."""

    report_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    audited_by: str = Field(default="security_audit")
    scope: list[str] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    remediation_commands: list[GestaltCommand] = Field(default_factory=list)
    overall_risk_score: int = Field(ge=0, le=100)
    created_at: datetime = Field(default_factory=utc_now)


class EventApproval(GestaltBaseModel):
    """Approval token issued by the orchestrator for peer-to-peer events."""

    approval_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    source_agent: str = Field(min_length=2)
    target_agent: str = Field(min_length=2)
    permitted_event: GestaltEventType
    rationale: str = Field(min_length=8)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def ensure_future_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("expires_at must be timezone aware")
        if value <= utc_now():
            raise ValueError("expires_at must be in the future")
        return value


class AgentContextEnvelope(GestaltBaseModel):
    """Normalized state fragment provided to an agent invocation."""

    trace_id: UUID = Field(default_factory=uuid4)
    cycle_id: UUID = Field(default_factory=uuid4)
    objective: str = Field(min_length=3)
    source: SchedulerSource
    latest_stats: GestaltStats
    blackboard_context: list[BlackboardMemoryRecord] = Field(default_factory=list)
    inbound_commands: list[GestaltCommand] = Field(default_factory=list)
    approvals: list[EventApproval] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GestaltGraphState(GestaltBaseModel):
    """Shared state object passed through the LangGraph super-graph."""

    trace_id: UUID = Field(default_factory=uuid4)
    cycle_id: UUID = Field(default_factory=uuid4)
    source: SchedulerSource = SchedulerSource.INTERNAL
    objective: str = Field(min_length=3, default="Maintain system cohesion")
    stats: GestaltStats = Field(default_factory=GestaltStats)
    decisions: list[AgentDecision] = Field(default_factory=list)
    messages: list[GestaltMessage] = Field(default_factory=list)
    commands: list[GestaltCommand] = Field(default_factory=list)
    command_results: list[GestaltCommandResult] = Field(default_factory=list)
    memories: list[BlackboardMemoryRecord] = Field(default_factory=list)
    optimization_proposals: list[OptimizationProposal] = Field(default_factory=list)
    audit_reports: list[GestaltAuditReport] = Field(default_factory=list)
    execution_reports: list[AgentExecutionReport] = Field(default_factory=list)
    latest_summary: GestaltSummary | None = None
    approvals: list[EventApproval] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CycleRequest(GestaltBaseModel):
    """API request payload to trigger a graph cycle."""

    objective: str = Field(min_length=3)
    source: SchedulerSource = SchedulerSource.API
    metadata: dict[str, Any] = Field(default_factory=dict)


class CycleResponse(GestaltBaseModel):
    """API response for a completed or accepted graph cycle."""

    trace_id: UUID
    cycle_id: UUID
    accepted: bool = True
    summary: GestaltSummary | None = None
    commands: list[GestaltCommand] = Field(default_factory=list)


class TriggerAuditRequest(GestaltBaseModel):
    """API request to force an audit cycle."""

    scope: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(GestaltBaseModel):
    """Simple health endpoint response."""

    status: Literal["live", "ready", "degraded"]
    service: str = Field(default="gestalt-core")
    version: str
    timestamp: datetime = Field(default_factory=utc_now)
    dependencies: dict[str, str] = Field(default_factory=dict)
