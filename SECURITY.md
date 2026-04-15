 # Security Policy

 ## Supported versions

 Until a formal version support matrix is introduced, security fixes are expected
 to land on the latest published `1.x` line.

 | Version | Supported |
 | --- | --- |
 | 1.x | Yes |

 ## Reporting a vulnerability

 Please do **not** report undisclosed security vulnerabilities through public
 GitHub issues.

 Instead, use a private disclosure path managed by the maintainers. If a dedicated
 security mailbox is not yet configured, open a private maintainer contact through
 the repository owner and clearly mark the report as a **security disclosure**.

 A good report includes:

 - affected version or commit
 - vulnerability type
 - impact assessment
 - reproduction steps
 - proof-of-concept if safe to share
 - mitigation ideas, if known

 ## What to expect

 Maintainers should aim to:

 - acknowledge receipt within 5 business days
 - assess severity and scope
 - coordinate remediation privately
 - publish a fix and advisory when appropriate

 ## Sensitive areas in this project

 The following parts of `gestalt-core` deserve extra scrutiny:

 - orchestrator routing authority
 - agent tool allowlists
 - event bus approval enforcement
 - blackboard data integrity
 - model gateway prompt / response handling
 - sandbox command execution
 - deployment secrets and runtime configuration

 ## Hardening guidance for operators

 If you deploy this project, you should:

 - rotate all default secrets before first public exposure
 - run Postgres, Redis, and Neo4j with network restrictions
 - keep admin tokens out of committed files
 - enable telemetry and centralized logs in production
 - review tool allowlists before enabling mutating integrations
 - prefer private networks and least-privilege service accounts
