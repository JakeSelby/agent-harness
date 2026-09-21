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

## Reference recipe: ClickStack

`endpoint` takes **any** OTLP/HTTP endpoint. This is one backend that was set up and measured
end to end, written down so the first person to point the exporter somewhere real does not have
to rediscover the setup steps. It is an example, not a requirement and not an endorsement:
anything that speaks OTLP/HTTP works, and nothing in the harness names a vendor.

ClickStack is the ClickHouse observability stack — a HyperDX UI over ClickHouse, fed by an
OpenTelemetry Collector. The all-in-one image runs the three of them in one container, which is
why it suits a laptop.

### Run it

```bash
docker run -d --name clickstack -p 8080:8080 -p 4317:4317 -p 4318:4318 -v clickstack-db:/data/db -v clickstack-ch:/var/lib/clickhouse -v clickstack-chlogs:/var/log/clickhouse-server clickhouse/clickstack-all-in-one
```

8080 is the UI and the HTTP API, 4317 is OTLP/gRPC and 4318 is OTLP/HTTP — the port the
`endpoint` above points at. The three volumes are the whole of the state: `/data/db` is the
MongoDB that holds the user, the team and the ingestion key, and the other two are ClickHouse's
data and logs. **The volumes are what persists**, not the container: after a `docker restart`,
and again after the container was removed and a fresh one run on the same three volumes, the
data was intact and the same ingestion key was still accepted, because the account and the key
live in `/data/db`. Without them a recreated container starts empty and the key is regenerated.
Measured idle on one laptop: about 795 MiB resident, about 1.5 GiB shortly after ingest.

This recipe deliberately contains no command that creates an account, writes down a password, or
removes a container or a volume. The first is a browser step, the second belongs in a file only
you can read, and the third is destructive and yours to type.

### Two manual steps before any data is accepted

**First, create the first user** in the UI at `http://localhost:8080`. The OTLP receivers on
4317 and 4318 stay closed until that account exists, because the collector is waiting on its
configuration from the app. Until then an exporter sees a connection that refuses to talk, and
nothing in the harness's error record will explain why.

**Second, send the team's ingestion key** — shown in the UI under the team settings — as a bare
`authorization` header on every request. It is the key on its own, with no `Bearer` prefix.
Without it the receiver answers:

```text
401 missing or empty authorization header: Authorization
```

So `headers_file` is not optional for this backend. One mode-600 file outside every repository
serves both directions of the integration: the ledger exporter reads it as `headers_file`, and
with `"native": true` the `otelHeadersHelper` script reads the same file for Claude Code.

```bash
printf 'authorization=%s\n' '<ingestion-key>' > ~/.config/agent-harness/otlp-headers
```

Create the file at mode 600 first, as under [Credentials](#credentials); the shell redirect above
does not change an existing file's mode.

**Codex cannot use this backend through `sync`.** `[otel]` takes header values only as literals
in `config.toml`, so there is no way to give Codex the key without writing it into a
configuration file — see [Native pass-through](#native-pass-through), which states that gap and
what it costs. Claude Code's native export is unaffected, and so is the ledger exporter.

Native Claude Code export also carries `user.email`, the account and organization ids and the
session id on every datapoint. On a container bound to localhost that is your own machine
talking to itself; read the warning under [Native pass-through](#native-pass-through) before
pointing the same configuration at anything hosted.

### Retention is 30 days by default

Every OpenTelemetry table the collector creates ships with its own 30-day TTL. Ten tables
carried one on the image measured: the logs and traces tables, the five metrics tables, the two
`*_kv_rollup_15m` rollups and `hyperdx_sessions`. This is the ledger-as-record argument made
concrete: the backend forgets, and `harness usage export --since <date>` puts the window back.

List what is actually there, with the TTL each table carries, rather than trusting a list in a
document:

```sql
SELECT name, engine FROM system.tables WHERE database = 'default' AND create_table_query LIKE '%TTL%' ORDER BY name
```

Then raise each one you care about. The TTL expression names that table's own time column — the
log and trace tables use `Timestamp`, the metric tables use `TimeUnix` — so copy the expression
out of the table's own `create_table_query` and change only the interval:

```sql
ALTER TABLE default.otel_logs MODIFY TTL toDateTime(Timestamp) + toIntervalDay(365)
```

A `MODIFY TTL` on a table that already holds data schedules a materialization; it does not
resurrect parts that have already expired.

### The dashboard

[`telemetry/clickstack-dashboard-native-cost.json`](telemetry/clickstack-dashboard-native-cost.json)
is ten tiles of raw SQL over `otel_metrics_sum`, reading the native Claude Code cost and token
metrics: spend, sessions, the subagent share of spend, cache hit rate, spend over time by model
and by harness version, spend by agent × model × effort, spend by cost variant and delegation
stance, tokens by type, and the most expensive sessions. The SQL is this repository's own, over
the standard OpenTelemetry tables; no dashboard, query or documentation is copied from the
upstream project.

The HTTP API answers under `/api/api/v2/` on the **UI** port, not the OTLP port — the doubled
`api` is not a typo. Send `/api/v2/...` instead and the proxy strips one `/api`, leaving the
backend to answer `404 Cannot GET /v2/dashboards`.

**The API key and the ingestion key are two different secrets.** The ingestion key is sent as a
bare `authorization` header to the OTLP ports; the HTTP API takes a *personal API key*, created
separately in the UI, as `Authorization: Bearer <key>` on the UI port. Neither works in the
other's place. Keep the API key in its own mode-600 file outside every repository and read it
inside the header argument rather than exporting it into the environment.

Each tile carries a `connectionId`, which is instance-specific and ships as the placeholder
`REPLACE_WITH_CONNECTION_ID`. Look yours up:

```bash
curl -s http://localhost:8080/api/api/v2/connections -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)"
```

Substitute it, keeping the original file intact:

```bash
sed 's/REPLACE_WITH_CONNECTION_ID/<connection-id>/g' docs/telemetry/clickstack-dashboard-native-cost.json > "$HOME/clickstack-dashboard.json"
```

Dry-run it before creating anything; a good definition comes back as
`{"valid": true, "errors": [], "normalized": …}`:

```bash
curl -s -X POST http://localhost:8080/api/api/v2/dashboards/validate -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)" -H 'content-type: application/json' --data-binary "@$HOME/clickstack-dashboard.json"
```

Then create it:

```bash
curl -s -X POST http://localhost:8080/api/api/v2/dashboards -H "Authorization: Bearer $(cat ~/.config/agent-harness/clickstack-api-key)" -H 'content-type: application/json' --data-binary "@$HOME/clickstack-dashboard.json"
```

### Licences, and what this repository ships

The HyperDX app is MIT. ClickHouse and the OpenTelemetry Collector are Apache-2.0. The all-in-one
image also contains MongoDB, which is under the SSPL — a licence this project would not ship
under, and does not need to, because you download the image from its publisher. This repository
distributes none of it, vendors none of it, and copies none of its dashboards or documentation.
Read the image's own terms before running it anywhere but your own machine.
