# Exporting the ledger

The usage ledger is a local JSONL file and that is deliberate: it is written before anything is
sent anywhere, it survives a backend being down, and it can be re-read. Export is a copy of it,
for dashboards, SQL and a team view. It is **off by default**; with it off no network code runs
and the hook behaves exactly as it did before this existed.

**The model, in one line: the ledger is the record, a backend is a rebuildable copy of it.** Most
backends expire data by default — the reference endpoint this was tested against ships a 30-day
TTL — so history outside the retention window lives in the ledger and is put back by replay.

What is recorded, and where it comes from, is [usage.md](usage.md).

## Turning it on

```json
{
  "telemetry": {
    "export": "otlp",
    "endpoint": "http://localhost:4318",
    "headers_env": "HARNESS_OTLP_HEADERS",
    "headers_file": "~/.config/agent-harness/otlp-headers",
    "labels": { "deployment.environment": "laptop" }
  }
}
```

- `export` is `off` or `otlp`. Any other value stops `harness sync` rather than silently
  exporting nothing.
- `endpoint` is the base URL of **any OTLP/HTTP endpoint**; `/v1/logs` is appended. No vendor is
  required and none is named in the code.
- `labels` are attributes added to every record — the place for an environment or a host name.
- `native` asks each runtime to export **its own** telemetry to the same endpoint. Off by
  default, and a separate decision from `export`: see [Native pass-through](#native-pass-through)
  before turning it on, because the runtimes attach identifiers the ledger does not.

`harness doctor` prints one line for this: the mode, the endpoint's scheme and host, and the
**names** of the headers it resolved.

## Credentials

Headers are read from the named environment variable or the named file and from nowhere else. A
header value written into `config.json` is refused by name, because a configuration file is
backed up, synced and read by every tool that reads the config.

```sh
export HARNESS_OTLP_HEADERS='authorization=<token>,x-scope-orgid=<tenant>'
```

Both forms are accepted, in the variable and in the file: `name=value` per line, or the
comma-separated `name=value` list that `OTEL_EXPORTER_OTLP_HEADERS` uses.

A `headers_file` is refused, with the reason, when it is **inside a git work tree** — one
`git add -A` from being published — or when it is **readable by other users**. Create it at mode
600 outside every repository:

```sh
install -m 600 /dev/null ~/.config/agent-harness/otlp-headers
```

No header value is ever printed, logged or written to an error record. A failure record names
only the endpoint's scheme and host, since a path or a query string can itself carry a token.

## What is sent

One OTLP log record per ledger row, `POST <endpoint>/v1/logs`, `Content-Type: application/json`,
using the standard library only. Logs rather than metrics: a row is an after-the-fact summary
that carries its own timestamps.

- `timeUnixNano` is the row's `ended`, `observedTimeUnixNano` is the moment it was sent. Both are
  decimal **strings**, as the OTLP/JSON mapping requires of a 64-bit integer — so an integer
  attribute travels as `{"intValue": "200"}`, not as a JSON number.
- The **body** is the whole row as a JSON string, so nothing is lost in translation.
- **Attributes** are the row's flat scalar fields — a null is omitted rather than sent as empty —
  plus `harness.row_key`, `harness.version`, one `harness.<dimension>` per recorded stance, and
  any configured labels. A nested map (`days`, `by_model`, `rules`, `counts`) stays in the body:
  attribute sets are flat, and a hundred per-day slices would be a hundred columns.
- Resource attributes are `service.name=agent-harness` and the harness version.

`harness.row_key` is the row's identity — session id, runtime, kind, agent id — and is stable
across replays. It is what a reader de-duplicates on.

## Where it runs, and what a dead endpoint costs

Export happens in the **detached worker** the `SessionEnd` hook spawns, after the row is already
in the ledger. One attempt, a two-second timeout, no retry. A collector that is down, slow or
misconfigured costs one line in `~/.local/state/agent-harness/usage.errors.jsonl` — the time, the
error class, the row count and the endpoint's host — and changes neither the hook's exit status
nor the session's.

## Replay

```sh
bin/harness usage export --since 2026-09-01                    # everything since that day
bin/harness usage export --since 2026-09-01 --until 2026-09-07 # one week
bin/harness usage export --since 2026-09-01 --dry-run          # count it, connect to nothing
```

Rows are re-sent in batches; the command prints how many were sent and how many failed, and
exits non-zero if any batch failed. Failures stay in the errors file and the same window can be
re-run. This is how a backend is backfilled after it is created, rebuilt after it is lost, and
repaired after an outage — the capability a live runtime telemetry stream does not have.

## Native pass-through

The ledger is one row per session, written after the fact. Each runtime can also export its own
live telemetry — Claude Code counts tokens by type and reports a dollar figure per API call;
Codex counts tokens, turn cost, tool calls and API calls. `"native": true` makes `harness sync`
write that configuration, pointing both runtimes at the same `endpoint`. It is off by default
and turning it on is a decision to read the two warnings below first.

```json
{ "telemetry": { "export": "otlp", "endpoint": "http://localhost:4318",
                 "headers_file": "~/.config/agent-harness/otlp-headers", "native": true } }
```

**Read this before pointing it at a hosted endpoint.** Both runtimes attach identifiers the
ledger export never sends. Claude Code puts `user.email`, `user.account_uuid`, `user.account_id`,
`user.id`, `organization.id` and `session.id` on its datapoints; its own switches trim some of
them — `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` and `OTEL_METRICS_INCLUDE_SESSION_ID` both default to
`true`, `OTEL_METRICS_INCLUDE_VERSION`, `OTEL_METRICS_INCLUDE_ENTRYPOINT` and
`OTEL_METRICS_INCLUDE_REPOSITORY` to `false`. The harness sets none of them, so adding one to
`env` yourself is yours to keep: `sync` owns the six variables below and no others. Prompt and
response logging stays at each runtime's default, which is off.

### What `sync` writes

**Claude Code**, in `env` in `~/.claude/settings.json`: `CLAUDE_CODE_ENABLE_TELEMETRY=1`,
`OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`,
`OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT` set to the base URL,
and `OTEL_RESOURCE_ATTRIBUTES` carrying `harness.version` and one `harness.<dimension>` per
resolved stance, plus the configured `labels`. With a header source configured it also sets
`otelHeadersHelper` to `~/.claude/hooks/harness/otel-headers.py`, which reads the same file or
variable the exporter reads and prints a JSON object of headers; the runtime re-runs it about
every 29 minutes. No header value is written into the settings file. A variable reaches the
helper only if it reached the runtime that spawned it, so `headers_file` is the source that
works for a desktop-launched client.

**Codex**, in `[otel]` in `~/.codex/config.toml`: `exporter` and `metrics_exporter`, both
`otlp-http` with `protocol = "binary"` and the signal-specific URLs `<endpoint>/v1/logs` and
`<endpoint>/v1/metrics`. Both are set on purpose. `metrics_exporter` defaults to Codex's own
first-party sink, and its source keeps an exact-name list of metrics that sink drops
client-side — token usage, turn cost, tool calls, API calls — under the comment *"Metrics
intentionally not sent through Codex's built-in Statsig route. Keep this as an exact-name list
so custom OTLP exporters still receive them."* Setting only `exporter` therefore sends no token
metrics anywhere.

**Codex gets no headers and no labels, and this is a real gap.** `[otel]` takes a literal header
map in `config.toml` and offers no environment or command indirection for it, so writing one
would put a credential in a configuration file — exactly what the rules above refuse. Native
Codex export needs an endpoint that accepts unauthenticated traffic from this machine, or one
fronted by something the user authenticates. There is also no config key for metric labels:
Codex builds its resource with the SDK's default builder, so `OTEL_RESOURCE_ATTRIBUTES` from the
process environment is honoured, but `sync` cannot put it there, and a Codex launched from a
desktop or an editor may inherit no shell environment at all. *Unverified:* both statements come
from the configuration reference and a source read, not from a run.

### Labels are frozen at sync time

They are computed when `sync` runs, not per session. Switch a stance without re-syncing and the
native stream is labelled with the old variant until the next `sync` — **the ledger row is still
right**, because it records the stances the session actually ran under. `harness doctor` says
whether the written labels match the current version and stances. A label whose name or value
carries a comma, an equals sign or whitespace cannot travel in `OTEL_RESOURCE_ATTRIBUTES`, which
has no escape the runtimes agree on: it is left off the native labels, named in the output of
`sync` and `doctor`, and still sent with the ledger export.

### What ownership means here

`sync` records every key it writes, so it can update it and take it back out.

- **A variable you set is never touched.** Ownership is per variable, not over `env`.
- **A managed key already holding something the harness did not write is left alone and
  reported**, in `sync` and in `doctor`. Remove it to let `sync` manage it. A key already holding
  exactly what the harness would write is taken over, since there is nothing to lose.
- **`"native": false` puts back what each key held before**, and removes the rest. An empty
  `"env": {}` can remain where the harness created the map; it is inert.
- `harness sync --dry-run` prints the pass-through lines only when the key is on.

## De-duplicating an at-least-once stream

A replay re-sends rows the backend may already hold, so read the newest record per key rather
than counting rows. In a ClickHouse-style schema, where OTLP log attributes land in a
`LogAttributes` map:

```sql
SELECT
    LogAttributes['harness.row_key'] AS row_key,
    argMax(Body, ObservedTimestamp)  AS row
FROM otel_logs
WHERE ServiceName = 'agent-harness'
  AND Timestamp >= now() - INTERVAL 30 DAY
GROUP BY row_key
```

The same shape works anywhere: group by `harness.row_key`, keep the record with the greatest
observed time. Because a replay carries the row as it stands in the ledger **now**, the newest
copy is also the corrected one when a `--rescan` has since improved it.
