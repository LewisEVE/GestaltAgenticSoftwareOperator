"""Gestalt blackboard implementation spanning semantic and graph memory."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase
from sqlalchemy import DateTime, Float, Integer, String, Text, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from gestalt.config import BlackboardConfig
from gestalt.protocol import (
    BlackboardMemoryRecord,
    BlackboardQuery,
    BlackboardQueryResult,
    BlackboardRelation,
    GestaltAuditReport,
    GestaltCommand,
    GestaltStatsReport,
    MemoryKind,
    OptimizationProposal,
)
from gestalt.utils.logging import get_logger
from gestalt.utils.runtime import is_sqlite_url

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for blackboard tables."""


class MemoryRow(Base):
    """Durable blackboard memory row."""

    __tablename__ = "blackboard_memory"

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    memory_kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    embedding_json: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class StatsRow(Base):
    """Persisted monitor stats reports."""

    __tablename__ = "stats_reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    collected_by: Mapped[str] = mapped_column(String(64))
    load_level: Mapped[int] = mapped_column(Integer)
    performance_tier: Mapped[str] = mapped_column(String(32))
    cost_efficiency_score: Mapped[int] = mapped_column(Integer)
    security_risk_score: Mapped[int] = mapped_column(Integer)
    gestalt_cohesion_score: Mapped[int] = mapped_column(Integer)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    active_cycles: Mapped[int] = mapped_column(Integer, default=0)
    failure_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuditRow(Base):
    """Persisted security audit reports."""

    __tablename__ = "audit_reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    audited_by: Mapped[str] = mapped_column(String(64))
    overall_risk_score: Mapped[int] = mapped_column(Integer)
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CommandRow(Base):
    """Persisted orchestrator or agent commands."""

    __tablename__ = "commands"

    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    command_type: Mapped[str] = mapped_column(String(64), index=True)
    issued_by: Mapped[str] = mapped_column(String(64))
    target_agent: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class OptimizationRow(Base):
    """Persisted optimizer proposals."""

    __tablename__ = "optimization_proposals"

    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class PromptOverlayRow(Base):
    """Persisted runtime prompt and routing overrides."""

    __tablename__ = "prompt_overlays"

    overlay_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(128), index=True)
    overlay_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class BlackboardQueryError(RuntimeError):
    """Raised when the blackboard cannot satisfy a query."""


class Neo4jGraphStore:
    """Very small async wrapper around Neo4j for relation writes and reads."""

    def __init__(self, config: BlackboardConfig) -> None:
        self._config = config
        self._driver: AsyncDriver | None = None

    async def initialize(self) -> None:
        """Initialize the Neo4j driver."""

        if is_sqlite_url(self._config.database_url):
            return
        self._driver = AsyncGraphDatabase.driver(
            self._config.neo4j_uri,
            auth=(self._config.neo4j_username, self._config.neo4j_password.get_secret_value()),
        )

    async def close(self) -> None:
        """Close the Neo4j driver."""

        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def merge_relations(self, relations: Iterable[BlackboardRelation]) -> None:
        """Upsert graph relations into Neo4j."""

        if self._driver is None:
            return
        query = """
        UNWIND $relations AS relation
        MERGE (source:Entity {entity_type: relation.source_type, entity_id: relation.source_id})
        MERGE (target:Entity {entity_type: relation.target_type, entity_id: relation.target_id})
        MERGE (source)-[edge:GESTALT_RELATION {relation_id: relation.relation_id}]->(target)
        SET edge.relation_type = relation.relation_type,
            edge.metadata = relation.metadata
        """
        async with self._driver.session(database="neo4j") as session:
            await session.run(query, relations=[relation.model_dump(mode="json") for relation in relations])

    async def query_relations(self, entity_id: str) -> list[BlackboardRelation]:
        """Fetch related relations for an entity id."""

        if self._driver is None:
            return []
        query = """
        MATCH (source:Entity)-[edge:GESTALT_RELATION]->(target:Entity)
        WHERE source.entity_id = $entity_id OR target.entity_id = $entity_id
        RETURN source.entity_type AS source_type,
               source.entity_id AS source_id,
               edge.relation_id AS relation_id,
               edge.relation_type AS relation_type,
               target.entity_type AS target_type,
               target.entity_id AS target_id,
               edge.metadata AS metadata
        """
        async with self._driver.session(database="neo4j") as session:
            cursor = await session.run(query, entity_id=entity_id)
            records = await cursor.data()
        return [BlackboardRelation.model_validate(record) for record in records]


