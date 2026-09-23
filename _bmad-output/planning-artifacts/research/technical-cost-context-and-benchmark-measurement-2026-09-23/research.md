---
title: 'technical research: cost, context overhead and benchmark measurement'
type: 'technical'
topic: 'cost, context overhead and benchmark measurement'
decision: 'What the harness can truthfully claim about cost and context overhead, which mechanisms actually save tokens, and which success metrics and publish bars the PRD should carry.'
source: 'process'
status: complete
preset: 'standard'
validation: 'normal'
claims_verified: 14
claims_unverified: 7
sources: 32
created: '2026-09-23'
updated: '2026-09-23'
---

# technical research: cost, context overhead and benchmark measurement

**Decision this research serves:** what the harness can truthfully claim about cost and context overhead, which mechanisms actually save tokens, and which success metrics and publish bars the PRD should carry.

**Method.** Headless Process run over the repository's own measurement record at commit `3020251`, sixteen GitHub issues and pull requests, and four unpublished maintainer notes, all read on 2026-09-23. Validation `normal`: the load-bearing figures were spot-checked against a second artifact, and the static figure and lint caps were re-run deterministically with no model call. Every source shares one publisher, so "verified" here means a second artifact or instrument agrees. It does not mean an outside party agrees. No source is copied into `imports/`, which lists sources only.

## Executive summary

**What the evidence says.** The harness can claim a **measured, capped and CI-gated standing context**. It can claim **nothing about saving money**. The one clean live comparison puts the harness at **1.052× bare per passed task** on four tasks. That is about 5% *more* expensive, and it misses the 0.85 publish bar [1]. The PRD should keep that bar fixed. It should add counter-metrics and a minimum sample, and it should require evidence that a mechanism fired before crediting that mechanism with a saving.

**The findings that drive the answer.**

