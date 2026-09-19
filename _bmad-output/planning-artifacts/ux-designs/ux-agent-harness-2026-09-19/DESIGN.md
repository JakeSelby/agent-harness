---
title: Agent Harness design contract
status: final
created: 2026-09-19
updated: 2026-09-19
colors:
  status: semantic-names-not-fixed-terminal-colors
typography:
  prose: system-sans
  code: system-monospace
rounded: none-required
spacing: compact-readable
components:
  - status-line
  - command-block
  - evidence-callout
sources:
  - ../../prds/prd-agent-harness-2026-09-19/prd.md
---

# Brand and style

Agent Harness is direct, inspectable and calm. Documentation leads with what a developer can do,
then states current limits without promotional inflation. The product has no required graphical
surface for v1; this contract governs documentation, terminal examples and future explanatory UI.

# Colors

Status meaning must not depend on color. Any future surface uses named semantic states—supported,
preview, planned, unsupported, unknown and failed—and renders their text labels visibly.

# Typography

Use the host system's readable sans-serif for prose and monospace for commands, paths and structured
output. Avoid decorative display typography in operational surfaces.

# Layout and spacing

Put the outcome and next safe action first. Keep commands copyable and keep caveats adjacent to the
claim they limit. Dense evidence belongs behind a link, not above the first experiment.

# Components

- **Status line:** literal state plus subject and evidence scope.
- **Command block:** complete executable command with no hidden prerequisite.
- **Evidence callout:** observed behavior, exact surface and limitations.

# Dos and don'ts

Do distinguish generated configuration, implemented policy and observed native behavior. Do not use
visual polish to imply qualification, savings or capability that has not been measured.
