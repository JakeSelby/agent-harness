---
title: Agent Harness developer experience contract
status: final
created: 2026-09-19
updated: 2026-09-19
sources:
  - DESIGN.md
  - ../../prds/prd-agent-harness-2026-09-19/prd.md
---

# Foundation

The primary surface is a local CLI supported by public documentation. Native clients consume the
resulting projections but remain independently authoritative for permissions and behavior. Visual
presentation follows `DESIGN.md`; operational truth comes from CLI state and evidence records.

# Information architecture

1. **Understand:** README states the concrete value and current support boundary.
2. **Select:** configuration names the runtimes, editor surfaces and stance variants the user wants.
3. **Preview:** dry run lists every link, rendered file, setting and conflict before ownership changes.
4. **Apply:** sync records what the harness owns and preserves unrelated state.
5. **Inspect:** doctor and stance output separate resolved policy, projection and native qualification.
6. **Recover:** repeat sync, drift repair and uninstall explain preserved conflicts and prior values.

# Key flows

## Riley evaluates the harness without surrendering configuration

Riley already uses Claude Code and Codex. They clone the repository, select those two runtimes, keep
editor management disabled, and run a dry sync. The key confirmation is the preview: Riley can see exactly what
would be linked or changed and stop on an unmanaged conflict. After applying, doctor reports local
activation separately from published support.

## Morgan changes one preference across both runtimes

Morgan changes the delegation stance, inspects the resolved stance output, previews the two adapter
projections and syncs. The key confirmation is seeing one authored choice reach both native formats while the
compatibility output still states which behavior has actually been observed on each client.

## Casey contributes a fix

Casey starts from a GitHub issue with a linked BMad story, works in a managed worktree, runs the exact
gate and opens one PR that closes the delivery issue. The key confirmation is a reviewer following the issue,
story, diff and evidence without needing a private transcript.

# Voice and tone

Use short, literal status language. Say supported, preview, planned, unsupported, unknown or failed;
never collapse unknown into absent or generated into verified. Error messages state what was protected
and the next safe inspection command.

# Component patterns

- Preview output groups proposed actions by runtime and ownership target.
- Conflict output identifies the current owner and never recommends adoption as the default.
- Compatibility output names runtime, client, OS, version and evidence state together.
- Planning links use stable BMad IDs while GitHub remains the delivery authority.

# State patterns

Operations expose proposed, applied, unchanged, conflicted, skipped and failed states. Evidence adds
passed, failed, unverified and superseded. Per-item failures are counted separately from empty results.

# Interaction primitives

Commands are explicit and composable. Mutating operations have dry-run equivalents where practical.
Repeated application is safe. Approval, verification and task-state handoff never transfer implicitly.

# Accessibility floor

All meaning is present in text, command examples remain copyable, headings are navigable, and output
works without animation or pointer interaction. Future graphical surfaces must retain keyboard and
screen-reader access to every operational action and status.
