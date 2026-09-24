---
bmad_id: "AH-SP012"
type: "spike"
title: "Jev: can a self-hosted Laya model serve the decision packs as a local provider?"
lifecycle: "active"
provenance: "authored"
github_issue: 753
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/753"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP012 — Jev: can a self-hosted Laya model serve the decision packs as a local provider?

<!-- bmad-sync:begin -->
- **GitHub issue:** [#753](https://github.com/JakeSelby/agent-harness/issues/753)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** active

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This work item was authored as part of the repository's committed BMad planning system.
<!-- bmad-sync:end -->

## Question

Can the existing stdlib Jev client talk to a self-hosted Laya server within the shadow latency bar,
well enough to justify a fourth decision provider? A local provider would send nothing off the
machine, pin its model by file hash, cost nothing per call, and let the harness publish per-point
figures, which the `jev` provider's terms rule out (FR-49). The decision waiting on it is whether to
file a `laya` provider story before the shadow binding (#140) and the publication rules in #147.

## Experiment

1. Licensing-review of Laya first: the licence of the weights as well as the code, the provenance of
   the training data, and the trademark exposure in "Jev-compatible". It is Apache-2.0 per its
   Hugging Face tags, and a tag is not proof.
2. Run a Laya server on a CPU-only machine and point the client at it.
3. Replay the recorded evaluation fixtures under `tests/fixtures/jev/eval/`, repeated to 200 calls.
4. Record the machine, the model file hash, the server version and every command line.

The recorded `jev` responses supply request shapes only; nothing is scored against them.

## Exit criterion

- Licensing-review passes, with training-data provenance recorded. A fail ends the spike at no-go.
- Wire compatibility: yes, or the exact adapter delta.
- p95 latency under 1 s over 200 calls on the named machine, the bar the shadow binding sets (#140,
  AC2).
- The result is a go or no-go on a `laya` provider story. Agreement waits for the #377 seed labels
  and is scored on them only, never against `jev` output, per the no-distillation non-goal.

## Result

<!-- fill: the measured numbers, where the raw evidence lives, and which side of the threshold they fall. -->

## Decision

<!-- fill: what the result decides, and the follow-up work it opens or closes. -->

## Dev notes

- Out of scope: shipping a provider, and any training.
- Laya's Hugging Face ports, checked 2026-09-23: Core ML, GGUF and ONNX builds, each tagged
  Apache-2.0. keel 0.2.0 ([codejunkie99/keel](https://github.com/codejunkie99/keel)) runs it through Core ML as its default local selector.
- The vendor terms a local model avoids [Source: _bmad-output/planning-artifacts/research/technical-decision-layer-evidence-2026-09-23/research.md#4-ecosystem-constraints].
- The client under test [Source: lib/harness_core/decisions/jev.py].

## Change log

- 2026-09-23: written, per #756.
