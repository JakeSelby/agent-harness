---
title: Agent Harness decision ledger
status: superseded
created: 2026-09-19
updated: 2026-09-19
superseded_by:
  - architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md
  - prds/prd-agent-harness-2026-09-23/addendum.md
---

# Decision ledger

This is an append-only summary of product decisions recovered from current repository authority and
the source ledger. Architecture decisions retain their detailed rules in the architecture spine.

## 2026-09-19

- BMad planning artifacts and project-specific customizations are public and live in this repository;
  generated runtime and skill projections remain ignored and reproducible.
- GitHub is authoritative for delivery state. Beads-compatible types are represented with labels and
  stable BMad IDs; Beads is not installed.
- Native GitHub issue types are organization-managed and unavailable in this personal-account
  repository. Exact `type::*` labels are authoritative for type; native sub-issues represent hierarchy.
- BMad IDs are global typed sequences and do not encode hierarchy. Reparenting never changes an ID.
- Existing open and closed issues are migrated in place. Historical artifacts are explicitly marked
  reconstructed, and original issue prose, state and comments are preserved.
- The v1 stable floor is Claude Code CLI and Codex CLI on macOS and Linux. VS Code and Codex desktop
  remain preview and do not block v1.
- External developer feedback is useful but not a prerequisite for a defensible v1 release; internal
  lifecycle proof, native evidence, policy and independent review are required.
- Adoption follows release: a real short demo, direct tester loop, friction fixes, staged community
  posts and repeat-use/actionable-feedback measures. Promotion-channel rules are rechecked at launch.
