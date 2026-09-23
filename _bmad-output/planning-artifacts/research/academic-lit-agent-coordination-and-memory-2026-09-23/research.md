---
title: 'academic-lit research: coordination and memory for parallel coding agents'
type: 'academic-lit'
topic: 'coordination and memory for parallel coding agents'
decision: 'Which coordination and memory mechanisms the harness adopts for parallel agents, and which it defers: declared path reservations with overlap warnings, a cross-runtime session archive, retrieval over past sessions.'
source: 'process: maintainer notes (unpublished) 2026-09-22; GitHub issues #541-#546; in-repo spine, PRD, epics, builder role, delegation rule, telemetry doc at 3020251; 6 arXiv preprints and 3 project pages fetched 2026-09-23'
status: complete
preset: 'normal'
validation: 'normal'
created: '2026-09-23'
updated: '2026-09-23'
claims_verified: 19
claims_unverified: 3
claims_disputed: 1
claims_overturned: 0
issue: 617
---

# academic-lit research: coordination and memory for parallel coding agents

**Decision this research serves:** which coordination and memory mechanisms the harness adopts for
parallel agents, and which it defers.

## Executive summary

**Adopt path reservations (#542) now. Build the session archive (#543) once the #541 spike picks
its row. Keep semantic retrieval deferred (#546). Keep pull-only recall (#544) behind the archive
and a measured arm.**

- **Conflicts are real, and measured fixes use shared state rather than chat.** Pull requests from
  different agents conflict 41.7% of the time, against 19.8% for pairs from the same agent [1].
  Write-time detection over a shared workspace beats a worktree baseline [4]. Advisory conflict
  notices raise pass rate at lower cost [5]. None of these mechanisms is peer messaging [6].
- **Memory systems mostly fail to beat no memory, but repository history has real value.** 11 of
  12 solver and memory-system pairings failed to beat memory-off [8]. Yet injecting the right
  experience directly helped [9]. What fails is delivery, not history.
- **The archive rests on runtime facts rather than literature.** The Claude session schema carries
  no stability promise [12], and transcripts expire or compress [13].

**Biggest caveat:** every empirical source is a single-lab preprint. None tests path-level claims,
which are coarser than what STORM [4] or CoAgent [5] built.

## 1. Conflict and coordination failure rates

- Pull-request pairs from different agents hit textual conflicts 41.7% of the time, against 19.8%
  for pairs from the same agent. The sample is 33,596 PRs, and the confidence intervals do not
  overlap [1]. The study is observational and proposes no fix [3]. It measures agents on GitHub,
  not sibling builders in one repository, so it gives direction and does not predict this
  repository's rate.
- About 42% of conflicts were structural, meaning modify/delete or add/add [2]. The builder's
  "prefer a new file" rule [22] prevents neither kind unless new paths are claimed too.
- STORM mediates every workspace interaction and resolves conflicts at write time. It scores +18.7
  over a git-worktree baseline on Commit0-Lite, but only +1.4 on PaperBench [4], so the gain
  depends on the task.
- In CoAgent, the runtime informs and the agent repairs. Pass rate rises from 45/71 to 63/71, at
  0.86x the cost [5]. The same paper argues that locks block long inference intervals [5].

## 2. Peer messaging against declared reservations

- None of the sources read compares peer chat with shared-state coordination. Every measured win
  mediates shared state [6], but this is an absence claim that was not independently searched
  (unverified).
- The note reports three costs of messaging: each message bills as a turn, loops need rate limits,
  and teams cannot resume [7]. These come from vendor documentation that was not fetched this run
  (unverified).
- #542 already follows the advisory-first shape: warn on the first overlap and deny on the second.
  Every hit is logged as an `intent-overlap` decision row, and merge conflicts are counted.
  Codex falls back to a pre-commit check [16].

## 3. Memory and retrieval against a no-memory baseline

- VibeMemBench (September 2026): 11 of 12 solver and memory-system pairings fail to exceed the
  matched memory-off baseline [8]. The unit is pairings, not memory systems, so the brief's
  paraphrase is inexact. Direct injection added 1.1 to 4.5 pp on four of five solvers and cut
  steps on all five [9].
- CTIM-Rover's episodic memory never beat its baseline, and the authors blame noise [10]. The
  paper is older than the six-month machine-learning freshness bar (low confidence).
- Monitors missed dangerous actions 2x to 30x more often after 800K benign tokens [11]. That was
  measured on classifier monitors, and applies to injected coding context only by analogy.

## 4. Session archive and full-text search

- The request for a stable Claude session JSONL schema was closed as not planned [12]. Claude
  transcripts expire at 30 days, and Codex rollouts are zstd-compressed after 7 days, beyond the
  reach of the Python 3.9 standard library [13]. Parsing each transcript once and keeping the row
  applies the ledger principle [23].
- agent-session-format is MIT-licensed TypeScript/Zod. It keeps tool-call ids, subagent labels and
  tokens, and names no compaction marker [14]. Under NFR2 it cannot be a runtime dependency, but
  its schema can be borrowed.
- agentsview already archives sessions in SQLite with FTS5 [15]. The agent count is disputed,
  and its upstream repository and licence were not confirmed.

## 5. When retrieval-augmented memory would pay off

The #546 reopen criterion requires all of the following [17]:

1. the archive has been live for four weeks;
2. at least 20% of logged queries found nothing useful through FTS, but a person found the answer
   by paraphrase;
3. a pull-based retrieval arm beats no-retrieval on normalised cost or pass rate;
4. a written note explains why the existing semantic memory service cannot answer the query.

The evidence supports this criterion [8][9][10].

## Cross-dimension insights

- **Both halves of the evidence point the same way.** Structured state delivered at the right
  moment pays: at write time [4][5], or as directly injected experience [9]. Generic channels and
  generic retrieval do not [6][8].
- **No story owns the #546 criterion.** It depends on a log of `harness sessions search` queries
  carrying a "useful?" signal [17], and neither #543 nor #544 lists that log among its
  acceptance criteria [18][19].

## Contrary evidence

The red-team pass was off. The strongest counters found:

- History does help when it is delivered directly [9].
- CoAgent argues against blocking [5], which bears on #542's deny on the second overlap.

## Recommendations

1. **Adopt #542, warn-first. Claims cover planned new paths as well as edited ones** [2][16].
   - Architecture spine: add a coordination invariant under AD-2 [20]. Parallel writers declare
     ownership, agents coordinate through shared state rather than by messaging each other, and
     every overlap is logged. The choice between warn and deny may be a policy variant; the
     invariant may not.
   - PRD: add an FR for coordinating parallel writers. None exists, and epic #116 covers no such
     requirement [21].
   - FR3 requires naming the Codex gap [21].
   - Confidence is medium: the evidence comes from single-lab preprints, and none of them tests
     path-level claims.
2. **Build #543 after #541 [19]: borrow a row shape, and add no TypeScript dependency** [14].
   - Bind it to FR11 (local, no remote), NFR2, NFR3 (the bodies switch) and FR8 (the archive is
     non-authoritative) [21].
   - Add a query log with a usefulness signal to #543 or #544, so #546 can ever reopen.
   - Confidence is high on the need [12][13] and low on which tool to adopt [15].
3. **Keep #546 deferred and #544 pull-only** [8][10][11][18].
   - Add "push-injected memory" to the PRD's explicit non-goals, beside native memory merging
     [20][21].
   - Add steps to #546's measured arm [9].
   - Confidence is medium.
4. **Do not adopt peer messaging for coordination** [6][7]. The evidence is thin (unverified); the
   decision rests on the absence of any measured benefit.

## Open questions

1. Does path-level claiming recover any of STORM's gain [4]? Record this repository's conflict
   rate before enabling #542 and compare after.
2. Does denying on the second overlap stall builders [5]? Count denials against abandoned turns in
   the decision rows.
3. Has anyone compared peer chat with shared state [6]? That needs a targeted literature search.
4. What are agentsview's upstream repository, licence and schema [15]? Settle them in the #541
   spike.
5. Does agent-session-format preserve compaction markers [14]? Settle this in the #541 spike.

## Source appendix

| [n] | Claim/finding it supports | Publisher | Pub date | Accessed | Confidence |
| --- | --- | --- | --- | --- | --- |
| [1] | 41.7% vs 19.8% cross- vs intra-agent conflict rate, 33,596 PRs | [arXiv 2607.04697 (preprint)](https://arxiv.org/abs/2607.04697) | 2026-07-06 | 2026-09-23 | medium |
| [2] | ~42% structural conflicts; 84.4% source files | [arXiv 2607.04697 (preprint)](https://arxiv.org/abs/2607.04697) | 2026-07-06 | 2026-09-23 | medium |
| [3] | Study is observational, proposes no mechanism | [arXiv 2607.04697 (preprint)](https://arxiv.org/abs/2607.04697) | 2026-07-06 | 2026-09-23 | high |
| [4] | STORM write-time detection, +18.7 Commit0-Lite, +1.4 PaperBench | [arXiv 2605.20563 (preprint)](https://arxiv.org/abs/2605.20563) | 2026-05-19 | 2026-09-23 | medium |
| [5] | CoAgent advisory control, 45/71 to 63/71 at 0.86x cost; locks block | [arXiv 2606.15376 (preprint)](https://arxiv.org/abs/2606.15376) | 2026-06-13 | 2026-09-23 | medium |
| [6] | No source compares peer chat with shared state (unverified) | maintainer notes (unpublished) | 2026-09-22 | 2026-09-23 | low |
| [7] | Messaging billed per turn, needs rate limits, teams cannot resume (unverified) | maintainer notes (unpublished) | 2026-09-22 | 2026-09-23 | low |
| [8] | 11 of 12 solver x memory-system pairings fail to beat memory-off | [arXiv 2609.23570 (preprint)](https://arxiv.org/abs/2609.23570) | 2026-09-20 | 2026-09-23 | medium |
| [9] | Direct injection +1.1 to 4.5 pp, fewer steps | [arXiv 2609.23570 (preprint)](https://arxiv.org/abs/2609.23570) | 2026-09-20 | 2026-09-23 | medium |
| [10] | Episodic memory never beat baseline; noise | [arXiv 2505.23422 (preprint, REALM '25)](https://arxiv.org/abs/2505.23422) | 2025-05-29 | 2026-09-23 | low |
| [11] | Monitors miss dangerous actions 2x to 30x after 800K benign tokens | [arXiv 2605.12366 (preprint)](https://arxiv.org/abs/2605.12366) | 2026-05-12 | 2026-09-23 | medium |
| [12] | Claude session JSONL schema request closed not planned | [anthropics/claude-code#53516](https://github.com/anthropics/claude-code/issues/53516) | 2026-04-26 | 2026-09-23 | high |
| [13] | Transcript expiry, Codex zstd, 10 of 130 sessions transcript-less (unverified) | [agent-harness #541](https://github.com/JakeSelby/agent-harness/issues/541) | 2026-09-22 | 2026-09-23 | medium |
| [14] | agent-session-format: TypeScript/Zod, MIT, fields kept | [agent-session-format](https://github.com/Atituiset/agent-session-format) | 2026-09-23 | 2026-09-23 | medium |
| [15] | agentsview SQLite+FTS5 archive; agent count disputed | [agentsview fork listing](https://github.com/arandomhooman/agentsview) | 2026-09-23 | 2026-09-23 | low |
| [16] | #542 claim, warn, deny, log and Codex fallback design | [agent-harness #542](https://github.com/JakeSelby/agent-harness/issues/542) | 2026-09-22 | 2026-09-23 | high |
| [17] | #546 reopen criterion | [agent-harness #546](https://github.com/JakeSelby/agent-harness/issues/546) | 2026-09-22 | 2026-09-23 | high |
| [18] | #544 pull-only, pointers, never injected, blocked by #543 and #369 | [agent-harness #544](https://github.com/JakeSelby/agent-harness/issues/544) | 2026-09-22 | 2026-09-23 | high |
| [19] | #543 archive scope; #541 exit criterion | [agent-harness #543](https://github.com/JakeSelby/agent-harness/issues/543) | 2026-09-22 | 2026-09-23 | high |
| [20] | Spine: AD-2 invariants, no coordination decision, memory merging deferred | [ARCHITECTURE-SPINE.md @3020251](../../architecture-spines/architecture-agent-harness-2026-09-19/ARCHITECTURE-SPINE.md) | 2026-09-19 | 2026-09-23 | high |
| [21] | PRD FR3, FR8, FR11, NFR2, NFR3; no coordination FR; #116 coverage | [prd.md @3020251](../../prds/prd-agent-harness-2026-09-19/prd.md) | 2026-09-19 | 2026-09-23 | high |
| [22] | Builder assumes a sibling, prefers new files; writes single-threaded | [builder.md @3020251](../../../../primitives/roles/builder.md) | 2026-09-23 | 2026-09-23 | high |
| [23] | The ledger is the record; a backend is a rebuildable copy | [telemetry.md @3020251](../../../../docs/telemetry.md) | 2026-09-23 | 2026-09-23 | high |

## Staleness map

Built with `recon_kit.py staleness`. The windows are 6 months for empirical-ml, runtime-behaviour
and tool-landscape claims, and 12 months for the project record.

- Already stale: [10] CTIM-Rover, re-check due 2025-11-29.
- Due 2026-10-26: [12] Claude schema status.
- Due 2026-11-12: [11].
- Due 2026-11-19: [4].
- Due 2026-12-13: [5].
- Due 2027-01-06: [1] to [3].
- Due in March 2027: [8], [9], [13], [14], [15].
- Due 2027-09-22: the project record, [16] to [23].

The earliest live re-check is [12], on 2026-10-26.
