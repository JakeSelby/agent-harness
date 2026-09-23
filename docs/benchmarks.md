# Cost benchmarks

What the harness costs you, measured against Claude Code with no harness at all. The static figure
below exists today. The live replay that compares whole tasks has a runner and no published
result yet, so nothing here claims a saving.

## Static context figure

Every session the harness manages starts with its global instructions, rules, selected stances and
output style already in context, plus one listed description for each agent, skill and command. A
bare Claude Code session loads none of that, so the whole count is the harness's standing overhead.

```sh
python3 scripts/cost_bench.py static            # print the figure for this checkout
python3 scripts/cost_bench.py static --check    # what CI runs
python3 scripts/cost_bench.py static --write    # refresh benchmarks/static.json at a release
```

`benchmarks/static.json` is the committed figure for the last release. It records files, lines,
characters, an estimated token count for the default stance selection and for the longest variant
of every dimension, the five largest files, and what that many tokens cost per model. Its
`scopes` block names the set each count is over, because the caps `harness lint` prints are
over a narrower one.

- **Tokens are an estimate:** characters divided by four. It is there to show the trend between
  versions with no tokenizer, network call or API key. It is not a billing figure.
- **Dollars come from `policy/prices.json`.** `session_start` prices the layer as one cache write,
  `later_turn` as one cache read. A session that outlives the cache pays the write again.
- **CI fails when the estimate grows more than 5% over the committed figure.** Trim the growth, or
  add an entry to `benchmarks/allow.json` naming `harness_version`, the new `est_tokens` and a
  `reason`. The entry stops matching as soon as the figure moves again.
- **The caps in `harness lint` are separate.** They bound the worst case — the longest variant of
  every stance — in tokens and in lines, over instructions, rules and stances only; this tracks the
  default selection, output styles and listings included, in tokens and dollars, version by
  version. Both use the same characters-over-four estimate. Which cap binds, and why:
  [how-it-works](how-it-works.md#context-discipline).

## Live replay

`scripts/cost_bench.py replay` runs the pinned tasks in `benchmarks/tasks.json` headlessly, once
against a signed-in, otherwise empty Claude Code profile and once against the installed harness, and
scores each run with a check the agent never sees. It calls a model and spends real usage, so it is
run by hand on a release candidate and never in CI.

```sh
python3 scripts/cost_bench.py replay --verify-tasks              # prove every check; calls no model
python3 scripts/cost_bench.py replay --model <id> --dry-run      # print the schedule
python3 scripts/cost_bench.py replay --model <id>                # 4 tasks x 2 arms x 2 reps
```

- **The arms differ by environment only.** Both get one command line: the same `--model`,
  `--strict-mcp-config`, `--max-budget-usd 2` and the same sandbox settings, with command network
  access off. The bare arm adds `CLAUDE_CONFIG_DIR`, pointing at the empty profile. The fence
  admits each arm's own config directory and `/tmp` for reading and writing, because the
  repository's suite writes to both and a fence that admitted only the CLI's default would fail
  the gate for whichever arm was moved to a bench profile.
- **Each arm's fence is proved before anything is scored.** One capped `-p` run per arm runs
  `bin/harness lint` under that arm's own fence and profile; an arm whose lint is not clean, or
  whose run has a read refused, refuses the whole replay with exit 2 before any scored run
  launches, and its cost counts against `--spend-cap`. The bar is lint rather than the full suite
  because the suite is profile-dependent at older snapshot commits. Every scored row records
  `preflight`. `--skip-preflight` bypasses the check and stamps the rows `skipped`.
- **Every run starts in a throwaway snapshot outside the home directory**, launched with a scrubbed
  environment. A folder under the home directory inherits the user's instruction files through the
  parent-folder walk, which would put the harness into the bare arm. The snapshot holds one commit,
  so the change that solved a task is not reachable from it, and it is removed after scoring.
- **Cost is the CLI's own `total_cost_usd`**, a list-price equivalent and not money charged under a
  plan sign-in. Run order changes it, because a later run finds its prefix already cached, so each
  row also carries a cache-normalised cost that reprices every thread's first-turn cache reads as
  cache writes. It is empty when the CLI output does not carry per-turn usage.
- **An errored run is an error, never a failure.** It sits outside both cost per passed task and
  the pass count, and is counted beside them. The per-run cap is soft, so the runner also stops
  before any launch that could take reported spend past `--spend-cap`.
- **`benchmarks/history.jsonl` holds one row per harness version per run day**, stored as a ratio to
  bare on the same day and model; `benchmarks/history.md` is rendered from it. Compare ratios across
  days, never dollars. The publishable threshold is fixed in the script: the harness costs at most
  85% of bare per passed task while passing no fewer than bare minus one, mean of reps.
- **What is faked:** single-shot prompts stand in for interactive sessions, two of the four tasks
  are synthetic, and only the installed harness can be run; older tags are refused.

**Status.** The live tier has produced one uncontaminated result: 1.052 on a four-task set, above
the 0.85 threshold, so no cost claim is published. Two earlier figures in either direction were
artifacts of the runner's sandbox and of a test-suite defect, both since fixed. Treat this tier as
an instrument whose methodology is under review, not as a result; the static tier above is the
figure to rely on today.

## Limits

- Claude Code only. Codex instructions are rendered at sync time and are not counted.
- Your own `CLAUDE.personal.md`, memory files, MCP servers and hook output are not counted. They
  are yours, not the harness's, and MCP tool definitions alone can outweigh everything measured
  here.
- Full agent and skill bodies load only when used, so only their descriptions are counted.
