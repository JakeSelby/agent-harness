# Usage telemetry

Measurements identify their runtime. Claude and Codex transcript adapters share detectors;
Codex cumulative token snapshots are counted once, unavailable metrics remain unknown, and
reports label partial totals. Detector failures are excluded from clean-session denominators.
See [runtime controls](runtime-controls.md) for limits. The Claude transcript details below
remain specific to that adapter.

The `usage-log` hook runs on `SessionEnd` and keeps one record per session in
`~/.local/state/agent-harness/usage.jsonl`. It is a local file and nothing else: no network
call, no service, no account, and nothing beyond the session id, the repository directory name,
the branch, model ids and token counts.

## What is recorded

Every row names its `kind`: `session`, `subagent` or `worker`. A row written before the field
existed is read as a session, which is all there was to record, and `--rescan` upgrades it.

**`kind: "session"`** — `session_id`, `repo`, `branch`, `models`, `started`, `ended`, `input`,
`output`, `cache_read`, `cache_write`, `subagents`, `turns`. The source is the transcript
Claude Code already writes under `~/.claude/projects/`. The worker streams it and sums the four
token fields over assistant messages **once per message id, at that id's largest figure**: one
API response is written as several transcript entries, so counting per line inflates every
total — but those entries do not repeat one `usage` object. The early ones carry a partial
streaming `output_tokens` and the last carries the response's true figure, so taking the first
undercounts it. The field-wise maximum is the final figure, and a reordered or truncated tail
cannot lower it. `subagents` counts `Agent` tool calls. The token totals **include the
session's subagents**, because their tokens are the session's bill — counted once over one map
of message ids, never as a sum of two files. Older Claude Code wrote a subagent's turns into
the session file as sidechain lines and newer Claude Code writes them to the agent's own file;
a transcript carrying both would otherwise pay for every delegated token twice.

**`kind: "subagent"`** — one row per `agent-<id>.jsonl` anywhere under `<session>/subagents/`,
the tree Claude Code writes beside the session's own file. The walk is recursive because a
Workflow-tool agent lives a level deeper, at `subagents/workflows/wf_<id>/`, and its `workflow`
field names that directory. `agent_id`, `agent_type` and `spawn_depth` come from the sibling
`.meta.json`, and an agent written without one is recorded as `agent_type: "unknown"` rather
than dropped. Then `model` — the id the agent's own transcript reports, most frequent across its
assistant records, falling back to the alias the spawn asked for only when it recorded none, so
a routed spawn and a direct one on the same model group under one name — `effort`, the four
token fields and `tool_calls`. `tool_use_id` is
the parent call this row belongs to, `requested_type` is the agent type that call asked for, and
`rerouted` is the two disagreeing — the measure of how often a spawn hook moved a spawn. A
requested type is kept only when it is a name the tool could have resolved; anything else is
recorded as `"other"`. These rows carry the same tokens a second time, attributed, which is why
no grouping sums both them and their session.

**`kind: "worker"`** — one row per completed `harness role run` worker, with the role name as
`agent_type`. A worker is an isolated CLI session; its runtime reports what the run cost in the
envelope or event stream the adapter already reads, and `workers.py` writes those totals into
its `status.json`. A runtime that reports none leaves the fields unknown rather than zero.
Neither runtime reports a worker's tool-call count, so `tool_calls` is unknown for workers. A
run that timed out or failed is not recorded: its total compares to nothing. A worker is
launched by name, so its `requested_type` and `tool_use_id` are null.

No row holds prompt text, command text or a brief: counts, and the identifiers `tool_use_id`
and `requested_type`, which are a tool call's id and an agent name the tool could have resolved.

`SessionEnd` hooks share a 1.5-second budget, so the hook spawns a detached worker and returns
at once. Rows are upserted by `(session_id, runtime, kind, agent_id)`, so re-reading a
transcript never duplicates one, and a subagent transcript is only ever read from its session.

### Codex rollouts

Codex is read from `~/.codex/sessions/` and `~/.codex/archived_sessions/` — `CODEX_HOME`
moves both — and it writes a subagent to a rollout file of its own rather than beside its
parent's. The `session_meta` is what tells the two apart: a top-level rollout's
`payload.source` is a string naming the front end, a spawned thread's is the object
`{"subagent": {"thread_spawn": {…}}}` carrying the parent thread id, the depth, the agent path
and a nickname. The row takes `agent_role` as its `agent_type` and falls back to
`agent_nickname`, which is what the fallback actually does today: Codex leaves the role null
and names each thread, so `--by role` groups Codex threads by nickname and the groups are
small. Only the **first** `session_meta` is this rollout's own — a thread that inherited its
parent's history carries the parent's further down the file.

