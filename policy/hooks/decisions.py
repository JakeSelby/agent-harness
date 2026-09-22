#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The decision log: one local, append-only record per judgment a harness hook makes.

`~/.local/state/agent-harness/decisions.jsonl`, beside `usage.jsonl`. The ledger says what a
session spent; this says what the harness decided and, where the session later showed it, how
the decision turned out. Nothing here reaches the network, nothing here is model-visible, and
no row is ever rewritten: an outcome is a second record joined to the first by `decision_id`,
so a reader of the file sees the decision exactly as the hook made it.

    {"kind": "decision", "decision_id": "…", "point": "grade-bash", "session_id": "…",
     "ts": "2026-09-21T18:04:05Z", "input_sha256": "…", "input": "git push --force",
     "deterministic_answer": "ask", "outcome": null, "runtime": "claude-code",
     "harness_version": "0.12.0"}
    {"kind": "outcome", "decision_id": "…", "point": "grade-bash", "session_id": "…",
     "ts": "…", "outcome": "ran", "harness_version": "0.12.0"}

`input` is the text the hook judged, capped at MAX_INPUT (2 KiB) — a command or a brief, never
tool output and never assistant prose. `input_sha256` is over the **uncapped** text, so two
rows whose capped text is identical are still told apart, and a long command can be matched
against its own later events.

This module sits beside the hooks rather than in `lib/harness_core`, for the reason
`telemetry.py` gives: a hook is reached through `~/.claude/hooks/harness` and nothing above
that directory resolves from it. `lifecycle.py` loads it with its own `load()`.

Every write is wrapped: a logging failure counts in `errors()` and changes no hook's decision,
output or exit status. See docs/usage.md for the report and docs/telemetry.md for the switch.
"""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

# The points that write. Named here so the report can list a point that has not fired yet, and
# so a typo in a call site is a test failure rather than a silent new group.
POINTS = ("grade-bash", "stop-gate", "tier-agent-spawns", "brief-guard", "evasion-deny")

# 2 KiB. Far past any command or the head of a brief, and small enough that a session's worth of
# rows stays a file a person can read. The hash is over the uncapped text, so the cap loses
# evidence, never identity.
MAX_INPUT = 2048

# A Bash ask with no matching PostToolUse by the end of the session. Not "denied": a user who
# refused, a user who interrupted the turn and a session that crashed all look the same here,
# and naming one of them would put a label in the file that nobody measured.
NOT_RUN = "not_run"
RAN = "ran"

_CONFIG = []
_ERRORS = [0]


def home():
    return Path(os.environ.get("HARNESS_HOME") or os.environ.get("HOME") or Path.home())


def state_dir():
    return home() / ".local" / "state" / "agent-harness"


def path():
    return state_dir() / "decisions.jsonl"


def config_path():
    return home() / ".config" / "agent-harness" / "config.json"


def read_config():
    """The user's config, read at most once per process. `{}` when there is none to read."""
    if not _CONFIG:
        try:
            with open(str(config_path()), encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, ValueError):
            data = {}
        _CONFIG.append(data if isinstance(data, dict) else {})
    return _CONFIG[0]


def enabled(cfg=None):
    """Whether decisions are logged: `telemetry.decisions`, which defaults to on.

    Collection is local and on by default, like the usage ledger it sits beside, because the
    labels are only worth having from the day the hook starts writing them. `false` turns it
    off and the harness writes nothing at all — no file, no directory. A `telemetry` block that
    is not an object is a configuration nobody can honour, and writes nothing either.
    """
    cfg = read_config() if cfg is None else cfg
    block = cfg.get("telemetry") if isinstance(cfg, dict) else None
    if block is None:
        return True
    if not isinstance(block, dict):
        return False
    return block.get("decisions", True) is True


def errors():
    """How many writes this process swallowed. A hook's decision never depends on it."""
    return _ERRORS[0]


def now_ts(now=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))


def digest(text):
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()


def harness_version():
    """The version in the `VERSION` file at the root of the checkout this file belongs to.

    The same walk `usage-log.py` does, and for the same reason: a hook is a script, not an
    import of the CLI. A copy running outside a checkout stamps no version rather than a guess.
    """
    here = Path(os.path.realpath(__file__)).parent
    for parent in [here] + list(here.parents):
        marker = parent / "VERSION"
        if marker.is_file() and (parent / "bin" / "harness").exists():
            try:
                return marker.read_text(encoding="utf-8").strip() or None
            except OSError:
                return None
    return None


def match_key(event, text):
    """The identity a later event re-derives to find this decision again.

    The tool-use id when the runtime's payload carries one — neither adapter's does today, and
    both pass the payload through `lifecycle.normalize()` untouched, so if one starts carrying
    it both sides of the join gain it at once — and otherwise the session and the hash of the
    text the hook judged. Two identical commands in one session share a key, which joins the
    same outcome to both rather than to neither.
    """
    event = event if isinstance(event, dict) else {}
    for name in ("tool_use_id", "call_id"):
        value = event.get(name)
        if isinstance(value, str) and value:
            return value
    return str(event.get("session_id") or "") + ":" + digest(text)


