# Agent Harness BMad corpus

This directory is the public product and delivery record. Start with the
[product brief](planning-artifacts/product-briefs/brief-agent-harness-2026-09-19/brief.md), then read
the [requirements](planning-artifacts/prds/prd-agent-harness-2026-09-19/prd.md),
[developer experience](planning-artifacts/ux-designs/ux-agent-harness-2026-09-19/EXPERIENCE.md),
and [architecture spine](planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-19/ARCHITECTURE-SPINE.md).
The [epic map](planning-artifacts/epics.md) owns program coverage, the
[decision ledger](planning-artifacts/decisions.md) preserves product calls, and the
[readiness report](planning-artifacts/implementation-readiness.md) states what remains before v1.
The [v1 release plan](planning-artifacts/v1-release-plan.md) is the approved gate sequence and ends
with the authoritative story-to-requirement mapping.

Hidden `.memlog.md` files are BMad's append-only decision history for safely updating their sibling
artifacts; the rendered documents remain the human-facing authorities. The
[source ledger](planning-artifacts/source-ledger.md) explains provenance and publication exclusions.
The machine-readable [`issue-map.json`](issue-map.json) links every GitHub issue to its immutable-ID
artifact under [`implementation-artifacts/`](implementation-artifacts/).

Repository-owned customizations and deliberately published artifacts are committed. Installed BMad
runtime files, generated agent skills, caches, raw conversations, private paths and machine-local
state are not. The complete boundary and reinstall procedure live in [`docs/bmad.md`](../docs/bmad.md).
