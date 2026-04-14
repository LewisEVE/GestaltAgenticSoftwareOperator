"""Integration tests for the Gestalt blackboard service."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from gestalt.blackboard import GestaltBlackboard
from gestalt.config import BlackboardConfig
from gestalt.protocol import BlackboardMemoryRecord, BlackboardQuery, GestaltStatsReport, MemoryKind
from gestalt.stats import LoadLevel, PerformanceTier


async def test_blackboard_memory_round_trip(tmp_path: Path) -> None:
    """The blackboard should persist and query semantic memories."""

    config = BlackboardConfig(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'blackboard.db'}",
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("secret"),
        use_sqlite_fallback_for_tests=True,
    )
    blackboard = GestaltBlackboard(config)
    await blackboard.initialize()
    try:
        record = BlackboardMemoryRecord(
            memory_kind=MemoryKind.KNOWLEDGE,
            title="Deployment incident",
            content="Redis stream lag was detected in production.",
            tags=["redis", "incident"],
        )
        await blackboard.write_memory(record)

        result = await blackboard.query_memory(BlackboardQuery(query="redis incident"))

        assert result.matches
        assert result.matches[0].title == "Deployment incident"
    finally:
        await blackboard.close()


async def test_blackboard_stats_round_trip(tmp_path: Path) -> None:
    """The latest stats report should be queryable."""

    config = BlackboardConfig(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'stats.db'}",
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("secret"),
        use_sqlite_fallback_for_tests=True,
    )
    blackboard = GestaltBlackboard(config)
    await blackboard.initialize()
    try:
        report = GestaltStatsReport(
            load_level=LoadLevel.MODERATE,
            performance_tier=PerformanceTier.MEDIUM,
            cost_efficiency_score=70,
            security_risk_score=20,
            gestalt_cohesion_score=88,
        )
        await blackboard.write_stats_report(report)

        latest = await blackboard.get_latest_stats()

        assert latest is not None
        assert latest.report_id == report.report_id
        assert latest.load_level == LoadLevel.MODERATE
    finally:
        await blackboard.close()
