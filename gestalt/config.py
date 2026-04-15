"""Application configuration loading for Gestalt Core."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when runtime settings are invalid."""


class AppConfig(BaseModel):
    """Application server metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = "gestalt-core"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8080, ge=1, le=65535)
    admin_token_env: str = "GESTALT_ADMIN_TOKEN"
    admin_token: SecretStr


class ModelRouteConfig(BaseModel):
    """Configured model route aliases by runtime tier."""

    model_config = ConfigDict(extra="forbid")

    low: str = Field(min_length=1)
    medium: str = Field(min_length=1)
    high: str = Field(min_length=1)
    critical: str = Field(min_length=1)


class ModelsConfig(BaseModel):
    """LiteLLM routing and completion defaults."""

    model_config = ConfigDict(extra="forbid")

    enable_mock_llm: bool = True
    default_alias: str = Field(min_length=1)
    routes: ModelRouteConfig
    embedding_alias: str = Field(min_length=1)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=3_000, ge=256, le=32_000)


class BlackboardConfig(BaseModel):
    """Shared blackboard configuration."""

    model_config = ConfigDict(extra="forbid")

    database_url: str = Field(min_length=1)
    neo4j_uri: str = Field(min_length=1)
    neo4j_username: str = Field(min_length=1)
    neo4j_password: SecretStr
    vector_dimensions: int = Field(default=24, ge=8, le=4096)
    semantic_top_k: int = Field(default=8, ge=1, le=100)
    memory_namespace: str = Field(default="gestalt", min_length=1)
    use_sqlite_fallback_for_tests: bool = True

    @computed_field
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


class EventConfig(BaseModel):
    """Redis Streams event bus configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["redis", "memory"] = "redis"
    redis_url: str = Field(min_length=1)
    stream_name: str = Field(default="gestalt.events", min_length=1)
    consumer_group: str = Field(default="gestalt-core", min_length=1)
    approval_ttl_seconds: int = Field(default=600, ge=30, le=86_400)
    max_stream_length: int = Field(default=10_000, ge=100, le=1_000_000)


class SchedulerConfig(BaseModel):
    """APScheduler interval settings."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = "UTC"
    monitor_interval_minutes: int = Field(default=5, ge=1, le=60)
    security_audit_interval_hours: int = Field(default=4, ge=1, le=24)
    knowledge_maintenance_minutes: int = Field(default=30, ge=1, le=1440)
    optimizer_interval_minutes: int = Field(default=30, ge=1, le=1440)


class LatencyThresholds(BaseModel):
    """Stats latency thresholds."""

    model_config = ConfigDict(extra="forbid")

    medium: int = Field(default=800, ge=1)
    high: int = Field(default=2_000, ge=1)
    critical: int = Field(default=5_000, ge=1)


class ErrorRateThresholds(BaseModel):
    """Stats error rate thresholds."""

    model_config = ConfigDict(extra="forbid")

    degraded: float = Field(default=0.05, ge=0.0, le=1.0)
    critical: float = Field(default=0.15, ge=0.0, le=1.0)


class QueueDepthThresholds(BaseModel):
    """Queue depth thresholds used to derive load tiers."""

    model_config = ConfigDict(extra="forbid")

    low: int = Field(default=5, ge=0)
    medium: int = Field(default=20, ge=0)
    high: int = Field(default=50, ge=0)
    critical: int = Field(default=100, ge=0)


class CohesionPenalties(BaseModel):
    """Penalty weights used by cohesion logic."""

    model_config = ConfigDict(extra="forbid")

    audit_finding: int = Field(default=8, ge=0, le=100)
    failed_command: int = Field(default=5, ge=0, le=100)
    blackboard_conflict: int = Field(default=12, ge=0, le=100)


class StatsConfig(BaseModel):
    """Stats policy configuration."""

    model_config = ConfigDict(extra="forbid")

    latency_thresholds_ms: LatencyThresholds
    error_rate_thresholds: ErrorRateThresholds
    queue_depth_thresholds: QueueDepthThresholds
    cohesion_penalties: CohesionPenalties
    optimizer_trigger_delta: int = Field(default=10, ge=1, le=100)


class AuditConfig(BaseModel):
    """Audit policy configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    cadence_hours: int = Field(default=4, ge=1, le=24)
    max_open_findings_before_escalation: int = Field(default=5, ge=1, le=1000)
    hallucination_score_threshold: int = Field(default=20, ge=0, le=100)
    jailbreak_score_threshold: int = Field(default=15, ge=0, le=100)
    enforce_event_approval: bool = True
    require_trace_ids: bool = True


class TelemetryConfig(BaseModel):
    """OpenTelemetry and logging configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    service_name_env: str = "GESTALT_OTEL_SERVICE_NAME"
    exporter_endpoint_env: str = "GESTALT_OTEL_EXPORTER_OTLP_ENDPOINT"
    resource_attributes: dict[str, str] = Field(default_factory=dict)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    service_name: str = "gestalt-core"
    exporter_endpoint: str | None = None


class SecurityConfig(BaseModel):
    """Security boundary configuration."""

    model_config = ConfigDict(extra="forbid")

    sandbox_enabled: bool = True
    sandbox_timeout_seconds: int = Field(default=30, ge=1, le=600)
    outbound_http_allowlist: list[str] = Field(default_factory=list)
    kubernetes_allowed_namespaces: list[str] = Field(default_factory=list)


class AgentPolicyConfig(BaseModel):
    """Per-agent enablement, routing preference, and tool allowlist."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model_preference: Literal["low", "medium", "high", "critical"] = "medium"
    max_retries: int = Field(default=2, ge=0, le=10)
    tool_allowlist: list[str] = Field(default_factory=list)


