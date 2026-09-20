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
than dropped. Then `model`, `effort`, the four token fields and `tool_calls`. `tool_use_id` is
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

## Usage feed

The usage log is read after the fact. The feed is the same measurement while the session is
still running: the `usage-feed` hook injects one or two lines of context so the orchestrator
sees what it is spending before it delegates again.

- On **`UserPromptSubmit`**, one line with the last turn's output tokens and tool calls and the
  session's own, followed by one line per subagent that has finished since the previous prompt.
  That second part is how a background spawn is reported at all: its `PostToolUse` fires at
  launch, before the agent has spent anything. At most five agents are listed, then `… and n more`.
- On **`PostToolUse`** for a synchronous `Agent` return, one line for that subagent, on the spot.
- On **`SubagentStop`**, nothing is injected — that event's context would reach the agent that
  has just finished — but the agent's cost is recorded for the lines above.

A subagent's figure is summed from its own transcript, never from the tool response, which
reports only the agent's **last** response: measured at 3,143 output tokens against 10,575
actually spent. Each line names the agent type, what it spent and, when its row carries budgets,
the larger of the two ratios against them, prefixed `over budget` past a `nudge_at` multiple.

Three settings in the active `cost` variant's sidecar govern all of it, and the hook holds no
number of its own:

- `turn_feed: "off"` — nothing is injected anywhere and no state file is written.
- `turn_feed: "thresholds"` — no turn line; only subagents at or over the smallest `nudge_at`.
- `turn_feed: "every-turn"` — the turn line and every finished subagent. `balanced` and `frugal`
  ship this.
- `nudge_at` — the multiples that mark a return as over budget. An empty list, which `max` ships,
  means never.

State lives in `~/.local/state/agent-harness/feed/<session-id>.json`, one file per session,
0600 in a 0700 directory. It holds the byte offset read so far, running counts and one record
per finished subagent — the agent type, its output tokens, its tool calls and whether it has
been reported. No prompt text, no command text, no agent output. The offset is what keeps the
hot path cheap: each event reads from it to EOF and no further, and a transcript that shrank
resets to the current EOF and marks the totals `(partial)`.

Codex raises neither `UserPromptSubmit` nor `SubagentStop`, so the feed is declared uncovered
there in `adapters/codex/capabilities.json`; posture still reaches Codex through role-run workers.

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
| `transcript-hygiene/brief-without-cap` | transcript-hygiene | an `Agent` brief with no word cap, for an agent whose definition carries none |
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
