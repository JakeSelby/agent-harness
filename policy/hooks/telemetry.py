#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional OTLP/HTTP export of usage ledger rows. Off unless `config.json` turns it on.

The ledger is the record and a backend is a rebuildable copy of it: every row is written to
`usage.jsonl` first, and only then offered to an endpoint from the detached worker, where a
slow or dead collector cannot reach the session. Delivery is at-least-once by design, so a
reader de-duplicates on `harness.row_key`; `harness usage export --since` replays a window.

This module sits beside `usage-log.py` rather than in `lib/harness_core` because the hook is
also a standalone script: it is reached through `~/.claude/hooks/harness`, which resolves to
the checkout's hook directory and to nothing above it. `usage-log.py` loads it with the same
`sibling()` resolver it loads the detectors with, and a copy running away from it exports
nothing rather than failing the session.

Nothing here ever logs, prints or records a header value. See docs/telemetry.md.
"""
import calendar
import json
import os
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# SessionEnd already ran by the time the worker exports, so the budget here is the user's
# patience on the next command, not the hook's. One attempt, no retry: the ledger still holds
# the row, and `harness usage export --since` is the recovery path.
TIMEOUT = 2.0

# A batch is bounded twice: by rows, so a replay of a month is many modest requests rather than
# one enormous one, and by bytes, because a single row carrying a large `rules` map can be tens
# of kilobytes and collectors refuse oversized bodies.
MAX_ROWS = 100
MAX_BYTES = 1 << 20

SERVICE_NAME = "agent-harness"
SEVERITY_NUMBER = 9  # INFO, per the OTLP logs data model.

# `native` is accepted and ignored here: runtime pass-through writes a runtime's own telemetry
# settings and is not this exporter's business.
KNOWN_KEYS = ("export", "endpoint", "headers_env", "headers_file", "labels", "native")
DEFAULT_ENDPOINT = "http://localhost:4318"


def home():
    return Path(os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or Path.home())


def config_path():
    return home() / ".config" / "agent-harness" / "config.json"


def read_config(path=None):
    try:
        with open(str(path or config_path()), encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def settings(cfg=None, path=None):
    """The validated `telemetry` block, or `{"export": "off"}` when there is none.

    Raises `ValueError` on a block that cannot be honoured, so the CLI can refuse loudly while
    the hook stays silent: a mistyped endpoint should stop a sync, never a session.
    """
    cfg = read_config(path) if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if block is None:
        return {"export": "off"}
    if not isinstance(block, dict):
        raise ValueError("telemetry must be an object")
    unknown = sorted(set(block) - set(KNOWN_KEYS))
    if unknown:
        # A header value in the config is the one typo worth naming: it would put a credential
        # in a file that is backed up, synced and read by every tool that reads the config.
        if any(k in ("headers", "header", "authorization") for k in unknown):
            raise ValueError(
                "telemetry headers must be read from headers_env or headers_file; a header "
                "value in config.json is a credential in a configuration file")
        raise ValueError("telemetry does not take " + ", ".join(unknown))
    mode = block.get("export", "off")
    if mode not in ("off", "otlp"):
        raise ValueError("telemetry.export must be \"off\" or \"otlp\"; got " + repr(mode))
    endpoint = block.get("endpoint") or DEFAULT_ENDPOINT
    if not isinstance(endpoint, str) or not endpoint.startswith(("http://", "https://")):
        raise ValueError("telemetry.endpoint must be an http:// or https:// URL")
    headers_env = block.get("headers_env") or ""
    if not isinstance(headers_env, str):
        raise ValueError("telemetry.headers_env must be the name of an environment variable")
    if "=" in headers_env:
        raise ValueError(
            "telemetry.headers_env names an environment variable to read headers from; it is "
            "not the headers themselves")
    headers_file = block.get("headers_file") or ""
    if not isinstance(headers_file, str):
        raise ValueError("telemetry.headers_file must be a path")
    labels = block.get("labels") or {}
    if not isinstance(labels, dict) or any(not isinstance(v, (str, int, float, bool)) for v in labels.values()):
        raise ValueError("telemetry.labels must be an object of scalar values")
    return {"export": mode, "endpoint": endpoint.rstrip("/"), "headers_env": headers_env,
            "headers_file": headers_file, "labels": dict(labels)}


def parse_headers(text):
    """`name=value` per line, or the comma-separated form `OTEL_EXPORTER_OTLP_HEADERS` uses."""
    out = {}
    for line in str(text or "").replace(",", "\n").splitlines():
        item = line.strip()
        if not item:
            continue
        name, sep, value = item.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not name or any(c.isspace() for c in name):
            raise ValueError("a telemetry header must read name=value")
        out[name] = value
    return out


def _in_git_work_tree(path):
    for parent in Path(path).resolve().parents:
        if (parent / ".git").exists():
            return True
    return False


def headers_from_file(path):
    """Headers from a file that is outside every work tree and unreadable by other users.

    A credential inside a repository is one `git add -A` from being published, and one that
    any account on the machine can read is not a secret. Neither the value nor the file's text
    appears in the refusal.
    """
    target = Path(path).expanduser()
    try:
        mode = target.stat().st_mode
    except OSError:
        raise ValueError("telemetry.headers_file {} cannot be read".format(target))
    if not stat.S_ISREG(mode):
        raise ValueError("telemetry.headers_file {} is not a regular file".format(target))
    if _in_git_work_tree(target):
        raise ValueError(
            "telemetry.headers_file {} is inside a git work tree; keep the credential outside "
            "every repository".format(target))
    if stat.S_IMODE(mode) & 0o007:
        raise ValueError(
            "telemetry.headers_file {} is readable by other users; `chmod 600` it".format(target))
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        raise ValueError("telemetry.headers_file {} cannot be read".format(target))
    return parse_headers(text)


def headers(config, env=None):
    """The request headers, from the named environment variable and file and nowhere else."""
    env = os.environ if env is None else env
    out = {}
    name = config.get("headers_env") or ""
    if name:
        raw = env.get(name)
        if raw is None:
            raise ValueError("telemetry.headers_env names ${}, which is not set".format(name))
        out.update(parse_headers(raw))
    if config.get("headers_file"):
        out.update(headers_from_file(config["headers_file"]))
    return out


# ------------------------------------------------------------------ the OTLP/JSON payload


def row_key(row):
    """The stable identity of a row: the tuple `usage-log.py`'s `row_key` upserts on, as text.

    A replay re-sends the same string for the same row, which is what lets a backend
    de-duplicate an at-least-once stream.
    """
    return "|".join(str(row.get(k) or d) for k, d in (
        ("session_id", ""), ("runtime", "claude-code"), ("kind", "session"), ("agent_id", "")))


def _nanos(stamp):
    """Epoch nanoseconds for a ledger timestamp, or None when it will not parse."""
    if not isinstance(stamp, str) or not stamp:
        return None
    text = stamp.replace("Z", "").split(".")[0]
    try:
        parsed = time.strptime(text, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    try:
        return int(calendar.timegm(parsed)) * 1000000000
    except (OverflowError, ValueError):
        return None


def any_value(value):
    """One OTLP `AnyValue`. Ints travel as decimal strings, which the JSON mapping requires."""
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def attributes(row, config=None, version=""):
    """The row's flat scalars, its stances, its key and the configured labels.

    A nested map — `days`, `by_model`, `rules`, `counts` — travels in the body only: attribute
    sets are flat, and flattening a hundred per-day slices into attribute names would make
    every row a new column in a backend. `stances` is the exception, because a stance is a
    dimension a report groups by: it flattens to one `harness.<dimension>` each.
    """
    out = {}
    for key, value in sorted(row.items()):
        if value is None or key == "stances":
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
    for dimension, variant in sorted((row.get("stances") or {}).items()):
        if isinstance(variant, (str, int, float, bool)):
            out["harness." + str(dimension)] = variant
    out["harness.row_key"] = row_key(row)
    stamped = row.get("harness_version") or version
    if stamped:
        out["harness.version"] = stamped
    for key, value in sorted(((config or {}).get("labels") or {}).items()):
        out[str(key)] = value
    return [{"key": k, "value": any_value(v)} for k, v in sorted(out.items())]


def log_record(row, config=None, version="", now=None):
    now_nanos = int((time.time() if now is None else now) * 1000000000)
    return {
        "timeUnixNano": str(_nanos(row.get("ended")) or now_nanos),
        "observedTimeUnixNano": str(now_nanos),
        "severityNumber": SEVERITY_NUMBER,
        "severityText": "INFO",
        "body": {"stringValue": json.dumps(row, sort_keys=True)},
        "attributes": attributes(row, config, version),
    }


def payload(rows, config=None, version="", now=None):
    resource = [{"key": "service.name", "value": {"stringValue": SERVICE_NAME}}]
    if version:
        resource.append({"key": "service.version", "value": {"stringValue": version}})
    return {"resourceLogs": [{
        "resource": {"attributes": resource},
        "scopeLogs": [{"scope": {"name": SERVICE_NAME},
                       "logRecords": [log_record(r, config, version, now) for r in rows]}],
    }]}


def batches(rows, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Rows grouped into requests, bounded by count and by encoded size."""
    batch, size = [], 0
    for row in rows:
        cost = len(json.dumps(row)) + 2048  # the row's body plus room for its attributes
        if batch and (len(batch) >= max_rows or size + cost > max_bytes):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += cost
    if batch:
        yield batch


