---
bmad_id: "AH-SP002"
type: "spike"
title: "Jev: Evaluate advisory action-risk and tool-output screening with Jev"
lifecycle: "completed"
provenance: "reconstructed"
github_issue: 146
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/146"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP002 — Jev: Evaluate advisory action-risk and tool-output screening with Jev

<!-- bmad-sync:begin -->
- **GitHub issue:** [#146](https://github.com/JakeSelby/agent-harness/issues/146)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** completed

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This file reconstructs planning metadata from the existing GitHub record. It does not imply that a BMad artifact existed when the original work was performed.
<!-- bmad-sync:end -->

## Question

Can bounded, advisory judgments from a decision provider close the semantic gaps that deterministic
command grading and instruction-pattern scanning leave: whether an unfamiliar action is on task,
destructive or an exfiltration risk, and whether tool output carries injected instructions?

Closed as not planned on 2026-09-19, before the experiment ran.
[Source: https://github.com/JakeSelby/agent-harness/issues/146]

## Experiment

As proposed, not run:
- Separate on-task, destructive-action, exfiltration-risk and instruction-injection judgments over
  bounded evidence, skipping the existing provably read-only fast path.
- Labelled tests including adversarially framed commands and results, benign quoted instructions,
  unfamiliar wrappers and uncertain cases.
- Payloads minimized and redacted before external inference; no raw secret sent to judge whether it is
  one.
- Report misses, false alarms and provider failures. Results stay advisory.

## Exit criterion

None was fixed. The issue states constraints rather than a numeric threshold: never override a
deterministic denial, never grant permission, never treat a low risk score as proof of safety, and any
blocking or auto-authorization behaviour would need a separately reviewed issue.

## Result

Not run. The issue was closed as not planned after scope review on 2026-09-19.

## Decision

Retired. Prompt-injection screening, exfiltration screening and general destructive-action safety
judgments are removed from the integration; existing deterministic permissions and security controls
remain authoritative, and tool isolation and native enforcement remain the security boundary. The
retained comparison of one action against explicit task boundaries moved to #142, and after #142 was
itself closed, #372 supersedes this issue and carries that bounded comparison as a tighten-only
ask-band gate.
[Source: https://github.com/JakeSelby/agent-harness/issues/135]

## Dev notes

- Bound: PRD §8 non-goals (no decision provider relaxes or denies a decision; semantic
  auto-authorization is out of scope) and FR-48 (tighten-only).
- Would have depended on #138 (packs and evaluation) and #140 (runtime events).
- [Source: https://github.com/JakeSelby/agent-harness/issues/146]
- [Source: https://github.com/JakeSelby/agent-harness/issues/372]

## Change log

- 2026-09-23: written from the issue and pull-request record.
- 2026-09-23: corrected after sample review: architecture bindings, current behaviour and history
  checked against the 2026-09-23 spine, the code and the record.