**A Codex parent's tokens do not include its children's**, which is the opposite of the Claude
Code rule above, so `harness usage` sums Codex subagent rows and skips Claude Code ones. The
evidence is the corpus of 438 rollouts this was built from: of the 21 parent threads with both
a typed total and children with one, four report fewer tokens than their own children sum to,
2.0M against 30.6M in the widest case. A total that included its children could not be smaller
than them.

`input_tokens` is reported inclusive of `cached_input_tokens`, `total_tokens` is input plus
output, and `reasoning_output_tokens` is part of `output_tokens` rather than beside it — no
exception in the 349 rollouts carrying a typed split. Codex Desktop often writes a snapshot
with `total_tokens` alone and every typed field zero (85 of 107 top-level Desktop rollouts
here). That row keeps `total`, is marked `partial`, and leaves the typed fields unknown, so the
report excludes it rather than reading a real session as free.

Codex capture travels through `harness usage --rescan` rather than through the hook. The
lifecycle coordinator does register `SessionEnd`, but whether the payload Codex sends names the
rollout file has not been observed here — no Codex CLI was installed on the machine this was
measured on, and nothing in the rollouts or `~/.codex/logs_*.sqlite` records a hook payload.
The hook accepts `rollout_path` and `session_path` beside Claude Code's `transcript_path` on
that chance; the rescan is the path known to work. Run it after a stretch of Codex work.

## Usage feed

The usage log is read after the fact. The feed is the same measurement while the session is
still running: the `usage-feed` hook injects one or two lines of context so the orchestrator
sees what it is spending before it delegates again.

- On **`UserPromptSubmit`**, one line with the last turn's output tokens and tool calls and the
  session's own — but only when there is a turn behind it and its figures are not the ones
  already printed, because a background agent's completion arrives as a prompt of its own and
  several in a row otherwise repeat one turn — followed by one line per subagent that has
  finished since the previous prompt.
  That second part is how a background spawn is reported at all: its `PostToolUse` fires at
  launch, before the agent has spent anything. At most five agents are listed, then `… and n more`.
- On **`PostToolUse`** for a synchronous `Agent` return, one line for that subagent, on the spot.
  Any `Agent` call, a background launch included, also carries a line when more agents are
  running than `max_parallel`: `usage-feed: 7 subagents running against a posture width of 6`.
  It is a note and never a decision — the feed has no deny path and writes no permission field.
- On **`SubagentStart`** and **`SubagentStop`**, nothing is injected — a `SubagentStop` context
  would reach the agent that has just finished — but the start and the cost are recorded for the
  lines above. Running means started and not yet stopped.

A subagent's figure is summed from its own transcript, never from the tool response, which
reports only the agent's **last** response: measured at 3,143 output tokens against 10,575
actually spent. Each line names the agent type, what it spent and, when its row carries budgets,
the larger of the two ratios against them, prefixed `over budget` past a `nudge_at` multiple.

That sum is capped at 8 MiB from the end of the agent's transcript and at four seconds, because
it runs inside a hook's timeout. When a cap bites, the line says `(partial)`; when the sum could
not be made at all, it says `spend unknown` rather than reporting the agent at zero. Either way
the stop is recorded, because an agent whose stop went missing would count as running for the
rest of the session. A start whose stop never arrives is forgotten after three hours.

The sum is made when the agent is **reported**, not when it stops. A `SubagentStop` fires the
instant the agent ends, which can be before one of its responses has been flushed to its
transcript, and it waits for nothing because a prompt may be queued behind it — so a stop with no
figure in it, or one read out of a response still being written, is journalled as not yet summed
and is summed again on the line that names it, before the lock is taken and inside one wall-clock
budget shared by every agent that event reports. Agents that budget does not reach keep their
place and are summed at the next event. `spend unknown` therefore means a transcript that is not
there; a transcript that is there and still holds no response says `spend not yet recorded`, and
the figure it gains later reaches the session totals without the agent being named twice.

A synchronous return can also arrive before the agent's last response is on disk: one API
response is written as several records, the early ones carrying a partial streaming count and
the last one a `stop_reason`. So the return polls the transcript's tail for up to a second,
waiting for that record, and the line says `(so far)` when it never comes. Whatever figure was
printed, the settled one the stop records afterwards raises the session totals — the agent is
never named a second time, and the session total is never below the sum of the final figures.

Four settings in the active `cost` variant's sidecar govern all of it, and the hook holds no
number of its own:

- `turn_feed: "off"` — nothing is injected anywhere and no file is written.
- `turn_feed: "thresholds"` — no turn line; only subagents at or over the smallest `nudge_at`.
  An agent nothing was said about stays unreported, so a later threshold crossing can still name it.
- `turn_feed: "every-turn"` — the turn line and every finished subagent. `balanced` and `frugal`
  ship this.
- `nudge_at` — the multiples that mark a return as over budget. An empty list, which `max` ships,
  means never.