# ------------------------------------------------------------------ delivery


def endpoint_label(endpoint):
    """Scheme and host only. A path or a query can carry a token; neither is ever recorded."""
    try:
        parts = urllib.parse.urlsplit(endpoint)
        host = parts.hostname or ""
        if parts.port:
            host = "{}:{}".format(host, parts.port)
        return "{}://{}".format(parts.scheme, host)
    except Exception:
        return ""


def post(rows, config, request_headers, version="", timeout=TIMEOUT, opener=None):
    """POST one batch. Raises on transport or status failure; the caller records the class."""
    url = config["endpoint"]
    if not url.endswith("/v1/logs"):
        url = url + "/v1/logs"
    body = json.dumps(payload(rows, config, version)).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for name, value in request_headers.items():
        request.add_header(name, value)
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            response.read()
    except urllib.error.HTTPError as exc:
        # An HTTPError is also the response, and holds a socket until it is closed.
        exc.close()
        raise
    if not 200 <= int(status) < 300:
        raise urllib.error.HTTPError(url, int(status), "OTLP export rejected", None, None)
    return len(rows)


def record_failure(path, endpoint, error, rows):
    """One line in the existing errors file: when, what class, how many rows, which host."""
    if not path:
        return
    entry = {"time": time.time(), "error": type(error).__name__, "action": "otlp-export",
             "endpoint": endpoint_label(endpoint), "rows": rows}
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def export_rows(rows, config=None, env=None, version="", errors_path=None,
                timeout=TIMEOUT, opener=None, dry_run=False):
    """Send rows to the configured endpoint. Returns `(sent, failed)` and never raises.

    With export off this opens no socket and reads no credential: the first check is the mode,
    so a machine that has not turned export on behaves exactly as it did before it existed.
    """
    rows = [r for r in rows if isinstance(r, dict)]
    try:
        config = settings() if config is None else config
    except ValueError as exc:
        record_failure(errors_path, "", exc, len(rows))
        return 0, len(rows)
    if config.get("export") != "otlp" or not rows:
        return 0, 0
    try:
        request_headers = headers(config, env)
    except ValueError as exc:
        record_failure(errors_path, config.get("endpoint", ""), exc, len(rows))
        return 0, len(rows)
    sent = failed = 0
    for batch in batches(rows):
        if dry_run:
            sent += len(batch)
            continue
        try:
            sent += post(batch, config, request_headers, version, timeout, opener)
        except Exception as exc:
            failed += len(batch)
            record_failure(errors_path, config.get("endpoint", ""), exc, len(batch))
    return sent, failed
