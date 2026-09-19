---
title: Agent Harness product requirements
status: final
created: 2026-09-19
updated: 2026-09-19
sources:
  - ../../source-ledger.md
  - ../../product-briefs/brief-agent-harness-2026-09-19/brief.md
---

# Product requirements

## Objective and release boundary

Agent Harness must let a developer author shared working preferences and project them safely into
Claude Code and Codex. The v1 stable matrix is Claude Code CLI and Codex CLI on macOS and Linux.
Editor and desktop clients may remain available as preview integrations with explicit status.

## Functional requirements

- **FR1 — Shared primitives:** The system must author rules, skills, roles, workflows and stances in
  one provider-neutral catalog.
- **FR2 — Resolution:** The system must resolve user-selected stance variants into one explicit
  policy result before adapter projection.
- **FR3 — Native projections:** Claude Code and Codex adapters must translate the shared result into
  their native supported formats without claiming unavailable parity.
- **FR4 — Preview and apply:** A user must be able to preview every managed change before applying it.
- **FR5 — Ownership:** Applied state must record prior and managed values so conflict-safe uninstall
  and rollback can preserve unrelated user configuration.
- **FR6 — Diagnostics:** The CLI must distinguish published qualification from local installation,
  activation and drift.
- **FR7 — Evidence:** Compatibility claims must reference versioned native evidence for an exact
  runtime, client, operating system and source revision under evaluation.
- **FR8 — Task continuity:** Work may transfer between supported runtimes through neutral,
  non-authoritative task state without transferring approvals or verification claims.
- **FR9 — Public planning:** Managed work must have a stable BMad ID, a GitHub issue and links in both
  directions before implementation ownership begins.
- **FR10 — Extensibility:** Contributors must be able to add or replace primitives without modifying
  a second runtime-specific authority.
- **FR11 — Observability:** Local measurements must distinguish known, partial, unavailable and failed
  data and shall not require remote telemetry.
- **FR12 — Release integrity:** Published releases and public support information must identify the
  same immutable source revision, evidence and compatibility status.

## Non-functional requirements

- **NFR1 — Preservation:** Install, sync, drift repair and uninstall must preserve unrelated settings
  and user edits; ambiguous conflicts fail visibly.
- **NFR2 — Reproducibility:** Deterministic generation and tests must run on Python 3.9 and the newest
  Python version in the test matrix.
- **NFR3 — Security:** Secrets and private paths must not enter tracked code, evidence or planning
  artifacts; authorization cannot be weakened by a stance.
- **NFR4 — Portability:** Stable support covers macOS and Linux; native Windows is unsupported and
  WSL2 remains unqualified until evidence says otherwise.
- **NFR5 — Auditability:** A support or release claim must be traceable to exact evidence bytes and
  cannot hide a contradictory active failure.
- **NFR6 — Reversibility:** Local configuration changes must be atomic where practical, recoverable and
  safe under repeat application.
- **NFR7 — Maintainability:** Generated projections are reproducible outputs, not parallel source
  catalogs; repository decisions are explained once at their authority.
- **NFR8 — Accessibility:** Public documentation and terminal output must remain understandable without
  color alone and use direct, status-specific language.

## Delivery programs

Delivery ownership and requirement coverage are maintained in `../../epics.md`.

## Success measures

- A clean user can preview, apply, repeat, upgrade, roll back and uninstall on every supported
  environment combination.
- Every supported environment combination passes the required native cases against the frozen v1
  candidate.
- A first-time visitor can identify the product, support status and safest experiment from the README.
- Migration tooling reports no duplicate planning IDs, broken artifact links or one-way issue mappings.

## Explicitly deferred

Stable editor/desktop support, Cursor and Grok adapters, hosted agents, native memory merging, the UML
viewer and automatic semantic authorization are outside the v1 contract.
