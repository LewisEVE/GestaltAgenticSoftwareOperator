 # Contributing to gestalt-core

 Thank you for considering a contribution to `gestalt-core`.

 This project aims to be a production-grade, open-source framework for headless software-operations automation built on a single LangGraph super-graph. We welcome contributions that improve correctness, reliability, developer experience, observability, documentation, and deployment readiness.

 ## Ways to contribute

 - Report bugs
 - Propose improvements
 - Improve documentation
 - Add tests
 - Refine deployment assets
 - Contribute new tools or agent capabilities that fit the architecture

 ## Before you start

 Please read:

 - `README.md`
 - `SECURITY.md`
 - `CODE_OF_CONDUCT.md`
 - `deployment/README.md`

 If your change affects architecture, agent lifecycle behavior, or protocol contracts, make sure your proposal preserves the core invariants:

 - one central orchestrator
 - one shared blackboard
 - strict typed protocols
 - graph-native agent execution
 - explicit, testable operational behavior

 ## Development setup

 ```bash
 python3 -m pip install --user --break-system-packages -e .[dev]
 ```

 Run checks before opening a pull request:

 ```bash
 python3 -m ruff check gestalt tests
 python3 -m pyright
 python3 -m pytest
 ```

 Run the application locally:

 ```bash
 uvicorn gestalt.main:app --reload
 ```

 ## Branching and pull requests

 - Keep pull requests focused and reviewable.
 - Prefer one logical change per pull request.
 - Include tests when you change runtime behavior.
 - Update docs when you change user-facing behavior, configuration, or deployment steps.
 - Avoid unrelated refactors in the same pull request.

 Recommended PR structure:

 1. problem statement
 2. implementation summary
 3. validation evidence
 4. caveats / follow-ups

 ## Code style expectations

 - Python 3.12+
 - type annotations on non-trivial code paths
 - Pydantic v2 models for typed contracts
 - structured, explicit error handling
 - production-oriented logging
 - tests for changed behavior

 Please preserve the existing architecture instead of introducing side-channel orchestration or duplicate memory pathways.

 ## Commit guidance

 Use descriptive commit messages that explain the logical change, for example:

 - `Add event bus approval integration tests`
 - `Improve scheduler readiness documentation`
 - `Refine optimizer proposal persistence`

 ## Reporting bugs

 When filing a bug, include:

 - expected behavior
 - actual behavior
 - reproduction steps
 - relevant logs
 - environment details
 - whether Redis / Postgres / Neo4j were available

 ## Feature requests

 Feature proposals are most likely to be accepted when they include:

 - the operational problem being solved
 - why it belongs in `gestalt-core`
 - protocol / graph / blackboard implications
 - testing and rollout expectations

 ## Security issues

 Do **not** open public issues for undisclosed security vulnerabilities. Follow `SECURITY.md` instead.