class GestaltSettings(BaseSettings):
    """Merged environment and YAML-backed application settings."""

    model_config = SettingsConfigDict(
        env_prefix="GESTALT_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    config_path: Path = Field(default=Path("config/gestalt.yaml"))
    app: AppConfig
    models: ModelsConfig
    blackboard: BlackboardConfig
    events: EventConfig
    scheduler: SchedulerConfig
    stats: StatsConfig
    audit: AuditConfig
    telemetry: TelemetryConfig
    security: SecurityConfig
    agents: dict[str, AgentPolicyConfig]

    @computed_field
    @property
    def version(self) -> str:
        return "1.0.0"

    @model_validator(mode="after")
    def validate_agents(self) -> GestaltSettings:
        required_agents = {
            "orchestrator",
            "monitor",
            "analyzer",
            "planner_executor",
            "optimizer",
            "knowledge",
            "security_audit",
        }
        missing = required_agents.difference(self.agents)
        if missing:
            missing_names = ", ".join(sorted(missing))
            raise ValueError(f"Missing agent policy configuration for: {missing_names}")
        return self


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file from disk."""

    config_path = Path(path)
    if not config_path.exists():
        raise SettingsError(f"Config file not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SettingsError("Top-level YAML configuration must be a mapping.")
    return data


def _resolve_env(name: str, default: str | None = None) -> str:
    """Resolve an environment variable with an optional default."""

    value = os.getenv(name, default)
    if value in (None, ""):
        raise SettingsError(f"Required environment variable is missing: {name}")
    return value


def _build_agent_configs(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize per-agent configuration from YAML."""

    agents = payload.get("agents")
    if isinstance(agents, dict) and agents:
        return agents

    tools = payload.get("tools", {})
    if not isinstance(tools, dict):
        tools = {}
    defaults = {
        "orchestrator": {"model_preference": "high"},
        "monitor": {"model_preference": "low"},
        "analyzer": {"model_preference": "medium"},
        "planner_executor": {"model_preference": "high"},
        "optimizer": {"model_preference": "medium"},
        "knowledge": {"model_preference": "medium"},
        "security_audit": {"model_preference": "critical"},
    }
    normalized: dict[str, Any] = {}
    for name, config in defaults.items():
        normalized[name] = {
            "enabled": True,
            "max_retries": 2,
            "tool_allowlist": tools.get(name, []),
            **config,
        }
    return normalized


def build_settings(config_path: str | Path | None = None) -> GestaltSettings:
    """Build validated settings from YAML plus environment values."""

    candidate_path = Path(config_path) if config_path else Path("config/gestalt.yaml")
    payload = load_yaml_config(candidate_path)

    app_payload = payload.get("app", {})
    telemetry_payload = payload.get("telemetry", {})
    blackboard_payload = payload.get("blackboard", {})
    events_payload = payload.get("events", {})

    normalized_payload = {
        "config_path": candidate_path,
        "app": {
            **app_payload,
            "admin_token": _resolve_env(app_payload.get("admin_token_env", "GESTALT_ADMIN_TOKEN"), "change-me"),
        },
        "models": payload.get("models", {}),
        "blackboard": {
            "database_url": _resolve_env(
                blackboard_payload.get("database_url_env", "GESTALT_DATABASE_URL"),
                "sqlite+aiosqlite:///./gestalt.db",
            ),
            "neo4j_uri": _resolve_env(
                blackboard_payload.get("neo4j_uri_env", "GESTALT_NEO4J_URI"), "bolt://neo4j:7687"
            ),
            "neo4j_username": _resolve_env(
                blackboard_payload.get("neo4j_username_env", "GESTALT_NEO4J_USERNAME"),
                "neo4j",
            ),
            "neo4j_password": _resolve_env(
                blackboard_payload.get("neo4j_password_env", "GESTALT_NEO4J_PASSWORD"),
                "change-me",
            ),
            "vector_dimensions": blackboard_payload.get("vector_dimensions", 24),
            "semantic_top_k": blackboard_payload.get("semantic_top_k", 8),
            "memory_namespace": blackboard_payload.get("memory_namespace", "gestalt"),
            "use_sqlite_fallback_for_tests": blackboard_payload.get("use_sqlite_fallback_for_tests", True),
        },
        "events": {
            **events_payload,
            "redis_url": _resolve_env(events_payload.get("redis_url_env", "GESTALT_REDIS_URL"), "redis://redis:6379/0"),
        },
        "scheduler": payload.get("scheduler", {}),
        "stats": payload.get("stats", {}),
        "audit": payload.get("audit", {}),
        "telemetry": {
            **telemetry_payload,
            "service_name": _resolve_env(
                telemetry_payload.get("service_name_env", "GESTALT_OTEL_SERVICE_NAME"),
                app_payload.get("name", "gestalt-core"),
            ),
            "exporter_endpoint": os.getenv(
                telemetry_payload.get("exporter_endpoint_env", "GESTALT_OTEL_EXPORTER_OTLP_ENDPOINT")
            ),
        },
        "security": payload.get("security", {}),
        "agents": _build_agent_configs(payload),
    }
    normalized_payload["events"].pop("redis_url_env", None)
    normalized_payload["app"].pop("admin_token_env", None)
    normalized_payload["telemetry"].pop("service_name_env", None)
    normalized_payload["telemetry"].pop("exporter_endpoint_env", None)

    try:
        return GestaltSettings.model_validate(normalized_payload)
    except ValidationError as exc:
        raise SettingsError(f"Invalid settings: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings(config_path: str | Path | None = None) -> GestaltSettings:
    """Return cached application settings."""

    return build_settings(config_path=config_path)
