# Spike: would an in-run budget nudge to a running subagent earn its weight?

**Status:** `failed` — do not build, 2026-09-22. The measured numbers did not meet the exit
criterion, and the criterion was not adjusted. Issue [#322](https://github.com/JakeSelby/agent-harness/issues/322).

## Question

A subagent learns its soft budget in its brief and hears nothing afterwards. Does a mid-run nudge
— one line naming actual against budget, denying nothing — reach enough over-budget runs, early
enough in them, to pay for the machinery it needs: an incremental transcript reader on every
subagent tool call, which is the heaviest piece of the usage feed?

## Cheapest experiment

The telemetry to answer it already exists, so nothing was built and nothing was run live. A
throwaway script read two things on one machine:

- `~/.local/state/agent-harness/usage.jsonl`, for every `kind: "subagent"` row carrying
  `budget_output_tokens` — the **recorded** sample, written by 0.11.1 when briefs already carried
  budgets.
- The same ledger's earlier Claude Code subagent rows, whose role is priced in
  `primitives/stances/cost/balanced.json`, with today's budget applied retrospectively — the
  **reconstructed** sample. Those runs predate budgets in the brief, so they stand for behaviour
  with no budget signal at all.

For each row the script rebuilt the run's cumulative output curve from the agent's own transcript
under `~/.claude/projects/<project>/<session>/subagents/`, one point per assistant message, each
message id counted once at its largest `output_tokens`, in file order, with the cumulative tool-use
count beside it. Where one agent id existed under two project directories the fullest transcript
was taken; every row's curve total then equalled its ledger total exactly, 89 of 89 and 235 of 235,
which is the check that the right file was read. The curve gives what the ledger alone cannot: the
point in a run where a threshold was crossed, and how much run was left after it.

What is faked: nothing was nudged, so every "could have saved" figure is the **ceiling** — the
tokens emitted after the crossing, on the assumption that a nudged agent stops dead. A real nudge
saves some fraction of that.

## Exit criterion

Fixed before the curve scan, from the issue's own framing — the nudge must be worth an incremental
reader on every subagent tool call:

- it fires on **at least 10%** of budgeted subagent runs, and
- at the crossing the median firing run still has **at least 10 tool calls** left, so the nudge can
  be acted on, and
- the output emitted after the crossing is **at least 10%** of all subagent output tokens.

Two of the three were missed.

## Machine

Apple M5 Pro, 24 GB, macOS 26.5, arm64. One developer machine, one ledger:
3,477 rows, 3,085 of them subagents, of which 2,778 Claude Code. The budgeted window is
2026-09-21 to 2026-09-23 at harness 0.11.1; the reconstructed window is everything before it.
Every figure below is that machine's, and a second machine could differ.

## Measured

Recorded sample — 89 subagent rows whose brief carried a budget:

- 2 of 89 runs (2.2%) ended over `budget_output_tokens`. Both were `builder`; no other role
  overran once.
- The median run finished at 0.17 of its budget; p75 0.32, p90 0.53, p95 0.87, max 1.66.
- Total excess on the two over-budget runs: 118,056 output tokens, 4.5% of the 2,594,799 output
  tokens those 89 runs spent.
- A nudge at 1.0× budget would have fired twice in 89 runs, each time with real runway — 19 and 67
  tool calls left, at 18% of the run's wall clock — addressing at most 115,713 tokens.
- A nudge at 0.8× would have fired 6 times; 4 of those 6 runs ended under budget, a two-to-one
  false-alarm rate. It would have addressed at most 161,579 tokens on the runs that did overrun.
- Tool calls are not a usable proxy for the same signal: 4 runs of 89 exceeded
  `budget_tool_calls`, all `builder`, and only 1 of those 4 also exceeded its token budget.

Reconstructed sample — 235 earlier runs, no budget in the brief, today's budget applied:

- 51 of 235 (21.7%) ended over budget, and the excess is 714,033 tokens, 8.9% of 8,026,505.
- The overruns are marginal and spread across four roles: `reviewer` 15, `gatherer` 14, `builder`
  14, `spec-reviewer` 8, with the smallest twelve ratios between 1.00 and 1.07.
- **This is the finding that decides it.** At the 1.0× crossing the median firing run had **1 tool
  call left**; 23 of 51 had none at all and 29 of 51 had two or fewer. At 0.8× the median firing run
  had 1 call left and 41 of 92 fires had none. A nudge delivered on a tool call the agent never
  makes is not delivered.
- The 0.8× false-alarm rate is the same shape at scale: 41 of 92 fires ended under budget.

Volume, for the cost side: 77,943 subagent tool calls are recorded on this machine against 89
budgeted runs' 4,167. The feed today runs on four parent-thread events per spawn; a nudge on the
subagent's own `PostToolUse` runs on every one of those calls.

## Where a nudge would have to ride

- **Not `SubagentStop`** — the run is over, and the feed already reports the total there.
- **The subagent's own `PostToolUse`** is the only event inside a running subagent. Hooks do fire
  inside a subagent: 22 hook-feedback records were found structurally in this machine's subagent
  transcripts, every one of them a `tool_result` block on a sidechain `user` record, 18 from
  `PreToolUse` and 2 from `PostToolUse`. The runtime's hook documentation agrees, and adds that the
  payload carries `agent_id` and `agent_type` inside a subagent, which is the identification a
  per-agent "once only" latch needs.
- `transcript_path` in that payload is the **parent's** transcript, not the agent's, so the nudge
  would derive the agent's file the way `usage-feed.py` already does from the session id and the
  agent id. The incremental reader — saved offset, inode and first-record hash, byte and clock
  budgets — exists there and would be reused rather than rewritten. So the harness *can* address a
  running subagent; it is the value, not the mechanism, that fails here.

## Verdict: do not build

Against the criterion: the nudge fires on 2.2% of budgeted runs, not 10%; the tokens it could
address are 4.5% of subagent output, not 10%. Only the runway test passes, and only on a sample of
two. The reconstructed sample, an order of magnitude larger, shows why that runway is luck: when
roles overrun without a budget in the brief, they overrun by a few percent at the very end of the
run, where a nudge arrives after the last tool call.

The cheaper reading of the same data is that the brief already did the work. Budgets in briefs
coincide with overruns falling from 21.7% to 2.2% and the median run landing at 0.17 of budget.
What remains is one role, `builder`, overrunning a budget that may simply be too small for the work
it is given — a cost-table question, answered by changing a number, not by a new channel.

The `switches.nudge_at` key stays as it is. It is already null in `frugal`, empty in `max`, and
`[1.0, 1.5]` in `balanced` for the turn feed on the parent thread; nothing here changes it, and no
subagent-side reader is added.

## What would change it

Re-run this same scan — the ledger already records budget and actual on every subagent row, so it
costs one script and no new instrumentation — and build when, over a window of at least 200
budgeted subagent rows:

- over-budget runs are **10% or more** of them, and
- the excess is **10% or more** of subagent output tokens, and
- at the 1.0× crossing the median over-budget run still has **10 or more tool calls** left.

Any one of those alone is not enough: a high overrun rate discovered with no runway is the
reconstructed sample, and it is the case a nudge cannot help. A narrower trigger would also change
the answer: if overruns stay concentrated in one role, a nudge restricted to that role is a much
smaller thing than a reader on every subagent tool call, and it should be spiked separately against
that role's rows alone.
