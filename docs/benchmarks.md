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
`scopes` block names the set each count is over, because the caps `citizen lint` prints are
over a narrower one.

- **Tokens are an estimate:** characters divided by four. It is there to show the trend between
  versions with no tokenizer, network call or API key. It is not a billing figure.
- **Dollars come from `policy/prices.json`.** `session_start` prices the layer as one cache write,
  `later_turn` as one cache read. A session that outlives the cache pays the write again.
- **CI fails when the estimate grows more than 5% over the committed figure.** Trim the growth, or
  add an entry to `benchmarks/allow.json` naming `harness_version`, the new `est_tokens` and a
  `reason`. The entry stops matching as soon as the figure moves again.
- **Every counted file is priced on its own.** The `files` map gives each file's characters,
  estimated tokens and dollars, and sums to the totals within rounding. `--check` prints one line
  per file whose estimate moved since the committed figure, priced on the model with the highest
  cache-read rate, so a change to one rule reads as that file's delta rather than a moved total.
  The 5% gate stays on the total.
- **The caps in `citizen lint` are separate.** They bound the worst case — the longest variant of
  every stance — in tokens and in lines, over instructions, rules and stances only; this tracks the
  default selection, output styles and listings included, in tokens and dollars, version by
  version. Both use the same characters-over-four estimate. Which cap binds, and why:
  [how-it-works](how-it-works.md#context-discipline).

### Recorded trims

One row per change that set out to shrink the static figure, before and after, from
`scripts/cost_bench.py static` run on that change's branch. `benchmarks/history.jsonl` cannot hold
these: its rows are replay ratios against a bare arm on one model and one day, and a static trim
has no arm. Read the rows in order; none of them is a live measurement.

| Change | Always-loaded | Listings | Total |
| --- | --- | --- | --- |
| Baseline at 0.12.0 | 5,198 | 2,326 | 7,524 |
| After shortening skill and agent descriptions (#430) | 5,198 | 1,980 | 7,185 |
| After trimming the output style (#430) | 4,539 | 1,980 | 6,519 |

## Live replay

`scripts/cost_bench.py replay` runs the pinned tasks in `benchmarks/tasks.json` headlessly, once
against a signed-in, otherwise empty Claude Code profile and once against the installed harness, and
scores each run with a check the agent never sees. It calls a model and spends real usage, so it is
run by hand on a release candidate and never in CI.

```sh
python3 scripts/cost_bench.py replay --verify-tasks              # prove every check; calls no model
python3 scripts/cost_bench.py replay --model <id> --dry-run      # print the schedule
python3 scripts/cost_bench.py replay --model <id>                # 7 tasks x 2 arms x 2 reps
python3 scripts/cost_bench.py replay --model <id> \
    --tag v0.12.0 --tag v0.13.0 --harness-config ~/.claude-bench-harness   # two versions, one run
```

- **`--tag` is what the harness arm runs, and it is repeatable.** `candidate`, the default, is the
  harness installed at `~/.claude` as it stands. Any other value is a git ref of this repository:
  it is checked out with its history intact, projected by its own `bin/harness sync` into a config
  directory of its own, run as a whole schedule, and torn down before the next tag. Each tag
  writes its own results file and its own history row, stamped with the version and commit of the
  ref that ran. Every ref is resolved before the first launch, so a typo costs nothing, and
  `--spend-cap` applies to each tag's schedule on its own.
- **A tagged sync touches nothing of yours.** It runs with a temporary HOME as well as an explicit
  `CLAUDE_CONFIG_DIR`, so it neither reads nor writes the profile you run under, and it renders no
  identity or stance selection out of your `~/.config/agent-harness/config.json`: a tagged arm
  loads that tag's defaults, which is the same question asked of every tag. A sync target that
  resolves to your live profile, sits inside it, holds it (HOME or any ancestor) or is the bare
  profile is refused. Because a profile's credential is keyed on its absolute path, a directory
  made for the run is not signed in; name a signed-in `--harness-config` as the directory each
  tag is synced into when the run is meant to spend. That profile must hold no harness files
  already (a link counts only when it leads into a harness checkout or sits at a name the harness
  manages; the CLI's own `debug/latest` does not), and it cannot serve `candidate` in the same
  run, and none of the names the sync writes (`rules`, `skills`, `commands`, `agents`, `hooks`,
  `output-styles`, `plans`, `CLAUDE.md`, `settings.json` and the rest) may be a link leading out
  of it. After each tag's schedule, exception or interrupt included, the sync is taken back out
  of it rather than the profile rolled back: exactly the links and files the sync's own manifest
  and ownership records name are removed, a directory it made goes only once empty, and the one
  file it rewrites in place, `settings.json`, is put back from a copy taken beforehand through an
  atomic write. Nothing else is touched: a transcript another session wrote during the run stays,
  and credential files are never copied, rewritten or deleted, whether they existed before or
  the CLI created them mid-run, so a refreshed token stays refreshed and a fresh sign-in stays
  signed in. Nothing in the profile is read but `settings.json`; a FIFO or an unreadable file
  is listed by its stat and never opened. The records are read from where the harness at HEAD
  writes them, so the profile itself is checked afterwards: if anything the sync could have
  written is still there, or the records were empty, the run stops at that tag with the leftover
  paths named, before another tag launches into a profile that would refuse it. If taking the
  sync back fails, the copy is kept and its path printed. The refusals above are all decided
  before the first launch of any tag; the copy-aside, checkout and sync run as each tag's turn
  comes. The pinned checkout is admitted to the harness arm's fence for reading only, and a
  pinned tag's results go in a folder named for it.

- **The arms differ by environment only.** Both get one command line: the same `--model`,
  `--strict-mcp-config`, `--max-budget-usd 2`, the task's own `max_turns` as `--max-turns`, and the
  same sandbox settings, with command network access off. The bare arm adds `CLAUDE_CONFIG_DIR`,
  pointing at the empty profile. The fence admits each arm's own config directory and `/tmp` for
  reading and writing, because the repository's suite writes to both and a fence that admitted only
  the CLI's default would fail the gate for whichever arm was moved to a bench profile.
- **Neither arm has the web.** `WebFetch` and `WebSearch` run in the CLI's own process, outside the
  command sandbox, so the fence's empty network list does not reach them; a profile's permission
  rules do, and the harness profile allows both on documentation domains. The settings every arm
  launches with therefore deny both tools, and a deny outranks any profile's allow.
- **The stop gate can fire.** The stop-gate hook runs a gate only in a folder the user trusted, and
  no one trusts a fresh snapshot. For the length of each scored run, its snapshot is listed in
  `~/.config/agent-harness/trusted.txt`, where `citizen trust` lists roots, and exactly that line
  is removed afterwards. Every arm's snapshot is listed; the bare arm has no hook to read it.
- **Every run is captured as `stream-json` with hook events**, the one format that carries the
  Stop hook's decisions, so each row records `stop_hooks`, how often the hook ran, and
  `hook_blocks`, how often it refused the stop. A raw file kept in the older single-document form
  still reads, with both fields `null`.
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
- **Beside it, `cache_miss_ratio`: how much of its prefix the run re-bought.**
  `cache_write / (cache_read + cache_write)` summed over every turn the run opened, subagent
  threads included, because a fan-out's fresh prefix is part of what the run cost. The
  arithmetic is `citizen usage --by prefix`'s, imported from that module rather than restated,
  but the two are not the same number: the session figure subtracts a subagent's tokens, so a
  run that fanned out reads higher here, by design. A candidate that buys fewer tokens by
  re-writing its prefix more often is otherwise invisible in the history, so `history.jsonl` and
  `history.md` carry each arm's mean of it beside the cache-normalised ratio. A run whose output
  carries no per-turn cache figures, any one of whose turns reports usage without them, or whose
  turns report neither reads nor writes, is `null` and is left out of the arm's mean; so is an
  errored run, whose turns are not the spend it would have had. Never zero: zero is a run that
  served its whole prefix.
- **An errored run is an error, never a failure.** It sits outside both cost per passed task and
  the pass count, and is counted beside them. The per-run cap is soft, so the runner also stops
  before any launch that could take reported spend past `--spend-cap`.
- **`benchmarks/history.jsonl` holds one row per harness version per run day**, stored as a ratio to
  bare on the same day and model; `benchmarks/history.md` is rendered from it. Compare ratios across
  days, never dollars. The publishable threshold is fixed in the script: the harness costs at most
  85% of bare per passed task while passing no fewer than bare minus one, mean of reps.
- **What is faked:** single-shot prompts stand in for interactive sessions, 2 of the 7 tasks are
  synthetic, and a tagged run measures the tag's default configuration rather than a configured
  one.
- **A task that cannot be passed honestly leaves the set** and moves to the manifest's `retired`
  list with its reason and date. `usage-prices` left on 2026-09-25: its held-back tests pin live
  prices and helper names its prompt never gives, and no arm can reach the web to confirm a price.

**Status.** The live tier has produced one uncontaminated result: 1.052 on a four-task set, above
the 0.85 threshold, so no cost claim is published. Two earlier figures in either direction were
artifacts of the runner's sandbox and of a test-suite defect, both since fixed. A review on
2026-09-24 found six more ways the arms were unequal or a task unfair: the task count above, the
turn cap, the stop gate, web access, `usage-prices` and hook capture. Each is fixed as described
above, and no result has been taken since. Treat this tier as an instrument whose methodology is under review, not as a result; the static tier above is the
figure to rely on today.

## Limits

- Claude Code only. Codex instructions are rendered at sync time and are not counted.
- Your own `CLAUDE.personal.md`, memory files, MCP servers and hook output are not counted. They
  are yours, not the harness's, and MCP tool definitions alone can outweigh everything measured
  here.
- Full agent and skill bodies load only when used, so only their descriptions are counted.
