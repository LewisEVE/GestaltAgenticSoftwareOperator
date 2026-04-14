"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gestalt.config import SettingsError, build_settings


def test_build_settings_uses_repository_config() -> None:
    """The checked-in config file should parse successfully."""

    settings = build_settings(Path("config/gestalt.yaml"))

    assert settings.app.name == "gestalt-core"
    assert settings.events.stream_name == "gestalt.events"
    assert "security_audit" in settings.agents


def test_build_settings_rejects_missing_agent_policy(tmp_path: Path) -> None:
    """Required agents must be defined."""

    invalid_config = tmp_path / "gestalt.yaml"
    invalid_config.write_text(
        """
app:
  name: gestalt-core
  environment: test
models:
  enable_mock_llm: true
  default_alias: mock://default
  routes:
    low: mock://low
    medium: mock://medium
    high: mock://high
    critical: mock://critical
  embedding_alias: mock://embed
blackboard:
  database_url_env: GESTALT_DATABASE_URL
  neo4j_uri_env: GESTALT_NEO4J_URI
  neo4j_username_env: GESTALT_NEO4J_USERNAME
  neo4j_password_env: GESTALT_NEO4J_PASSWORD
events:
  backend: redis
  redis_url_env: GESTALT_REDIS_URL
scheduler:
  timezone: UTC
  monitor_interval_minutes: 5
  security_audit_interval_hours: 4
  knowledge_maintenance_minutes: 30
  optimizer_interval_minutes: 30
telemetry:
  enabled: false
security:
  sandbox_enabled: true
stats:
  latency_thresholds_ms:
    medium: 800
    high: 2000
    critical: 5000
  error_rate_thresholds:
    degraded: 0.05
    critical: 0.15
  queue_depth_thresholds:
    low: 5
    medium: 20
    high: 50
    critical: 100
  cohesion_penalties:
    audit_finding: 8
    failed_command: 5
    blackboard_conflict: 12
  optimizer_trigger_delta: 10
agents:
  monitor:
    tool_allowlist: []
audit:
  enabled: true
  cadence_hours: 4
  max_open_findings_before_escalation: 5
  hallucination_score_threshold: 20
  jailbreak_score_threshold: 15
  enforce_event_approval: true
  require_trace_ids: true
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(SettingsError):
        build_settings(invalid_config)
