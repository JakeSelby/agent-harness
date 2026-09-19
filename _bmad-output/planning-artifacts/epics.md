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

- **Defensible v1.0.0 ([#206](https://github.com/JakeSelby/agent-harness/issues/206), AH-E005):**
  stable CLI support on macOS and Linux, lifecycle proof, public SemVer and deprecation policy,
  immutable release surfaces and independent audit. The five release stories and their requirement
  coverage are defined in `v1-release-plan.md` and tracked by the v1.0.0 milestone.

## Post-v1 programs

- **Client graduation ([#216](https://github.com/JakeSelby/agent-harness/issues/216), AH-E007):**
  editor and desktop clients earn stable status only through independent evidence and support gates.
- **Adoption and feedback ([#212](https://github.com/JakeSelby/agent-harness/issues/212), AH-E006):**
  publish a two-runtime proof, run a direct tester cohort, fix onboarding friction, then stage broader
  launch channels and measure usable attempts, repeat use and actionable feedback.

## Coverage rule

Every implementation story must cite the FR, NFR, architecture decision or explicit maintenance
obligation it serves. A relationship to an epic is not delivery ownership; each PR still closes one
dedicated issue.
