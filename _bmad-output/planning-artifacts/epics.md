---
title: Agent Harness epics
status: active
created: 2026-09-19
updated: 2026-09-19
inputDocuments:
  - prds/prd-agent-harness-2026-09-19/prd.md
  - architecture-spines/architecture-agent-harness-2026-09-19/ARCHITECTURE-SPINE.md
  - ux-designs/ux-agent-harness-2026-09-19/DESIGN.md
  - ux-designs/ux-agent-harness-2026-09-19/EXPERIENCE.md
---

# Epic map

## Existing programs

- **Provider-agnostic harness (#93):** shared primitives, native adapters, lifecycle safety,
  qualification, positioning and coordinated release. Covers FR1–FR8 and FR10–FR12.
- **Complete stance and settings contract (#116):** make declared switches effective at every policy
  layer while preserving invariants. Covers FR2, FR3, FR6, FR10 and NFR3.
- **Optional semantic decision layer (#135):** bounded opt-in judgments that remain subordinate to
  deterministic checks. This is post-v1 and does not expand the stable support floor.
- **Commit public BMad planning (#189):** public corpus, stable IDs, GitHub migration and v1 planning.
  Covers FR9 and the auditability portions of NFR5 and NFR7.

## Release program

- **Defensible v1.0.0:** stable CLI support on macOS and Linux, lifecycle proof, public SemVer and
  deprecation policy, immutable release surfaces and independent audit. Detailed story mapping is
  maintained with issue #193 after the GitHub traceability migration.

## Post-v1 programs

- **Client graduation:** Claude Code VS Code, Codex VS Code and Codex desktop earn stable status only
  through their own complete native evidence.
- **Adoption and feedback:** publish one real preference-to-two-runtimes demo and release note;
  recruit a small direct tester cohort; fix observed onboarding friction; then stage community and
  broader launch posts. Measure usable attempts, repeat use and actionable feedback.

## Coverage rule

Every implementation story must cite the FR, NFR, architecture decision or explicit maintenance
obligation it serves. A relationship to an epic is not delivery ownership; each PR still closes one
dedicated issue.
