# Spike: can action-gated rule text be deferred behind the hook that fires on the act?

**Status:** `open` — framed, not run, 2026-09-22. Nothing here is a measurement. Issue
[#430](https://github.com/JakeSelby/agent-harness/issues/430), change 1 of three; changes 2 and 3
landed without it.

## Question

Seven always-loaded files bind only once a specific act is attempted: `secrets`, `verification`
and the `commits`, `licensing`, `testing`, `plan-ceremony` and `build-vs-buy` stance variants.
Measured on this branch they are 5,012 characters, an estimated 1,253 tokens, 36% of the 3,524-token
rules-and-stances layer. The harness already defers this way elsewhere — `grade-bash` and
`brief-guard` deliver their text at the tool call rather than at session start — and the rules
layer has not adopted the pattern.

Does moving those seven out of the always-loaded layer and into hook output keep the behaviour they
buy, or does a rule that arrives at the act arrive too late to change the plan that produced it?

That is the real risk and it is not a token question. `testing` and `plan-ceremony` shape work well
before any gated tool call: an agent that learns "tests ship with the change" at `git commit` has
already written the change without them. `secrets`, `verification`, `commits` and `licensing` are
closer to a single detectable act and are the plausible candidates.

## Cheapest experiment

Do not build the deferral. Two cheap steps, in order, and the first can kill the idea alone:

1. **Trace each of the seven to an act a hook can see.** For every operative line, name the event
   (`PreToolUse` on `Bash`, on `Write`, `UserPromptSubmit`, `Stop`) and the matcher that would fire
   it, using the existing `policy/hooks/` detectors — `rule-detectors.py` already recognises commit,
   push, secret-in-write and plan-card shapes, so the matchers mostly exist. A line with no act,
   or whose act comes after the decision it governs, is not deferrable and stays resident.
2. **Replay the deferred arm against the resident arm on the tasks that exercise those rules.**
   `scripts/cost_bench.py replay` is the runner; the arm is a profile whose rules directory omits
   the deferred files and whose hooks emit them. Score compliance with an oracle that reads the
   transcript, not the model's own account: commit messages against Conventional Commits, a
   `--no-verify` or force-push attempt, a secret written to a tracked file, a change landed with no
   test.

## Exit criterion

Fixed before anything runs. Build the deferral only when all three hold:

- **At least 900 of the 1,253 tokens** are traced in step 1 to an act a hook can see before the
  decision the rule governs, so the win is worth an architecture change.
- **Compliance does not fall**: over at least 20 paired task runs, the deferred arm's oracle pass
  count is no lower than the resident arm's minus one — the same bar `benchmarks/history.jsonl`
  already uses for cost.
- **The measured live prefix falls by at least 700 tokens**, read from a paired transcript's first
  assistant `cache_creation_input_tokens`, not from `benchmarks/static.json`.

Any one missed is a `failed` record and the seven files stay where they are. A partial pass — say
`secrets` and `commits` traceable but `testing` not — is a narrower spike against those files
alone, not a licence to defer all seven.

## What was NOT run

Everything. No trace was done, no arm was built, no replay was launched, no transcript was paired.
The token figures above are the static character-count estimate for this branch and nothing else;
`benchmarks/static.json` counts files, so it cannot answer the compliance question or the live
prefix. The next session starts at step 1, which costs one careful read of seven files and no
model spend.

## Machine

Not applicable yet. When step 2 runs, record the machine, the CLI version, the model and the day,
because the replay's dollars are only comparable within one of those.
