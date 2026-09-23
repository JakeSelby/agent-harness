---
bmad_id: "AH-SP005"
type: "spike"
title: "Jev: Evaluate deletion-only compaction against task success"
lifecycle: "active"
provenance: "authored"
github_issue: 373
github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/373"
parent_bmad_id: "AH-E003"
parent_github_issue: 135
updated: "2026-09-23"
---

# AH-SP005 — Jev: Evaluate deletion-only compaction against task success

<!-- bmad-sync:begin -->
- **GitHub issue:** [#373](https://github.com/JakeSelby/agent-harness/issues/373)
- **Primary parent:** [AH-E003](https://github.com/JakeSelby/agent-harness/issues/135)
- **State:** active

The issue carries the summary, discussion and acceptance evidence; this file carries the design.

This work item was authored as part of the repository's committed BMad planning system.
<!-- bmad-sync:end -->

## Question

Does deletion-only compaction, with each tool call and result scored by a decision provider for
relevance to the task still open, preserve task success while cutting context? The decision waiting on
it is whether the harness offers provider-scored compaction on Claude Code's compaction hook, or the
spike closes negative.
[Source: https://github.com/JakeSelby/agent-harness/issues/373]

## Experiment

- **Mechanism:** on Claude Code's compaction hook, score each tool call and result for relevance to the
  open task, then keep verbatim, truncate or drop. Never summarise or rewrite, so the filter cannot
  fabricate.
- **Two departures from the public plugins,** both forced by their open defects:
  - score a result from a bounded head and tail of its content, because scoring a length stub drops
    results that are needed again;
  - drop a call together with the narration that depends on it, so no summary of tool-free work
    survives.
- **Protocol:** run the replay benchmark's tasks to a midpoint, compact, finish, and compare against
  uncompacted runs of the same tasks.
- **Measured:** task pass rate and context tokens, compacted against uncompacted.

## Exit criterion

Both must hold, fixed in the issue before the run:
1. Task pass rate equal to the uncompacted arm, at n ≥ 8 tasks.
2. At least 40% fewer context tokens.

Otherwise the spike closes negative and says so.

## Result

Not yet run. Blocked by #136 and #137 (merged) and #369, the first live replay results (open).

## Decision

Open: the replay comparison against the exit criterion decides it. A pass opens a story to ship the
compaction filter on Claude Code; a miss closes the spike negative.

## Dev notes

- Claude Code only: Codex has no equivalent hook, and the issue asks for that gap to be recorded in the Codex capabilities file.
- Separate from ingest-time trimming in `policy/hooks/filter-output.py`, which is out of scope.
- Skill shortlists (#143) explicitly leave whole-session compaction to this spike.
- Bound: FR-49 (evidence before any stage), FR-56 (live replay against a bare arm) as the benchmark.
- [Source: https://github.com/JakeSelby/agent-harness/issues/373]
- [Source: https://github.com/JakeSelby/agent-harness/issues/369]

## Change log

- 2026-09-23: written from the issue and pull-request record.
