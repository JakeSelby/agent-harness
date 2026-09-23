---
bmad_id: "AH-SP008"
type: "spike"
title: "Choose the neutral session-turn row: NirSession, agentsview's schema, or our own"
lifecycle: "active"
provenance: "authored"
github_issue: 541
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/541"
parent_bmad_id: "AH-E002"
parent_github_issue: 116
updated: "2026-09-23"
---

# AH-SP008 — Choose the neutral session-turn row: NirSession, agentsview's schema, or our own

<!-- bmad-sync:begin -->
- **GitHub issue:** [#541](https://github.com/JakeSelby/agent-harness/issues/541)
- **Primary parent:** [AH-E002](https://github.com/JakeSelby/agent-harness/issues/116)
- **State:** active

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This work item was authored as part of the repository's committed BMad planning system.
<!-- bmad-sync:end -->

## Question

Which neutral turn row should the harness keep when it parses a runtime's native session file once: agent-session-format's NirSession, agentsview's schema, or a row of its own beside the ledger row ([#541](https://github.com/JakeSelby/agent-harness/issues/541))?

The work that waits on it is recorded on both sides: #543, the session archive, is blocked by this spike and stores "the row #541 chose" ([#543](https://github.com/JakeSelby/agent-harness/issues/543)), and the 2026-09-23 spine defers "the session archive's row format" to this spike, bound by AD-11 and AD-16 [Source: _bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md#Deferred].

Why now, per the issue:
- Claude Code transcripts expire at 30 days, their schema is undocumented, and the request for one was closed as not planned.
- Codex rollouts are zstd-compressed after 7 days, which the repository's Python 3.9 standard-library floor cannot read.
- 10 of 130 ledger sessions were already transcript-less when the ledger plan was written.
- The usage ledger already applies "parse native storage once, keep the row forever"; the spike asks whether the same holds for turns.

## Experiment

- **Inputs:** every local Claude Code and Codex session on the reference machine, parsed into each of the three candidate rows.
- **Counted:** unparsed events; lost fields (tool-call ids, subagent links, compaction markers, usage); whether both the native ids and the harness session id survive.
- **Measured:** parse time and row-store size per 1,000 sessions.
- **Noted:** the licence and Python-floor fit of any dependency, zstd included.

[Source: [#541](https://github.com/JakeSelby/agent-harness/issues/541)]

## Exit criterion

One candidate:
1. parses 100% of events on both runtimes, with zero silently dropped fields the harness reads today;
2. keeps a foreign key to the native id, the ledger row, the decision rows and the worker run;
3. fits a permissive licence and the 3.9 floor, or names the optional dependency.

The decision is recorded in the artifact, and no code is merged beyond the spike script ([#541](https://github.com/JakeSelby/agent-harness/issues/541)).

## Result

Not yet run. The issue is open on the v0.15.0 milestone, and no spike script or result is on `main`.

## Decision

Open: the exit criterion above decides it. The chosen row becomes the archive schema in #543.

## Dev notes

- **Bound:**
  - FR-63: Coordination for parallel agents — the archive "stores neutral turn rows keyed to the harness session, searchable by full text."
  - AD-11: Local ledgers are the system of record, and grow compatibly — it prevents "history lost to backend retention or transcript expiry", the loss this spike responds to.
  - AD-16: Parallel writers coordinate through shared, recorded state — named with AD-11 in the spine's deferral.
  - NFR-11 Licensing and the Python 3.9 floor bound the dependency choice.
- **Out of scope:** search, embeddings and any agent-facing surface; those are #543 and #544 ([#541](https://github.com/JakeSelby/agent-harness/issues/541)).
- **Reservation:** the BMad ID was reserved by PR #548 for #547.
- References:
  - [#541](https://github.com/JakeSelby/agent-harness/issues/541), [#543](https://github.com/JakeSelby/agent-harness/issues/543), [#544](https://github.com/JakeSelby/agent-harness/issues/544)
  - [Source: _bmad-output/planning-artifacts/prds/prd-agent-harness-2026-09-23/prd.md#FR-63: Coordination for parallel agents]
  - [Source: _bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md#AD-11: Local ledgers are the system of record, and grow compatibly]

## Change log

- 2026-09-23: written from the issue and pull-request record.