1. **The mechanism the saving was claimed from has never run.** Delegation produced zero subagent spawns in every replay run: 19 by one count, forty by the later one [6][21]. On three of the four tasks a spawn would have paid, because break-even is 4.8 to 5.9 calls and those tasks ran 17 to 45 calls [21].
2. **Trimming cannot reach the bar.** Standing context is about 20% of a run's cost, and trimming can remove about 25% of that [15]. That is roughly 5% of a run, while the gap from 1.052 to 0.85 is about 19%. Only removing work closes the gap: fewer turns, less thrash, delegation. Output tokens are about 20% of spend, so brevity rules are a 2–3% lever against a turn-count swing of about 60% [29].
3. **The first two ratios were contaminated and were rightly discarded.** They were 0.782 and 1.160, one on each side of the bar. A test-suite isolation defect (#498) wrote into the benchmark profiles [16][29], and the benchmarks doc names both figures as artifacts [1].

**The biggest caveat.** The live tier is underpowered. It has 16 scored runs at two reps, with per-task spread up to 1.86× [22]. Even 1.052 is one point estimate, and per-rule effects of 2–3% cannot be resolved at this sample size.

## Standing context overhead

- **Static tier.** The committed figure for 0.12.0 is about 7,494 estimated tokens: 5,168 always-loaded and 2,326 of listings, with a worst case of 7,553 [2]. The estimate is characters divided by four, a trend figure and not a billing figure. CI fails on growth over 5% [1][4][13]. Re-running the count at `3020251` gives about 6,751, roughly 10% under the committed figure, after the #430 trims [4]. The docs' own trim table starts at 7,524, not 7,494, which is a minor inconsistency [1][2].
- **Largest single file.** The output style is the largest file, at about 1,515 tokens, 3.9× the next file [2].
- **Caps.** `harness lint` caps the instructions, rules and longest stance variants at **200 lines and 4,202 tokens**. At `3020251` that layer stands at **199 of 200 lines** and about 3,858 tokens, so **the line cap is the one that binds** [5].
- **Live prefix.** The measured live standing context against a bare profile is **12,607 tokens**, stable to ±15 across eight task pairs, and the token cap is a third of that figure [5]. A later remeasure found 13,640 [29]. Either way the live prefix is **about 1.7–1.8× the static estimate**, so the static figure is a lower bound on what a session pays.
- **What the figures leave out.** Neither figure counts the user's own personal file, memory, MCP servers or hook output. MCP tool definitions alone can outweigh everything measured [1].
- **Price.** At list rates the static layer costs cents per session start and a fraction of a cent per cached turn [2].

## Live replay against bare Claude Code

- **Method** [1][4][14]:
  - Pinned tasks run headlessly, each scored by a held-back check the agent never sees.
  - The two arms differ by environment only, and each arm's sandbox fence is proved by a lint pre-flight before any scored run.
  - Runs start in one-commit snapshots outside the home directory.
  - Cost is the CLI's list-price `total_cost_usd`, reported beside a cache-normalised cost and `cache_miss_ratio`.
  - Errored runs are counted apart from failures.
  - History rows are same-day, same-model ratios to bare. Dollars are never compared across days.
- **Publish bar.** The bar is fixed in code: a ratio of at most 0.85 of bare cost per passed task, and a pass count no lower than bare minus one. A run that passes too few tasks fails however cheap it is [4].
- **Discarded ratios, both *discarded*:**
  - **0.782** came from 24 runs at three reps and was the bare arm's fence thrash.
  - **1.160** came from 16 runs with the harness arm moved to a separate profile.
  - Three follow-up ablations of the personal layer (1.285, 1.738, 1.226) were chasing the same defect [29].
  - The root cause is #498: the test suite's sync tests wrote into whatever profile `CLAUDE_CONFIG_DIR` named, so every benchmark-profile arm had to pass a gate it structurally could not pass [16].
- **The one clean result (*measured*, 2026-09-22).** 16 runs (four tasks × two arms × two reps), no errors, both pre-flights passed:
  - **1.052**, or 1.044 cache-normalised, which fails the bar [1].
  - Per task: link-alias 0.859, codex-pre-allow 1.166, hook-ids 1.197, hook-inventory 1.417 [29].
  - The 0.859 flatters the harness, because the bare arm's thrash on that task still traced to #498.
  - Two harness cells were bimodal at n=2 (6 vs 25 calls, and 10 vs 52 calls) [29].
- **Per-tag replay (#599/#609), *held*.** `--tag` is now repeatable. Each ref is synced into an isolated signed-in profile, and the sync is removed afterwards using its own manifest [24][25]. No per-tag result exists yet.
- **Scope drift.** The manifest now holds **eight** tasks: six issue-derived, two synthetic, one leak-class control. The docs still describe a four-task schedule, no `history.jsonl` is committed, and the eight-task set of 48 runs is held [3][29].

## Mechanisms measured

- **Delegation — *measured, never fired*.** No `Agent` calls were made in either arm [6][15][21].
  - On `hook-inventory` the harness read all 18 files itself, in 10 calls against bare's 11 [6]. That task runs about 6 calls, which is below break-even, so it cannot show delegation paying. That is a manifest defect [29].
  - The spawn hook fires only once a spawn is attempted, so it cannot prompt one. #513 proposes a PostToolUse nudge instead [21].
  - #429 is still open [15].
- **Soft budgets in briefs — *measured, observational*.** Once #254 put an expected spend into every brief, over-budget runs fell from 21.7% of 235 reconstructed runs to 2.2% of 89 budgeted runs, and the median run finished at 0.17 of its budget. This was on one machine with no control arm [11][27][26].
- **In-run budget nudge — *failed* (2026-09-22, n=89 recorded and 235 reconstructed).** The nudge would fire on 2.2% of runs against a pre-registered bar of 10%, and would address 4.5% of subagent output against a bar of 10%. In the larger sample the median overrunning run had one tool call left, so most nudges would arrive too late. Do not build [11].
- **Cache hit rate — *measured, flat*.** Across 137 sessions on one machine, the hit rate was 97.0–97.3% in every subagent-count band. The expected fall with fan-out did not show [7].
- **Brief cap hook — *measured, metric did not move*.** The brief-without-cap rate read 3.2, 3.6 and 3.2 per 100 turns before, during and after the hook, because the ledger reads the brief as the model wrote it, before the hook edits it. The metric was renamed [6][28].
- **Brevity against turn count — *measured share, lever estimated*.** Output tokens are 19.6–22.9% of spend across four arm-sets, so brevity is a 2–3% lever [29]. The output-style on/off A/B was planned and never run.
- **Deferred rule text — *held*.** A spike is framed but not run. It would move about 1,253 tokens, 36% of the rules-and-stances layer, behind hooks. It needs a measured live-prefix fall of at least 700 tokens and compliance no worse than the resident arm minus one [12].
- **Workflow-tool spawns — *measured, version-bound*.** On CLI 2.1.280, Workflow agents bypass band routing and the brief guard. Their ledger rows cannot be joined for reroute measurement [23].
- **Not evidenced in this source set:**
  - the cost-posture routing shift
  - tool-output compression raising cost
  - release-round cost
  - the output-archive result: the permitted spike folder holds only scripts and no recorded figure [31]

  See Open questions.

## Evaluation method

- **Tiered pyramid (#509–#514, all open)** [17][18][19][20][22][32]:
  - Per-file static pricing, with per-file CI deltas.
  - Offline detector replay over stored transcripts.
  - A deterministic matrix of hook × stance-variant decisions.
  - A micro-task tier on a cheap model that reports whether a mechanism fired, kept in a separate series. Its target is under 2 USD and 15 minutes per set.
  - Production-model probes, and then the full live set as a per-release calibration.
- **Model-invariant and model-bound questions.** Hook decisions, detector hits, skill triggering and prefix cost are model-invariant and can be answered at the cheap tiers. Strategy, delegation judgment and thrash are model-bound [32].
- **Per-rule regression is structurally blocked** [22][30]:
  - The runner has two hard-coded arms.
  - Nothing enumerates the rule surface, and no row records which rule an ablation removed.
  - `cost_per_passed` folds cost and pass rate into one number.
  - The first-call prefix field is warmth-contaminated: 45,847 vs 27,977 tokens on one profile.
  - With 23,328 stance permutations, the unit has to be per-rule plus pairwise checks, not the full grid [32].
- **Detector validity.** All 17 detectors are measured against a synthetic labelled corpus with a 0.9 floor, and two sit at p=0.83. Per-variant rates are observational [6].
- **Standalone report.** The report runs from one local ledger without the rest of the harness [9].

## Cross-dimension insights

- **The bar is a work-removal bar, not a context bar.** Prefix share (about 20%) times the trim ceiling (about 25%) is about 5% of a run [15]. The only measured wins are strategic. Hook-ids rep 1 used one inline script and made 10 calls where bare made 55 [29], and that is the capability delegation was supposed to supply [6]. The PRD should put its cost target on turns and thrash, and put context under a cap rather than a target.
- **The instrument's credibility asset is its own failures.** Every negative here was caught by an instrument and recorded before anyone was asked to believe a positive: the discarded ratios, delegation never firing, the flat brief metric, the failed nudge [1][6][11]. This is the claim the brief can safely make.
- **The static tier is the only tier that can gate a pull request today.** It is deterministic, zero-cost and capped [4][5]. The live tier cannot resolve per-change effects [22].

## Contrary evidence

The red-team pass was off, so this section is omitted. The strongest counter-signal to "no saving" is the per-task split: the harness beat bare on link-alias (0.859), and hook-ids rep 1 ran 10 calls against 55 [29]. Both are n≤2, and the first is flattered by residual contamination.

## Recommendations

**PRD: success metrics, counter-metrics and publish bars**

1. Keep the headline metric and bar unchanged: cost per passed task as a same-day, same-model ratio to bare, at most 0.85, with passes no fewer than bare minus one [4]. *High confidence (fixed in code).*
2. Add a minimum sample before any publication: the eight-task set at three or more reps, a stated minimum detectable effect, and per-task figures published beside the headline, both halves included [3][22][30]. *Medium confidence (the power argument rests on one spread figure).*
3. Counter-metrics to report on every row: pass rate, turns and tool calls, `cache_miss_ratio`, errored-run count, and the unpriced-row count [1][7]. *High confidence.*
4. Add a mechanism-fired metric, such as spawns per run on above-break-even tasks. No saving is credited to a mechanism unless the rows show it fired [6][21]. *High confidence.*
5. Standing-context metrics: the static estimate per version, gated at 5% growth; the lint caps of 200 lines and 4,202 tokens; and a live prefix measured from paired transcripts, reported separately as the truer figure [1][5]. *High confidence.*
6. Spikes and mechanism changes carry a numeric exit criterion written before the run, and the criterion is never adjusted afterwards [10][11]. *High confidence.*

**Architecture spine: measurement invariants**

1. Compare ratios across days and never dollars. All dollars are list-price equivalents and not invoices [1][7].
2. Arms differ by environment only. Each fence is proved before scoring. Snapshots sit outside the home directory. No tagged sync may touch the live profile, which is the class of failure #498 produced [1][16][24].
3. Unknown and unpriced figures are never recorded as zero, and an errored run is never counted as a failure [1][7].
4. A session row is never summed with its subagent rows. A subagent's cost comes from its own transcript, not from the tool response, which undercounts: 3,143 vs 10,575 output tokens [7][8].
5. Micro-tier and cheap-model rows never enter the production series [20].
6. Every row records its arm's provenance. Ablations are declared in a manifest, not made by hand [22][30].

**Brief: claims the brief may make**

- *May claim:* standing context is measured, capped and gated. It is about 7,000 estimated tokens static and about 12,600 live [2][5].
- *May claim:* a bare-comparison benchmark with a pre-registered publish bar, and an instrument that has caught the harness's own non-working mechanisms [1][6].
- *May claim, hedged:* budgets in briefs coincided with fewer overruns on one machine [11].
- *May not claim:* any cost saving, that delegation saves tokens, or any effect from compression, routing or cache. The honest current figure is about 5% dearer than bare on four tasks [1].

## Open questions

1. **Cost-posture routing shift, tool-output compression, release-round cost.** No figure for any of these exists in the permitted sources. To answer: a follow-up Process run over the evidence that recorded them.
2. **Output-archive premise.** Only the spike's scripts were available [31]. To answer: process the recorded result.
3. **Does delegation fire above break-even?** To answer: the #513 nudge plus a micro-task, then one production-model pair [21].
4. **Does 1.052 hold on the eight-task set at three reps?** To answer: run the held 48-run set once #509–#511 provide mechanism rows.
5. **What does 0.12.0 vs HEAD show under per-tag replay?** No run exists yet [25].
6. **Is the deferred-rule trim behaviour-safe?** To answer: step 1 of the open spike, at zero model spend [12].

## Source appendix

| # | Claim/finding it supports | Publisher | Pub date | Accessed | Confidence |
| --- | --- | --- | --- | --- | --- |
| [1] | Static and replay method, publish bar, 1.052 status, limits | [agent-harness: docs/benchmarks.md](../../../../docs/benchmarks.md) | 2026-09-23 | 2026-09-23 | high |
| [2] | Committed static figure 7,494; largest file | [agent-harness: benchmarks/static.json](../../../../benchmarks/static.json) | 2026-09-22 | 2026-09-23 | high |
| [3] | Eight-task manifest, leak classes | [agent-harness: benchmarks/tasks.json](../../../../benchmarks/tasks.json) | 2026-09-22 | 2026-09-23 | high |
| [4] | THRESHOLD 0.85, minus-one rule, 5% growth; re-run 6,751 | [agent-harness: scripts/cost_bench.py](../../../../scripts/cost_bench.py) | 2026-09-23 | 2026-09-23 | high |
| [5] | Lint caps 200 lines and 4,202 tokens; live prefix 12,607 | [agent-harness: bin/harness](../../../../bin/harness) | 2026-09-23 | 2026-09-23 | high |
| [6] | Zero spawns in 19 runs; brief-guard metric; detector validity | [agent-harness: docs/caught-in-the-act.md](../../../../docs/caught-in-the-act.md) | 2026-09-23 | 2026-09-23 | high |
| [7] | List-price and unpriced rules; flat 97% hit rate; subagent undercount | [agent-harness: docs/usage.md](../../../../docs/usage.md) | 2026-09-23 | 2026-09-23 | medium |
| [8] | Never sum session and subagent rows | [agent-harness: docs/telemetry.md](../../../../docs/telemetry.md) | 2026-09-23 | 2026-09-23 | high |
| [9] | Standalone measurement report | [agent-harness: docs/standalone-measurement.md](../../../../docs/standalone-measurement.md) | 2026-09-22 | 2026-09-23 | medium |
| [10] | Spike records are pre-registered history | [agent-harness: docs/spikes/README.md](../../../../docs/spikes/README.md) | 2026-09-23 | 2026-09-23 | high |
| [11] | Budget nudge failed; brief budgets and overrun rates | [agent-harness: in-run budget nudge spike](../../../../docs/spikes/2026-09-22-in-run-budget-nudge.md) | 2026-09-22 | 2026-09-23 | medium |
| [12] | Deferred rule text spike, open | [agent-harness: deferred rule text spike](../../../../docs/spikes/2026-09-22-deferred-rule-text.md) | 2026-09-23 | 2026-09-23 | high |
| [13] | Static tier and 5% gate shipped | [GitHub PR #362](https://github.com/JakeSelby/agent-harness/pull/362) | 2026-09-21 | 2026-09-23 | high |
| [14] | Replay runner shipped as same-day ratio | [GitHub PR #368](https://github.com/JakeSelby/agent-harness/pull/368) | 2026-09-21 | 2026-09-23 | high |
| [15] | Delegation never fires; prefix about 20% of a run; trim ceiling about 25% | [GitHub issue #429](https://github.com/JakeSelby/agent-harness/issues/429) | 2026-09-21 | 2026-09-23 | medium |
| [16] | Suite wrote into the real profile (contamination root cause) | [GitHub issue #498](https://github.com/JakeSelby/agent-harness/issues/498) | 2026-09-22 | 2026-09-23 | high |
| [17] | Per-file static pricing tier | [GitHub issue #509](https://github.com/JakeSelby/agent-harness/issues/509) | 2026-09-22 | 2026-09-23 | high |
| [18] | Offline detector replay tier | [GitHub issue #510](https://github.com/JakeSelby/agent-harness/issues/510) | 2026-09-22 | 2026-09-23 | high |
| [19] | Hook by variant decision matrix | [GitHub issue #511](https://github.com/JakeSelby/agent-harness/issues/511) | 2026-09-22 | 2026-09-23 | high |
| [20] | Micro-task tier, separate series | [GitHub issue #512](https://github.com/JakeSelby/agent-harness/issues/512) | 2026-09-22 | 2026-09-23 | high |
| [21] | Zero spawns in forty runs; break-even 4.8 to 5.9 calls | [GitHub issue #513](https://github.com/JakeSelby/agent-harness/issues/513) | 2026-09-22 | 2026-09-23 | high |
| [22] | Per-rule attribution blockers; 1.86x spread; warmth contamination | [GitHub issue #514](https://github.com/JakeSelby/agent-harness/issues/514) | 2026-09-22 | 2026-09-23 | medium |
| [23] | Workflow-tool agents bypass routing | [GitHub PR #578](https://github.com/JakeSelby/agent-harness/pull/578) | 2026-09-23 | 2026-09-23 | medium |
| [24] | Tagged replay must not touch the live profile | [GitHub issue #599](https://github.com/JakeSelby/agent-harness/issues/599) | 2026-09-23 | 2026-09-23 | high |
| [25] | Repeatable per-tag replay shipped, no result yet | [GitHub PR #609](https://github.com/JakeSelby/agent-harness/pull/609) | 2026-09-23 | 2026-09-23 | high |
| [26] | Cost variants with p75 role budgets | [GitHub PR #248](https://github.com/JakeSelby/agent-harness/pull/248) | 2026-09-20 | 2026-09-23 | high |
| [27] | Expected spend stated in every brief | [GitHub PR #254](https://github.com/JakeSelby/agent-harness/pull/254) | 2026-09-20 | 2026-09-23 | high |
| [28] | brief-without-cap rate 3.2 / 3.6 / 3.2 | [GitHub issue #324](https://github.com/JakeSelby/agent-harness/issues/324) | 2026-09-21 | 2026-09-23 | high |
| [29] | Discarded ratios; per-task clean ratios; 13,640 prefix; output share of spend | maintainer notes (unpublished), cost replay journey | 2026-09-22 | 2026-09-23 | medium |
| [30] | Controls that do and do not hold; per-rule method | maintainer notes (unpublished), cost instrument review | 2026-09-22 | 2026-09-23 | medium |
| [31] | Output-archive spike: scripts only, no result | maintainer notes (unpublished), output-archive spike | 2026-09-21 | 2026-09-23 | low |
| [32] | Pyramid tiers; model-invariant split; 23,328 permutations | maintainer notes (unpublished), evaluation harness deep dive | 2026-09-21 | 2026-09-23 | medium |

## Staleness map

Computed with `recon_kit.py staleness` using these windows in months: measurement 3 (AI-adjacent), mechanism-failure 3, version 1, method 24. Nothing is stale today.

- 2026-10-23: [23] Workflow-tool bypass on CLI 2.1.280 (version class). **This is the earliest re-check.**
- 2026-12-21: [28] brief-guard metric.
- 2026-12-22: [2] static figure, [11] nudge rates, [21] break-even, [29] discarded ratios.
- 2026-12-23: [1] 1.052, [5] caps and live prefix, [6] zero spawns, [7] cache hit rate.
- 2028-09: [4] publish bar, [32] pyramid method.

A new CLI release or harness tag invalidates [23] and the replay ratios sooner than these dates.
