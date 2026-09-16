# Usage telemetry

The `usage-log` hook runs on `SessionEnd` and keeps one record per session in
`~/.local/state/agent-harness/usage.jsonl`. It is a local file and nothing else: no network
call, no service, no account, and nothing beyond the session id, the repository directory name,
the branch, model ids and token counts.

## What is recorded

`session_id`, `repo`, `branch`, `models`, `started`, `ended`, `input`, `output`, `cache_read`,
`cache_write`, `subagents`, `turns`. The source is the transcript Claude Code already writes
under `~/.claude/projects/`. The worker streams it and sums the four token fields over
assistant messages **once per message id**: one API response is written as several transcript
entries that each repeat the same `usage` object, so counting per line inflates every total.
`subagents` counts `Agent` tool calls.

`SessionEnd` hooks share a 1.5-second budget, so the hook spawns a detached worker and returns
at once. Records are upserted by `session_id`, so re-reading a transcript never duplicates one.

## Reading it

```sh
bin/harness usage                      # last 30 days, grouped by day
bin/harness usage --days 7 --by repo
bin/harness usage --by model           # a session using two models groups under both, joined
bin/harness usage --rescan             # re-read transcripts in the window first, then report
```

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
