---
bmad_id: "AH-SP004"
type: "spike"
title: "Jev: Count the labelled decisions existing sessions already hold"
lifecycle: "completed"
provenance: "reconstructed"
github_issue: 371
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/371"
parent_bmad_id: null
parent_github_issue: null
updated: "2026-09-23"
---

# AH-SP004 — Jev: Count the labelled decisions existing sessions already hold

<!-- bmad-sync:begin -->
- **GitHub issue:** [#371](https://github.com/JakeSelby/agent-harness/issues/371)
- **Primary parent:** None
- **State:** completed

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This file reconstructs planning metadata from the existing GitHub record. It does not imply that a BMad artifact existed when the original work was performed.
<!-- bmad-sync:end -->

## Question

Do existing local artifacts already hold enough labelled decisions to evaluate a decision provider without
synthetic data? The issue ties the answer to the evaluation in #138: below the bar, evaluation starts
from hand-labelled fixtures and the decision log has to accumulate before any point is promoted.

The issue body names #135 as its parent; the story's manifest records no primary parent.
[Source: https://github.com/JakeSelby/agent-harness/issues/371]

## Experiment

A read-only, offline script over local session transcripts and the usage ledger that counts, for the
last 30 days:

- Stop events preceded by a completion claim, joined to the next gate result.
- Bash `ask` decisions joined to the user's approve or deny.
- Unnamed subagent spawns joined to a budget overrun.

Nothing leaves the machine; only counts are reported on the issue. Building the decision log itself, and
any call to an external service, were out of scope.

## Exit criterion

At least 200 labelled rows each for stop-claims and ask-prompts.

## Result

Recorded on the issue on 2026-09-21: "**Result: exit criterion missed for both target points.**" Measured
read-only and offline over 503 session transcripts from the last 30 days plus a 3,342-row usage ledger on
one workstation.

- **Stop claims:** about 13 gate-red stops are recoverable from transcripts, against a bar of 200. Stop-gate
  state keeps only the latest result per workspace, so passes after a claim are not recoverable at all.
- **Ask prompts:** 19 user rejections of a tool call. The hook's ask decision is never written anywhere, so
  a rejection cannot be joined to the grade that caused it. The ledger holds 31 `denied-by-grade` counts
  with no inputs.
- **Unnamed spawns:** 3,001 subagent rows carry `agent_type`, `requested_type`, `rerouted`, model, effort
  and output tokens. None carries its budget, but overrun can be derived against the posture table, so
  routing is the one point that can be evaluated from existing data.

The raw evidence is local and is not published; only the counts above are on the record.

## Decision

As recorded in the result: #138 starts from hand-labelled fixtures for stop-claims and the ask band, and
#370 has to be accumulating before either is promoted. #370 should also stamp the budget on subagent rows.
#370 did so: its PR (#385) added `budget_output_tokens` and `budget_tool_calls` to subagent rows.

## Dev notes

- Bound requirement: FR-27, Decision log `[ASSUMPTION: the spike measured the gap that the decision log
  fills; it predates the PRD]`.
- The counting script is not committed to the repository. Not recorded in the issue or pull request
  beyond the method above.
- Milestone: v0.13.0.
- [Source: https://github.com/JakeSelby/agent-harness/issues/371]
- [Source: https://github.com/JakeSelby/agent-harness/issues/370]
- [Source: https://github.com/JakeSelby/agent-harness/pull/385]

## Change log

- 2026-09-23: written from the issue and pull-request record.