def decision_id(point, key):
    """The reproducible id of a decision at `point` over `key`. See `match_key`."""
    return digest(point + "|" + key)[:32]


# How much of the tail an arriving event reads to find out whether its decision was logged. A
# decision made seconds ago is at the end of the file, and a bounded read is what keeps a
# PostToolUse hook's cost flat as the log grows.
TAIL_BYTES = 256 * 1024


def tail_text(target=None, limit=TAIL_BYTES):
    """The last `limit` bytes of the log as text, or "" when there is nothing to read."""
    target = Path(target) if target else path()
    try:
        with open(str(target), "rb") as stream:
            try:
                stream.seek(-limit, os.SEEK_END)
            except OSError:
                stream.seek(0)
            return stream.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _append(row, target=None):
    """One line, one `write`. Appending is the only way this file is ever changed."""
    target = Path(target) if target else path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(target.parent), 0o700)
    except OSError:
        pass
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return target


def record(point, answer, text="", event=None, runtime="", key=None, target=None, now=None):
    """Log one judgment. Returns its `decision_id`, or None when nothing was written.

    Never raises. A failed write is counted and the caller carries on with the decision it had
    already made: a log that can change a permission answer is worse than no log.

    `key` makes the id reproducible, so an event that arrives later can name this decision
    without having read the file; with none, the id is a fresh one nobody will join to.
    """
    try:
        if not enabled():
            return None
        text = text if isinstance(text, str) else ""
        identity = uuid.uuid4().hex if key is None else decision_id(point, key)
        row = {"kind": "decision", "decision_id": identity, "point": point,
               "session_id": str((event or {}).get("session_id") or "") if event else "",
               "ts": now_ts(now), "input_sha256": digest(text), "input": text[:MAX_INPUT],
               "deterministic_answer": answer, "outcome": None,
               "runtime": runtime or os.environ.get("HARNESS_RUNTIME", ""),
               "harness_version": harness_version()}
        _append(row, target)
        return identity
    except Exception:
        _ERRORS[0] += 1
        return None


def observe(decision_id, outcome, point="", session_id="", target=None, now=None):
    """Log the outcome of an earlier decision. Never raises; returns whether a line was written.

    The decision row keeps its `null`. An outcome is its own record, and a reader joins them.
    """
    try:
        if not decision_id or not enabled():
            return False
        _append({"kind": "outcome", "decision_id": decision_id, "point": point,
                 "session_id": str(session_id or ""), "ts": now_ts(now), "outcome": outcome,
                 "harness_version": harness_version()}, target)
        return True
    except Exception:
        _ERRORS[0] += 1
        return False


def observe_if_logged(identity, outcome, point="", session_id="", target=None, now=None):
    """Log an outcome only for a decision this log actually holds. Never raises.

    Most events that could carry an outcome follow no decision at all — the harness answers the
    permission question on a small minority of Bash calls — and an outcome with nothing to join
    to would be both a wrong count and a file that grows with every tool call. The tail read is
    bounded; a decision older than the tail goes unlabelled, which the report shows as such.
    """
    try:
        if not identity or not enabled():
            return False
        if identity not in tail_text(target):
            return False
    except Exception:
        _ERRORS[0] += 1
        return False
    return observe(identity, outcome, point, session_id, target, now)


def read_rows(target=None):
    """Every well-formed record in the log, oldest first. An unreadable file is no rows."""
    target = Path(target) if target else path()
    rows = []
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("decision_id"):
            rows.append(row)
    return rows


def joined(rows):
    """Decision rows with their outcome filled in, oldest first.

    The first outcome recorded for a `decision_id` is the one that holds: a second record for
    the same decision is a duplicate event, not a change of mind, and an append-only file has
    no way to say the earlier one was wrong.
    """
    outcomes = {}
    for row in rows:
        if row.get("kind") == "outcome" and row["decision_id"] not in outcomes:
            outcomes[row["decision_id"]] = row.get("outcome")
    out = []
    for row in rows:
        if row.get("kind") == "outcome":
            continue
        result = row.get("outcome")
        if result is None:
            result = outcomes.get(row["decision_id"])
        out.append(dict(row, outcome=result))
    return out


def close_session(session_id, points=("grade-bash",), outcome=NOT_RUN, target=None, now=None):
    """Label this session's unanswered decisions at SessionEnd. Returns how many were labelled.

    A Bash ask whose PostToolUse never arrived is the session's answer to it, and the session
    is over: nothing else will ever arrive. Only the points whose outcome is observed this way
    are closed, so a decision that is simply not labelled yet stays unlabelled and shows up in
    the report's unlabelled share rather than as a fabricated result.
    """
    try:
        if not session_id or not enabled():
            return 0
        rows = read_rows(target)
        answered = set(r["decision_id"] for r in rows if r.get("kind") == "outcome")
        closed = 0
        for row in rows:
            if row.get("kind") == "outcome" or row.get("session_id") != session_id:
                continue
            if row.get("point") not in points or row["decision_id"] in answered:
                continue
            answered.add(row["decision_id"])
            if observe(row["decision_id"], outcome, row.get("point") or "", session_id,
                       target, now):
                closed += 1
        return closed
    except Exception:
        _ERRORS[0] += 1
        return 0
