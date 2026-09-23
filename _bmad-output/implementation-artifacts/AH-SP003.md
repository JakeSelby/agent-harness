---
bmad_id: "AH-SP003"
type: "spike"
title: "Jev: Evaluate short source-to-output fidelity"
lifecycle: "completed"
provenance: "reconstructed"
github_issue: 159
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/159"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP003 — Jev: Evaluate short source-to-output fidelity

<!-- bmad-sync:begin -->
- **GitHub issue:** [#159](https://github.com/JakeSelby/agent-harness/issues/159)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** completed

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This file reconstructs planning metadata from the existing GitHub record. It does not imply that a BMad artifact existed when the original work was performed.
<!-- bmad-sync:end -->

## Question

Can a decision provider judge the semantic fidelity of a short output to a short source under a narrow
transformation instruction, checking contradictions, unsupported additions, changed attribution and
lost uncertainty as separate criteria? The decision waiting on it was whether a fidelity pack would be
offered as a bounded check.

Closed as not planned on 2026-09-21, before the experiment ran. It was one of seven additional bounded
experiments (#156 to #162) that the epic re-scope closed with the other prose-level checks, because
nothing consumed those answers and nothing could score them.
[Source: https://github.com/JakeSelby/agent-harness/issues/159]
[Source: https://github.com/JakeSelby/agent-harness/issues/135]

## Experiment

As proposed, not run:
- **Input:** a short source, a narrowly stated transformation instruction and a short output, all
  supplied by the caller; per-pack input limits declared and enforced, with oversized or missing input
  left unverified rather than silently truncated.
- **Fixtures:** faithful paraphrases and controlled single-error variants, held-out source families,
  and honest omissions the instruction allows. Public or synthetic fixtures first.
- **Baseline:** a configured LLM guard under an explicit budget.
- **Measured:** misses, false alarms, abstentions, errors, latency and available cost, per criterion,
  on a held-out split with labels fixed before evaluation. Ordinary tests offline; live tests opt-in and
  budgeted.

## Exit criterion

None was fixed. The issue required labels before evaluation and a held-out split but stated no numeric
threshold, and required no default enforcement before workload-specific validation.

## Result

Not run. Closed as not planned on 2026-09-21.

## Decision

Retired with the epic re-scope. No fidelity pack is planned. Long-document summary checking, source
summarization to fit the limit, external fact checking and claims of whole-agent correctness were out of
scope even in the proposal, as were a generic quality score, inferred permissions, model training and
live configuration changes. Publishing the provider's performance results stays subject to its terms.

## Dev notes

- Would have depended on #136, #137 and #138, with #140 only for later automatic runtime delivery.
- The issue names no PRD requirement.
- [Source: https://github.com/JakeSelby/agent-harness/issues/159]

## Change log

- 2026-09-23: written from the issue and pull-request record.