class GestaltBlackboard:
    """Unified blackboard service for semantic, relational, and operational memory."""

    def __init__(self, config: BlackboardConfig) -> None:
        self._config = config
        self._engine: AsyncEngine = create_async_engine(
            config.database_url,
            echo=False,
            future=True,
        )
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
        self._graph_store = Neo4jGraphStore(config)

    @property
    def supports_vector_search(self) -> bool:
        """Return whether vector search should be attempted."""

        return not is_sqlite_url(self._config.database_url)

    async def initialize(self) -> None:
        """Create schema and initialize backing services."""

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            await self._graph_store.initialize()
        except Exception as exc:  # pragma: no cover - exercised in integration environments
            logger.warning(
                "neo4j initialization failed; continuing with relational blackboard only",
                extra={"error": str(exc)},
            )

    async def close(self) -> None:
        """Close engine and graph store."""

        await self._graph_store.close()
        await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async SQLAlchemy session."""

        async with self._sessionmaker() as session:
            yield session

    async def write_memory(self, record: BlackboardMemoryRecord) -> BlackboardMemoryRecord:
        """Persist a semantic memory record."""

        row = MemoryRow(
            record_id=str(record.record_id),
            trace_id=str(record.trace_id),
            memory_kind=record.memory_kind.value,
            title=record.title,
            content=record.content,
            tags_json=json.dumps(record.tags),
            embedding_json=json.dumps(record.embedding) if record.embedding is not None else None,
            metadata_json=json.dumps(record.metadata),
            created_at=record.created_at,
        )
        async with self.session() as session:
            session.add(row)
            await session.commit()
        return record

    async def query_memory(self, query: BlackboardQuery) -> BlackboardQueryResult:
        """Query memory records using a simple ranked relational strategy."""

        started = datetime.now(UTC)
        async with self.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MemoryRow).order_by(MemoryRow.created_at.desc()).limit(query.limit * 3),
                    )
                )
                .scalars()
                .all()
            )
            candidates = [self._memory_from_row(row) for row in rows]

        normalized_query = query.query.lower()
        scored = sorted(
            candidates,
            key=lambda record: self._score_memory(record, normalized_query, query.filters),
            reverse=True,
        )
        matches = [record for record in scored if self._score_memory(record, normalized_query, query.filters) > 0][
            : query.limit
        ]
        relations = []
        if matches:
            relations = await self._graph_store.query_relations(str(matches[0].record_id))
        latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000
        return BlackboardQueryResult(query=query, matches=matches, relations=relations, latency_ms=latency_ms)

    async def write_stats_report(self, report: GestaltStatsReport) -> GestaltStatsReport:
        """Persist a stats report."""

        row = StatsRow(
            report_id=str(report.report_id),
            trace_id=str(report.trace_id),
            collected_by=report.collected_by,
            load_level=int(report.load_level),
            performance_tier=report.performance_tier.value,
            cost_efficiency_score=report.cost_efficiency_score,
            security_risk_score=report.security_risk_score,
            gestalt_cohesion_score=report.gestalt_cohesion_score,
            queue_depth=report.queue_depth,
            active_cycles=report.active_cycles,
            failure_ratio=report.failure_ratio,
            p95_latency_ms=report.p95_latency_ms,
            payload_json=report.model_dump_json(),
            captured_at=report.captured_at,
        )
        async with self.session() as session:
            session.add(row)
            await session.commit()
        return report

    async def get_latest_stats(self) -> GestaltStatsReport | None:
        """Return the most recent stats report."""

        async with self.session() as session:
            row = (
                await session.execute(select(StatsRow).order_by(StatsRow.captured_at.desc()).limit(1))
            ).scalar_one_or_none()
        if row is None:
            return None
        return GestaltStatsReport.model_validate_json(row.payload_json)

    async def write_audit_report(self, report: GestaltAuditReport) -> GestaltAuditReport:
        """Persist an audit report."""

        row = AuditRow(
            report_id=str(report.report_id),
            trace_id=str(report.trace_id),
            audited_by=report.audited_by,
            overall_risk_score=report.overall_risk_score,
            findings_json=json.dumps([finding.model_dump(mode="json") for finding in report.findings]),
            payload_json=report.model_dump_json(),
            created_at=report.created_at,
        )
        async with self.session() as session:
            session.add(row)
            await session.commit()
        return report

    async def write_command(self, command: GestaltCommand) -> GestaltCommand:
        """Persist a command record."""

        row = CommandRow(
            command_id=str(command.command_id),
            trace_id=str(command.trace_id),
            command_type=command.command_type.value,
            issued_by=command.issued_by,
            target_agent=command.target_agent,
            rationale=command.rationale,
            status=command.status.value,
            payload_json=command.model_dump_json(),
            created_at=command.created_at,
        )
        async with self.session() as session:
            session.add(row)
            await session.commit()
        return command

    async def write_optimization_proposal(self, proposal: OptimizationProposal) -> OptimizationProposal:
        """Persist an optimizer proposal."""

        row = OptimizationRow(
            proposal_id=str(proposal.proposal_id),
            trace_id=str(proposal.trace_id),
            title=proposal.title,
            summary=proposal.summary,
            confidence=proposal.confidence.value,
            payload_json=proposal.model_dump_json(),
            created_at=proposal.created_at,
        )
        async with self.session() as session:
            session.add(row)
            await session.commit()
        return proposal

    async def update_prompt_policy(self, target: str, overlay: dict[str, Any]) -> None:
        """Persist a prompt or routing overlay for runtime self-optimization."""

        row = PromptOverlayRow(target=target, overlay_json=json.dumps(overlay))
        async with self.session() as session:
            session.add(row)
            await session.commit()

    async def get_prompt_policy(self, target: str) -> dict[str, Any]:
        """Fetch the latest overlay for a target."""

        async with self.session() as session:
            row = (
                await session.execute(
                    select(PromptOverlayRow)
                    .where(PromptOverlayRow.target == target)
                    .order_by(PromptOverlayRow.created_at.desc())
                    .limit(1),
                )
            ).scalar_one_or_none()
        return json.loads(row.overlay_json) if row else {}

    async def link_entities(self, relations: list[BlackboardRelation]) -> list[BlackboardRelation]:
        """Persist graph relations."""

        if relations:
            await self._graph_store.merge_relations(relations)
        return relations

    async def compute_cohesion_inputs(self) -> dict[str, Any]:
        """Compute blackboard-derived inputs used by the orchestrator."""

        async with self.session() as session:
            stats_count = (await session.execute(select(StatsRow.report_id))).scalars().all()
            audit_rows = (
                (await session.execute(select(AuditRow).order_by(AuditRow.created_at.desc()).limit(10))).scalars().all()
            )
            command_rows = (
                (await session.execute(select(CommandRow).order_by(CommandRow.created_at.desc()).limit(25)))
                .scalars()
                .all()
            )
        failed_commands = sum(1 for row in command_rows if row.status == "failed")
        recent_risk_average = sum(row.overall_risk_score for row in audit_rows) / len(audit_rows) if audit_rows else 0.0
        return {
            "stats_samples": len(stats_count),
            "failed_commands": failed_commands,
            "recent_average_audit_risk": recent_risk_average,
            "supports_vector_search": self.supports_vector_search,
        }

    def _memory_from_row(self, row: MemoryRow) -> BlackboardMemoryRecord:
        """Convert a SQLAlchemy row to a protocol model."""

        return BlackboardMemoryRecord(
            record_id=UUID(row.record_id),
            trace_id=UUID(row.trace_id),
            memory_kind=MemoryKind(row.memory_kind),
            title=row.title,
            content=row.content,
            tags=json.loads(row.tags_json or "[]"),
            embedding=json.loads(row.embedding_json) if row.embedding_json else None,
            metadata=json.loads(row.metadata_json or "{}"),
            created_at=row.created_at,
        )

    @staticmethod
    def _score_memory(
        record: BlackboardMemoryRecord,
        normalized_query: str,
        filters: dict[str, Any],
    ) -> float:
        """Simple lexical ranking for development and fallback environments."""

        haystack = " ".join([record.title, record.content, " ".join(record.tags)]).lower()
        score = 0.0
        for token in normalized_query.split():
            if token in haystack:
                score += 2.0
        if normalized_query in haystack:
            score += 5.0
        for key, expected in filters.items():
            if record.metadata.get(key) == expected:
                score += 1.0
        return score
