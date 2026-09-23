---
bmad_id: "AH-SP007"
type: "spike"
title: "Does the Claude Code Workflow tool bypass band routing, confinement and the ledger?"
lifecycle: "completed"
provenance: "authored"
github_issue: 540
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/540"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP007 — Does the Claude Code Workflow tool bypass band routing, confinement and the ledger?

<!-- bmad-sync:begin -->
- **GitHub issue:** [#540](https://github.com/JakeSelby/agent-harness/issues/540)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** completed

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This work item was authored as part of the repository's committed BMad planning system.
<!-- bmad-sync:end -->

## Question

Does the Claude Code Workflow tool bypass the harness? Three sub-questions:
1. Does `tier-agent-spawns` fire on a script's `agent()` calls?
2. Can a script invoke `harness role run` for a confined role?
3. Does `usage-log` attribute a script's agents to the parent session?

Why it mattered: the Workflow tool ships natively and any user can run one. If band routing,
brief-guard and the ledger do not see its spawns, a script is a way around the delegation stance whether
or not the harness adopts scripts. #520 asks the same question of the tier restriction per
runtime; this is the Workflow-shaped instance.
[Source: https://github.com/JakeSelby/agent-harness/issues/540]

## Experiment

One minimal project workflow script with `agent()` calls in one phase, run headless: one unnamed call,
one whose brief declares a constrained role, and one naming the constrained role through `agentType`.
Three further runs probed the runtime's reach: an agent asked to run `echo`, one asked to run a
destructive command against a scratch directory, and one asked to spawn a nested subagent. The record
compares what the hooks saw (`decisions.jsonl`), what the ledger recorded (`usage.jsonl`), and whether
the confined-role spawn was refused as it is through the `Agent` tool. Four headless runs in total, on
Claude Code 2.1.280 with harness 0.12.0.
[Source: docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md#Experiment]

## Exit criterion

A yes or no per sub-question, with the ledger and decision rows as evidence; the issue sets no numeric
threshold. Any "no" becomes a bug against the coordinator or a gap in the capabilities file, filed from
the spike.

## Result

Partially bypassed, measured 2026-09-22.
1. **No.** A script's `agent()` calls produce no `Agent` tool call, so `tier-agent-spawns`,
   `brief-guard` and the constrained-role refusal never run; `decisions.jsonl` held zero rows for the
   probe session, and no hook matcher matches the `Workflow` launch. The script sets model, effort and
   `agentType` directly.
2. **No, and it does not need to.** The script body has no filesystem or shell access and refuses
   `import()`, so it cannot call `harness role run`; naming the role in `agentType` runs it in session,
   unconfined, on that definition's model.
3. **Yes. Not bypassed.** `usage-log.py` records every workflow agent as a subagent row tagged with
   the workflow id. Those rows carry no `tool_use_id`, however, so the reroute join is empty and
   compliance cannot be measured from them.

Fan-out is one level deep: the built-in workflow subagent disallows the `Agent` tool. Untested and said
so in the record: whether `PreToolUse` fires on a workflow agent's own `Bash`. The raw evidence is in
the spike record.
[Source: docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md#Measured result]

## Decision

Two follow-ups filed from the record: #576 guards the `Workflow` launch at `PreToolUse` (log it, honour
delegation off, refuse constrained roles in `agentType`), and #577 separates workflow spend in
`harness usage`. FR-30 now states that the Workflow tool's `agent()` calls bypass routing (#576,
v0.14.0). The finding that a script cannot call `harness role run` bears on #545, whose acceptance
routes confined roles that way.

## Dev notes

- Delivered in #578, merged 2026-09-23: `docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md`
  and `CHANGELOG.md`. Docs only; no code changed.
- The repository had no committed spike convention; the record follows the dated-file style of
  `docs/solutions/` and the spike-contract fields (question, experiment, measured result, machine,
  verdict).
- To repeat: the command and script shape are in the record's Experiment section.
- Bound: FR-30 (band routing), FR-41 (confinement however the spawn is named), FR-23 (usage ledger).
- Model used: not recorded in the pull request. Review findings: none recorded.
- [Source: https://github.com/JakeSelby/agent-harness/pull/578]
- [Source: https://github.com/JakeSelby/agent-harness/issues/576]

## Change log

- 2026-09-23: written from the issue and pull-request record.
- 2026-09-23: corrected after sample review: architecture bindings, current behaviour and history
  checked against the 2026-09-23 spine, the code and the record.
