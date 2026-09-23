---
bmad_id: "AH-SP006"
type: "spike"
title: "Jev: Evaluate a typed same-work check for evasion_deny"
lifecycle: "active"
provenance: "authored"
github_issue: 374
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/374"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP006 — Jev: Evaluate a typed same-work check for evasion_deny

<!-- bmad-sync:begin -->
- **GitHub issue:** [#374](https://github.com/JakeSelby/agent-harness/issues/374)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** active

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This work item was authored as part of the repository's committed BMad planning system.
<!-- bmad-sync:end -->

## Question

`evasion_deny` in `lib/harness_core/lifecycle.py` decides whether a re-spawn is the same refused work
with a `difflib` ratio of 0.85 or more over a 2,000-character fingerprint, and it denies rather than
asks. Would a typed same-work judgment from a decision provider make fewer wrong denials without missing
more evasions?
[Source: https://github.com/JakeSelby/agent-harness/issues/374]

## Experiment

- **Inputs:** logged `evasion_deny` decisions from the decision log, replayed through the provider in
  `shadow`.
- **Labels:** hand-labelled pairs in three classes: reworded but the same work, similar but legitimately
  different, and unrelated.
- **Baseline:** the current `difflib` ratio at 0.85.
- **Measured:** false denials and missed evasions for each method on the same pairs.

## Exit criterion

On at least 50 labelled pairs, fixed in the issue before the run: the typed judgment makes fewer false
denials than the ratio, and no more missed evasions. The label is rare, so the run waits for the
decision log to accumulate.

## Result

Not yet run. Blocked by #138 and #370 (both closed); waiting on enough logged `evasion_deny` decisions to
label 50 pairs.

## Decision

Open: the labelled comparison against the exit criterion decides it. [ASSUMPTION: a pass would open a
story to replace or supplement the ratio, and a miss would keep it; the issue records neither.] Either way, whether the deny should become an ask is a
policy question for its own issue.

## Dev notes

- Follow-on, not a 0.13.0 release dependency.
- `evasion_deny` is defined in `lib/harness_core/lifecycle.py`, with `SIMILARITY = 0.85` and `FINGERPRINT_MAX = 2000` on `main`; lifecycle tests are in `tests/test_lifecycle.py`.
- Bound: FR-48 (a provider never turns an allow or an ask into a deny, and never relaxes a deny),
  FR-49 (shadow until a criterion is met), and AD-15, Decision providers are subordinate. [Source: _bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md#AD-15]
- [Source: https://github.com/JakeSelby/agent-harness/issues/374]

## Change log

- 2026-09-23: written from the issue and pull-request record.
- 2026-09-23: corrected after sample review: architecture bindings, current behaviour and history
  checked against the 2026-09-23 spine, the code and the record.