- `max_parallel` — the width the running-agent note measures against. `null`, which `max` ships,
  means the note never appears.

### State, and why it is two files

These hooks are separate processes that run at the same time: tool calls go out in parallel and
several agents finish at once. So the state is split, both files 0600 in a 0700 directory under
`~/.local/state/agent-harness/feed/`.

- `<session-id>.events.jsonl` is append-only. A subagent starting or finishing is one line under
  4 KB written with a single `os.write` on an `O_APPEND` descriptor — an atomic append no handler
  ever rewrites, so no record can be lost to a concurrent one.
- `<session-id>.json` is the main thread's reader state: the transcript offset, the journal
  offset, the running totals, the open message ids, the agents still in flight and the finished
  ones not yet named. Everything that reads and then writes it does so under an exclusive
  `flock` on `<session-id>.lock` with a two-second bound. No lock, no write, and nothing said.

Nothing slow ever happens while that lock is held. `SubagentStart` and `SubagentStop` never take
it — they append and exit — and the two main-thread events sum a subagent's transcript before
acquiring it. A four-second sum under the lock would starve the prompt waiting behind it, and
that prompt would lose its line in silence.

Both files hold counts and agent type names only — no prompt text, no command text, no agent
output — and an agent type that is not a plain name is recorded as `other`. A session's files
are swept once a day, together and only when the newest of them has gone a fortnight untouched,
never the running session's; `harness uninstall` removes the directory.

The two offsets are what keep the hot path cheap: each prompt reads the transcript and the
journal from where it left off, so a long session's subagent total can only ever grow.
It is trusted only while the file is the same file, which the inode and a hash of the first
record decide, so a transcript replaced by a *larger* one resets exactly as a truncated one does.
With no usable state the read starts 8 MiB from the end rather than at byte zero, because a
resumed session's transcript runs to hundreds of megabytes and a hook killed at its timeout
would stall every prompt after it. Any read that skipped content, or that ran past its
three-second budget, marks the totals `(partial)`.

Codex raises none of `UserPromptSubmit`, `SubagentStart` or `SubagentStop`, so the feed is
declared uncovered there in `adapters/codex/capabilities.json`; posture still reaches Codex
through role-run workers.

### The session registry

One more directory sits beside the feed's, `~/.local/state/agent-harness/sessions/`, written by
session start rather than by any measurement: one small file per session naming the agent
definitions that session's registry held, which is what decides whether an unnamed spawn can be
routed to a band worker — see [runtime controls](runtime-controls.md). It holds agent names and a
timestamp, nothing about the work; the files are owner-only in an owner-only directory, swept
after a fortnight of not being used, and removed by `harness uninstall`.

## Reading it

```sh
bin/harness usage                      # last 30 days, grouped by day
bin/harness usage --days 7 --by repo
bin/harness usage --by model           # a session using two models groups under both, joined
bin/harness usage --by role            # per agent type: runs, p50/p75/p90 output and tool calls
bin/harness usage --rescan             # re-read transcripts in the window first, then report
```

`--by role` reads the subagent and worker rows. Spend per delegated task is a distribution, not
a mean, so it prints three points on the curve; `unmeasured` counts the runs whose runtime
reported no tool-call figure, which are named there rather than averaged in as a zero.

The token groupings — `day`, `repo`, `model` — sum session and worker rows and never a
subagent's. A subagent's tokens are already inside its session's total; a role-run worker has
no session row at all, so leaving it out would hide its spend in every report there is.

A session that crashes or is killed never fires `SessionEnd` and so is never recorded live;
`--rescan` walks every transcript touched inside `--days` and upserts it, which is how you fill
those gaps.

### Re-seeding budgets

A cost variant's per-role budgets are measured, not guessed, so they go stale as roles change.
Run `bin/harness usage --rescan --by role` over a window wide enough to hold a few dozen runs,
read the p75 column for the role — the shipped figures are that point on the curve — and write it
into your variant's row as `budget_output_tokens` and `budget_tool_calls`.

## What the hit rate tells you

`hit` is `cache_read / (input + cache_read + cache_write)` — the share of the prompt served from
cache rather than paid at base input rate. `claude/skills/delegation-tiering/SKILL.md` puts
caching in Gate 0: it is an orchestrator lever, not a subagent one, because a subagent starts a
fresh prefix sharing no cache with its parent and parallel fan-outs with identical prefixes each
pay full price. So a repo whose hit rate falls as its `subagents` count rises is paying for
delegation twice; check the return caps before you reach for a different tier.

## Rule telemetry

The same pass that sums the tokens builds the event list `claude/hooks/rule-detectors.py`
documents and runs every detector over it, so the record carries three more fields:

- `rules` — `{detector id: hits}`, detectors with no hit omitted. A hit is a count, never a
  snippet: `usage.jsonl` holds no command text and no message text.
