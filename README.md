# gestalt-core

`gestalt-core` is a production-grade, headless, server-side autonomous operations framework built around a **single LangGraph super-graph**. It is designed for SaaS, platform, DevOps, and growth operations workloads where multiple specialist agents must collaborate without fragmenting state, routing logic, or memory.

## Core guarantees

- **One super-graph, one brain**: the Gestalt Orchestrator is the only routing authority.
- **Native multi-agent execution**: specialist agents are graph-native nodes/subgraphs, not remote API silos.
- **Shared memory only through the Gestalt Blackboard**: Postgres + PGVector for durable/vectorized knowledge and Neo4j for relationship knowledge.
- **Strict typed protocols**: internal messages, commands, audits, stats, and API payloads use Pydantic v2 schemas.
- **Closed-loop operations**: MAPE-K + OODA execution with optimizer-driven runtime tuning and periodic security audit.
- **Production operations posture**: structured logging, OpenTelemetry, retries, checkpointing, Docker Compose, Kubernetes manifests, and automated tests.

## Architecture overview

### Control plane

1. **FastAPI runtime** receives cycle triggers, audit triggers, and health/stat queries.
2. **Gestalt Orchestrator** evaluates graph state, blackboard state, audit posture, and statistics.
3. **Conditional LangGraph edges** activate the next native agent node or subgraph.
4. **Specialist agents** read/write through the Blackboard and operate only on approved tools.
5. **Redis Streams Event Bus** handles orchestrator-approved peer signaling.
6. **Monitor, Optimizer, Knowledge, and Security Audit loops** keep the system adaptive and self-correcting.

### Data plane

- **Postgres + PGVector**: stats snapshots, commands, audit reports, optimization proposals, semantic memory.
- **Neo4j**: entity relationships, incident lineage, knowledge graph links.
- **LangGraph checkpointing**: resumable execution for long-running operations.

## Project structure

```text
gestalt-core/
├── gestalt/
│   ├── __init__.py
│   ├── config.py
│   ├── protocol.py
│   ├── blackboard.py
│   ├── base_agent.py
│   ├── orchestrator.py
│   ├── graph.py
│   ├── stats.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── base.py
│   │   └── implementations/
│   ├── agents/
│   │   ├── monitor.py
│   │   ├── analyzer.py
│   │   ├── planner_executor.py
│   │   ├── optimizer.py
│   │   ├── knowledge.py
│   │   └── security_audit.py
│   ├── events/
│   ├── utils/
│   └── main.py
├── config/
│   └── gestalt.yaml
├── tests/
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── k8s/
│   └── README.md
├── pyproject.toml
├── README.md
├── LICENSE
└── .env.example
```

## Development discipline

The codebase follows strict engineering rules:

1. No task is considered complete until the implementation, tests, and release notes agree.
2. Any runtime error must be root-caused and corrected before work proceeds.
3. New prompts or tasks extend the same codebase; existing architecture must absorb them cleanly.
4. Major milestones require validation through focused automated tests and, where appropriate, end-to-end runtime evidence.
5. All agent behavior must remain aligned with the shared Gestalt state machine rather than diverging into bespoke local flows.

## Runtime components

### Agents

- **Monitor Agent**: collects load, latency, failure, and health metrics every 5 minutes.
- **Analyzer Agent**: diagnoses anomalies and generates root-cause hypotheses.
- **Planner & Executor Agent**: translates orchestrator commands into safe operational actions.
- **Optimizer Agent**: tunes runtime model routing, prompts, and policy overlays.
- **Knowledge Agent**: curates semantic and graph memory to preserve reusable organizational knowledge.
- **Security Audit Agent**: performs periodic full-system audits every 4 hours by default.

### Stats system

The Stats subsystem tracks:

- `LoadLevel` (1-5)
- `PerformanceTier` (`low`, `medium`, `high`, `critical`)
- `CostEfficiencyScore` (0-100)
- `SecurityRiskScore` (0-100)
- `GestaltCohesionScore` (0-100)
- per-agent `AgentHealth`

The Monitor Agent publishes stats every 5 minutes. The Orchestrator consumes those stats to adapt routing and trigger the Optimizer when thresholds change.

## Configuration

Primary runtime settings live in `config/gestalt.yaml`, with environment overrides loaded from `.env`.

Key groups:

- model aliases and tier routing
- scheduler intervals
- blackboard and database connectivity
- event bus policy
- audit cadence and risk thresholds
- telemetry exporters
- tool allowlists per agent

See `.env.example` and `config/gestalt.yaml` for the full configuration surface.

## Open-source release files

The repository now includes the baseline community and release assets expected for
 a public open-source project:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- `OPEN_SOURCE_LAUNCH.md`
- `RELEASE_CHECKLIST.md`
- `.github/ISSUE_TEMPLATE/*`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/REPOSITORY_METADATA.md`

## Local development

### Install

```bash
python3.12 -m pip install --user --break-system-packages -e .[dev]
```

### Run tests

```bash
python3 -m ruff check gestalt tests
python3 -m pyright
python3 -m pytest
```

### Run locally

```bash
uvicorn gestalt.main:app --reload
```

## Docker Compose

Bring the full stack up with:

```bash
docker compose -f deployment/docker-compose.yml up --build
```

Services included:

- gestalt-core API
- Postgres with pgvector
- Redis
- Neo4j
- Prometheus
- Grafana
- OpenTelemetry Collector

The Compose stack ships with repository-local config files for Prometheus and the OpenTelemetry
Collector under `deployment/prometheus.yml` and `deployment/otel-collector-config.yaml`.
In this cloud environment the Docker CLI is unavailable, so configuration was validated up to the
file level and the runtime stack could not be smoke-tested with `docker compose up`.

See `deployment/README.md` for compose and Kubernetes deployment notes.

## Observability

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Tracing and metrics use OpenTelemetry and Prometheus-compatible instrumentation.

## Community and governance

For public repository readiness, review:

- `CONTRIBUTING.md` for contribution workflow
- `CODE_OF_CONDUCT.md` for community expectations
- `SECURITY.md` for responsible disclosure
- `SUPPORT.md` for support routing
- `OPEN_SOURCE_LAUNCH.md` and `.github/REPOSITORY_METADATA.md` for GitHub description, topics, and launch copy

## Release checklist

`RELEASE_CHECKLIST.md` captures the 1.0 release gate. The current release bar is:

- [x] passing Ruff, Pyright, and pytest
- [x] successful graph bootstrap and end-to-end cycle execution
- [x] working scheduler registration
- [x] documented Docker Compose and Kubernetes deployment
- [x] security audit and stats loops enabled by configuration

## License

MIT