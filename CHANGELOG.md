# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-04-14

### Added

- Initial 1.0 release of the Gestalt Core framework.
- Single LangGraph super-graph architecture with a central Gestalt Orchestrator.
- Typed protocol layer for messages, commands, stats, and audit reports.
- Shared Gestalt Blackboard abstraction for vector and graph-backed memory.
- Unified BaseGestaltAgent lifecycle with specialist agent implementations.
- Redis Streams event bus with orchestrator approval workflow.
- FastAPI runtime, APScheduler jobs, observability hooks, and deployment assets.
- Docker Compose stack, Kubernetes manifests, and deployment runbook.
- Release checklist documenting the 1.0 ship criteria.
- Open-source launch documentation, GitHub metadata guidance, and community policy files.
- Unit and integration test suites covering core runtime behavior, routing, scheduler jobs,
  event-bus approvals, API endpoints, and end-to-end graph execution.
