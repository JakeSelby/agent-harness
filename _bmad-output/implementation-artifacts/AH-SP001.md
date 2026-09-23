---
bmad_id: "AH-SP001"
type: "spike"
title: "Jev: Verify stop claims against gate evidence"
lifecycle: "active"
provenance: "reconstructed"
github_issue: 141
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/141"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP001 — Jev: Verify stop claims against gate evidence

<!-- bmad-sync:begin -->
- **GitHub issue:** [#141](https://github.com/JakeSelby/agent-harness/issues/141)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** active

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This file reconstructs planning metadata from the existing GitHub record. It does not imply that a BMad artifact existed when the original work was performed.
<!-- bmad-sync:end -->

## Question

Can a decision provider, shown one short completion claim beside the gate result that followed it,
separate supported claims from unsupported ones well enough for the stop-claim point to leave `shadow`
and advise at Stop? The decision waiting on it is whether the stop-claim point, the epic's first
consumer, is promoted to `advise` or ships in `shadow` with the release saying so.

Context: the 2026-09-21 re-scope promoted this issue from a deferred experiment to the first consumer.
Among published coding-harness uses of a decision model, checking a completion claim at Stop has the
strongest measured result; the label is free, because the gate result that follows a claim is ground
truth the harness already computes; and the repository holds a working prototype with a frozen corpus,
replay and budget caps.
[Source: https://github.com/JakeSelby/agent-harness/issues/141]

## Experiment

- **Inputs:** held-out stop-gate rows from the decision log (#370), each carrying the completion claim
  (#387, delivered by #574 behind `telemetry.completion_claim`) and the gate result, plus the
  hand-labelled seed fixtures from #377.
- **Unit:** one bounded claim/result pair per stop. Whole-task completion is not inferred and no
  evidence is collected automatically.
- **Runner:** `harness decisions eval --point <stop-claim point>` (#138), threshold fitted on the dev
  split and reported on held-out.
- **Baselines:** the deterministic `stop-gate` answer, and wording alone.
- **Measured:** discrimination against the wording-alone baseline, and false blocks per 100 stops.
  Insufficient evidence is reported apart from contradiction and from provider errors.
- **Where the provider sits:** as a note beside `stop-gate`, which still decides.

## Exit criterion

Promote the stop-claim point to `advise` only when, on held-out decision-log rows:
1. False blocks are no more than 2 per 100 stops.
2. Discrimination is well above wording alone. The issue gives no number for this bar.
   [ASSUMPTION: the discrimination margin is to be written as a number before the held-out run; the
   issue states it only qualitatively.]

A point that misses either stays in `shadow`, and the release says so (epic exit criterion 2).

## Result

Not yet run. Blocked by #136, #138 and #387 (closed), and by #140 and #377 (open). A prototype is ported
onto current `main` on a branch and passes the full gate, per the issue; it has not landed on `main`.

## Decision

Open: the held-out result against the exit criterion decides it.
- **Pass:** the stop-claim point moves to `advise`: a note at Stop; `stop-gate` still decides, and a
  favourable judgment never replaces repository gates or user acceptance. `act` for this point is
  listed first among FR-48's planned consumers.
- **Miss:** the point stays in `shadow`, and #147 documents it as such.

## Dev notes

- The deterministic exit-code and freshness checks stay in code; the provider never replaces them.
- The completion claim is the last 2 KiB of the turn's final assistant message, off by default under
  its own switch, because it is the only decision-log field holding assistant prose.
  [Source: https://github.com/JakeSelby/agent-harness/pull/574]
- Bound: FR-48 (tighten-only stages; stop-claim check named as the first `act` consumer), FR-49
  (evidence gates), FR-27 (decision log and completion claim), and AD-15, Decision providers are
  subordinate: at the stop point `act` may turn an allowed stop into a block that returns the turn to
  the agent, and never releases a block. [Source: _bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md#AD-15]
- [Source: https://github.com/JakeSelby/agent-harness/issues/141]
- [Source: https://github.com/JakeSelby/agent-harness/issues/387]
- [Source: _bmad-output/planning-artifacts/prds/prd-agent-harness-2026-09-23/prd.md#FR-48]
- [Source: _bmad-output/planning-artifacts/research/technical-decision-layer-evidence-2026-09-23/digests/gh-issue-141.md]

## Change log

- 2026-09-23: written from the issue and pull-request record.
- 2026-09-23: corrected after sample review: architecture bindings, current behaviour and history
  checked against the 2026-09-23 spine, the code and the record.