- `counts` — `web_search`, `agent` and `ask_user` tool calls, recorded whether or not a
  detector fires, because the capped ones are worth watching below their cap.
- `stances` — the resolved `dimension: variant` map, so a hit can be read against the stance
  that was in force. The ladder is the CLI's: built-in defaults, then
  `~/.config/agent-harness/config.json`, then `HARNESS_STANCE_<DIMENSION>`, which every hook
  inherits from the session.

A registry that is missing, broken or a version apart costs the record its `rules` and `counts`
and nothing more: the record is written with `rules_error` naming the failure. A record with no
`rules` map is a gap, not a session without hits — it is left out of every count and out of the
share's denominator, and the report says how many there were.

A rescan cannot know the stances a past session ran under, only this minute's. It leaves a
record's `stances` alone when it has them and otherwise stamps the current ones with
`"stances_source": "rescan"`, which `--by stance` then excludes by name. The stamped stances
still drive the detectors, so hit counts do backfill.

### What each detector looks for

| Detector | Rule | Hit on |
| --- | --- | --- |
| `transcript-hygiene/whole-file-cat` | transcript-hygiene | a lone `cat <one path>`: no pipe, no filter, no heredoc, no redirect |
| `transcript-hygiene/unfiltered-find` | transcript-hygiene | `find <dir>` with no filtering predicate and nothing consuming its output |
| `transcript-hygiene/model-wrote-no-cap` | transcript-hygiene | an `Agent` brief the model wrote with no word cap, for an agent whose definition carries none |
| `delegation/executed-from-summary` | delegation | a Bash command whose first appearance in the session was inside an `Agent` return |
| `verification/no-verify` | verification | a commit or push that walks past the repository's own hooks |
| `secrets/secret-in-write` | secrets | a secret-shaped string written to a file or into a heredoc body |
| `secrets/git-add-secret-file` | secrets | `git add` of a path whose name says it holds a credential |
| `research/search-over-cap` | research-and-verification | the web search that takes the session past the per-session cap |
| `cache-hygiene/model-switch` | cache-hygiene | a model change mid-session, which rebuilds the cached prefix |
| `cache-hygiene/compact` | cache-hygiene | each compaction boundary in the transcript |
| `voice/banned-opener` | voice-and-format | a final message opening with a phrase the output style bans, or closing with one |
| `voice/second-table` | voice-and-format | two or more table blocks in one final message |
| `decisions/no-alternatives` | decisions-and-plans | a final message whose recommendation line names no other course |
| `autonomy/confirmed-irreversible` | autonomy | a command re-run behind the `HARNESS_CONFIRMED=1` marker |
| `autonomy/denied-by-grade` | autonomy | a Bash result carrying the grade hook's deny signature |
| `commits/non-conventional` | commits | a commit subject that is not a Conventional Commit line |
| `commits/missing-trailer` | commits | a commit message with no `Co-Authored-By:` line |

A rule with nothing a transcript can decide opts out by name in `OPT_OUT`, with the reason;
`harness lint` fails on a rule file that has neither a detector nor an opt-out.

Every detector reads a tool call as the model wrote it. A transcript records the model's
`tool_use` input, while a `PreToolUse` hook's `updatedInput` is written to a separate
`attachment` line the scan does not read, so no detector can see what a hook delivered.
`transcript-hygiene/model-wrote-no-cap` is named for that: it counts briefs `brief-guard` went
on to cap, and a hit is the orchestrator's omission and not an uncapped brief reaching a
subagent. It was called `transcript-hygiene/brief-without-cap`, which read as the second thing;
`rule-detectors.RENAMED` maps the old id to the new one. The ledger file is never rewritten for a
rename — `--rules` folds that map as it reads, in all three groupings — so a record written under
the old id reports under the new one and the series does not split.

### Reading the report

```sh
bin/harness usage --rules                      # hits per detector over the last 30 days
bin/harness usage --rules --by repo            # sessions, hits and the top three per repo
bin/harness usage --rules --by stance          # the same, per dimension=variant
bin/harness usage --rescan --days 30 --rules   # backfill from the transcripts, then report
```

`--rules` groups by rule, repo or stance; `--by model` is refused rather than quietly regrouped,
since a session's hits belong to no one of its models. Every registry id gets a line, including
the ones with no hit, and two annotations are printed
from the numbers alone. `promote?` means the detector hit in more than 30 percent of the
sessions in a window of at least 20; `unobserved` means it hit in none of at least 20. A window
narrower than 20 sessions is annotated nothing, because a share over three sessions says little.

Those two are the ends of one ladder. A rule that trips in most sessions is prose that failed:
the agent read it and walked past it anyway, so it wants to be a hook, where the decision is
made for it rather than asked of it. A rule unobserved for a month is either kept honestly by
the model or unobservable from here, and either way it can leave the 200 always-loaded lines
and live in the skill that explains it.
