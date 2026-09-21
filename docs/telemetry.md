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
- `native` is reserved for runtime pass-through and does nothing yet.

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
