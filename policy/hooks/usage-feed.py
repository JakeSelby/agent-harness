#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Feed measured spend back to the orchestrator: one turn line, one line per finished subagent.

Four events, all on the parent thread. `SubagentStart` and `SubagentStop` record when an agent
began and what it cost. `PostToolUse` on `Agent` reports a synchronous return the moment it lands,
and says how many agents are running when that is past the posture's width. `UserPromptSubmit`
reports the turn and every subagent that finished since the previous prompt — which is how a
background spawn, whose `PostToolUse` fires at launch with no totals, is reported at all.

Five facts shape the whole file:

- **A tool response's token figure describes only the subagent's last response.** Measured on a
  live return: `tool_response.usage.output_tokens` said 3,143 against 10,575 actually spent over
  nineteen responses. The real figure is summed from the subagent's own transcript, once per
  message id at the field-wise maximum, by `usage-log.py`'s per-agent row function and not by a
  second copy of that logic here.
- **These hooks run concurrently, as separate processes.** So state is split in two. A subagent
  event is one line under 4 KB appended to `<session>.events.jsonl` through an `O_APPEND`
  descriptor, which no handler ever rewrites and which therefore cannot lose a record. Everything
  the main thread read-modify-writes lives in `<session>.json`, under an exclusive `flock` on
  `<session>.lock` with a bounded wait. No lock, no write, and nothing emitted.
- **Nothing slow happens under the lock.** `SubagentStart` and `SubagentStop` never take it at
  all, and the two main-thread events sum a subagent's transcript before acquiring it. A stop
  that took four seconds to read while holding the lock would starve the prompt waiting behind
  it, and that prompt would silently lose its line.
- **A record that cannot be computed is still a record.** A stop is journalled in a `finally`,
  with null totals when the sum failed and `partial` when a budget cut it short. An agent whose
  stop went missing would otherwise count as running for the rest of the session and the width
  line would fire falsely forever; a start with no stop also decays after three hours.
- **Reads are bounded everywhere.** The parent transcript is read from a saved offset, trusted
  only while the inode and the hash of the first record still match, and from 8 MiB before the
  end on a cold start. The journal is read from its own saved offset, so a long session's totals
  can only grow. A subagent's transcript is capped by bytes and by the clock.

No budget, threshold, model name or role name lives here: every number comes from the cost
table, every switch from `switches.turn_feed`, `switches.nudge_at` and `switches.max_parallel`.
A variant that sets none of them feeds nothing. Any failure at all emits nothing and exits 0,
and no line the feed emits is ever a decision.
"""
import errno
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - a platform with no advisory locking
    fcntl = None

HOOKS = Path(__file__).resolve().parent
PREFIX = "usage-feed: "
# A journal line is one `os.write`. Far under PIPE_BUF, which is what makes an append atomic.
MAX_LINE = 4096
# How many message ids stay open for a later line to raise. One API response is written as
# several lines repeating its id, and a response whose id is evicted before its final, largest
# figure arrives would be counted twice; a tail this long is far past that window.
OPEN_TAIL = 64
MAX_LISTED = 5
# Stops waiting for a line, and ids whose spend is already in the totals. Both bound what one
# session's state file can grow to, and both are far past any real fan-out.
MAX_PENDING = 200
MAX_COUNTED = 1000
# A cold start reads this much of the transcript's tail, not the whole file.
COLD_TAIL = 8 * 1024 * 1024
READ_BUDGET = 3.0
# What one subagent's transcript may cost a hook that has ten seconds for everything.
AGENT_BUDGET = 4.0
AGENT_BYTES = 8 * 1024 * 1024
LOCK_WAIT = 2.0
# A start with no stop this old is not running; something ended it without saying so.
RUNNING_TTL = 3 * 3600
FEED_TTL = 14 * 86400
PRUNE_EVERY = 86400
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
# What an agent type may look like before it is allowed into injected text or the journal.
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
UNNAMED = "other"
MODES = ("off", "thresholds", "every-turn")


def sibling(name):
    """A module beside this hook, or None. A feed never fails loudly over an import."""
    try:
        spec = importlib.util.spec_from_file_location(
            "harness_" + name.replace("-", "_"), str(HOOKS / (name + ".py")))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _open(path):
    """The one place the parent transcript is opened, so a test can measure what a read costs."""
    return open(str(path), "rb")


def plural(number, noun):
    """`1 tool call`, `15 tool calls`, `135,000 output tokens`. Every emitted number reads."""
    return "{:,}".format(number) + " " + noun + ("" if number == 1 else "s")


# --------------------------------------------------------------------------- paths


def home(env):
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def feed_dir(env):
    return home(env) / ".local" / "state" / "agent-harness" / "feed"


def paths(session_id, env):
    """`(state, journal, lock)` for one session, or None when the id is not a name we would write."""
    if not isinstance(session_id, str) or not IDENTIFIER.match(session_id):
        return None
    directory = feed_dir(env)
    return (directory / (session_id + ".json"), directory / (session_id + ".events.jsonl"),
            directory / (session_id + ".lock"))


def ensure_dir(directory):
    try:
        if not directory.is_dir():
            os.makedirs(str(directory), 0o700)
        return True
    except OSError:
        return directory.is_dir()


# --------------------------------------------------------------------------- the journal


def journal_append(path, record):
    """One line, one `os.write`, on an `O_APPEND` descriptor. Never read-modify-write."""
    data = (json.dumps(record, ensure_ascii=True) + "\n").encode("utf-8")
    if len(data) > MAX_LINE or not ensure_dir(path.parent):
        return False
    try:
        handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError:
        return False
    try:
        written = os.write(handle, data)
        if written == len(data):
            return True
        # A short write leaves a fragment. Terminating it is all that is owed: the reader drops
        # an unparseable line, and the next record then starts on a line of its own.
        if not data[:written].endswith(b"\n"):
            os.write(handle, b"\n")
        return False
    except OSError:
        return False
    finally:
        os.close(handle)


# --------------------------------------------------------------------------- the reader's state


def new_state():
    return {"version": 3, "offset": 0, "size": 0, "inode": None, "head": None, "partial": False,
            "session": {"output": 0, "tool_calls": 0},
            "turn": {"output": 0, "tool_calls": 0},
            "previous_turn": {"output": 0, "tool_calls": 0},
            "subagents": {"output": 0, "tool_calls": 0, "count": 0, "unknown": 0},
            "journal_offset": 0, "running": {}, "pending": [], "counted": [],
            "open": [], "pruned": 0}


def load_state(path):
    """The session's state, or a fresh one. A file we cannot read is a file we start over from."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return new_state()
    if not isinstance(data, dict) or data.get("version") != 3:
        return new_state()
    state = new_state()
    state.update(data)
    for key in ("session", "turn", "previous_turn", "subagents"):
        value = state.get(key)
        state[key] = value if isinstance(value, dict) else new_state()[key]
        for name, blank in new_state()[key].items():
            if not isinstance(state[key].get(name), int) or isinstance(state[key].get(name), bool):
                state[key][name] = blank
    for key in ("offset", "size", "journal_offset", "pruned"):
        if not isinstance(state.get(key), int) or isinstance(state.get(key), bool):
            state[key] = 0
    if not isinstance(state.get("running"), dict):
        state["running"] = {}
    for key in ("pending", "counted", "open"):
        if not isinstance(state.get(key), list):
            state[key] = []
    return state


def save_state(path, state):
    """Atomic and private. Called before the slow read as well as after it."""
    state["pending"] = state.get("pending", [])[-MAX_PENDING:]
    state["counted"] = state.get("counted", [])[-MAX_COUNTED:]
    if not ensure_dir(path.parent):
        return
    tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        handle = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(handle, json.dumps(state).encode("utf-8"))
        finally:
            os.close(handle)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


class Lock(object):
    """An exclusive `flock` with a bounded wait. Unavailable or contended means emit nothing.

    Every writer of the reader's state is a hook process with ten seconds for everything, and
    nothing slow is ever done while this is held. Waiting longer than a couple of seconds for a
    figure the next prompt will recompute anyway is worse than skipping the line.
    """

    def __init__(self, path, wait=LOCK_WAIT):
        self.path = path
        self.wait = wait
        self.handle = None

    def __enter__(self):
        if fcntl is None or not ensure_dir(self.path.parent):
            return False
        try:
            self.handle = os.open(str(self.path), os.O_WRONLY | os.O_CREAT, 0o600)
        except OSError:
            return False
        deadline = time.monotonic() + self.wait
        while True:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # A lock file is never written, so without this its age is its creation and the
                # sweep below would eventually delete the file a live session is holding.
                try:
                    os.utime(str(self.path), None)
                except OSError:
                    pass
                return True
            except (IOError, OSError) as exc:
                if getattr(exc, "errno", None) not in (errno.EACCES, errno.EAGAIN):
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
        os.close(self.handle)
        self.handle = None
        return False

    def __exit__(self, *exc):
        if self.handle is not None:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_UN)
            finally:
                os.close(self.handle)
                self.handle = None
        return False


def prune(directory, state, keep, now=None):
    """Once a day at most, drop the files of sessions nothing has touched in a fortnight.

    A session's three files go together or not at all, judged by the newest of them: a state
    file rewritten every prompt beside a journal nobody appended to for a month is one live
    session. `keep` is this session, which is never a candidate however old its files look.
    """
    now = time.time() if now is None else now
    if now - state.get("pruned", 0) < PRUNE_EVERY:
        return
    state["pruned"] = int(now)
    sessions = {}
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        stem = entry.name.split(".", 1)[0]
        if stem == keep:
            continue
        try:
            if not entry.is_file():
                continue
            sessions.setdefault(stem, []).append((entry, entry.stat().st_mtime))
        except OSError:
            continue
    for files in sessions.values():
        if now - max(mtime for _, mtime in files) <= FEED_TTL:
            continue
        for entry, _ in files:
            try:
                entry.unlink()
            except OSError:
                continue


# --------------------------------------------------------------------------- the parent transcript


def _slot(state, mid):
    """The open maximum for one message id, newest last, oldest evicted past the tail."""
    entries = state["open"]
    if mid:
        for item in entries:
            if item[0] == mid:
                return item
    item = [mid, 0, []]
    entries.append(item)
    del entries[:max(0, len(entries) - OPEN_TAIL)]
    return item


def _apply(state, entry):
    """One transcript line against the running totals. Sidechain lines belong to a subagent."""
    if not isinstance(entry, dict) or entry.get("isSidechain"):
        return
    kind = entry.get("type")
    message = entry.get("message")
    message = message if isinstance(message, dict) else {}
    if kind == "user":
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
            return
        if entry.get("isMeta") or entry.get("isCompactSummary"):
            return
        # A real prompt closes the turn. An empty one is not a turn worth remembering, so it
        # never displaces the last turn that spent anything.
        if state["turn"]["output"] or state["turn"]["tool_calls"]:
            state["previous_turn"] = state["turn"]
        state["turn"] = {"output": 0, "tool_calls": 0}
        return
    if kind != "assistant":
        return
    mid = message.get("id") if isinstance(message.get("id"), str) else ""
    usage = message.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    slot = _slot(state, mid)
    try:
        output = int(usage.get("output_tokens") or 0)
    except (TypeError, ValueError):
        output = 0
    if output > slot[1]:
        # Only the rise is added, so a partial streaming count followed by the true figure is
        # one message counted once at its largest.
        for name in ("session", "turn"):
            state[name]["output"] += output - slot[1]
        slot[1] = output
    for index, block in enumerate(message.get("content") or []):
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        key = block.get("id") or str(block.get("apiBlockIndex", index))
        if key in slot[2]:
            continue
        slot[2].append(key)
        for name in ("session", "turn"):
            state[name]["tool_calls"] += 1


def _align(handle, offset, size):
    """The next line start at or after `offset`. A saved offset mid-line re-aligns forward."""
    if offset <= 0:
        return 0
    if offset >= size:
        return size
    handle.seek(offset - 1)
    if handle.read(1) == b"\n":
        return offset
    handle.seek(offset)
    raw = handle.readline()
    return size if not raw.endswith(b"\n") else offset + len(raw)


def _identity(handle):
    """`(inode, head hash, size)`. A replaced transcript of any size fails this, not just a shorter one.

    The hash covers the transcript's first line rather than a fixed 512 bytes, because a young
    file shorter than that is still being appended to inside the window a fixed slice would
    cover, and its identity would change under it every turn. A first record is written once.
    """
    stat = os.fstat(handle.fileno())
    handle.seek(0)
    head = handle.read(512)
    cut = head.find(b"\n")
    if cut >= 0:
        head = head[:cut]
    return stat.st_ino, hashlib.sha256(head).hexdigest()[:16], stat.st_size


def advance(state, transcript, save=None, budget=READ_BUDGET):
    """Read from the settled offset to EOF, bounded by `COLD_TAIL` and by the clock.

    `save` is called once the offset and the file identity are settled and before a single line
    is parsed: a hook killed at its timeout must not leave the next one to repeat the same work
    forever. `timed_out` on the returned state says the read gave up, and the caller stays quiet.
    """
    path = Path(os.path.expanduser(str(transcript)))
    try:
        handle = _open(path)
    except OSError:
        if save:
            save(state)
        return state
    with handle:
        try:
            inode, head, size = _identity(handle)
        except OSError:
            return state
        if (state.get("inode") != inode or state.get("head") != head
                or state["offset"] > size or size < state["size"]):
            # Compaction, a rotation, a replacement — of any size. What came before is unknowable
            # about the transcript; what the journal recorded is still true and stays.
            seen = state.get("inode") is not None
            kept = {key: state[key] for key in
                    ("journal_offset", "running", "pending", "counted", "subagents", "pruned")}
            state = dict(new_state(), **kept)
            state["inode"], state["head"] = inode, head
            state["offset"] = max(0, size - COLD_TAIL)
            state["partial"] = seen or state["offset"] > 0
        try:
            state["offset"] = _align(handle, state["offset"], size)
        except OSError:
            return state
        state["size"] = size
        if save:
            save(state)
        if state["offset"] >= size:
            return state
        position = state["offset"]
        deadline = time.monotonic() + budget
        handle.seek(position)
        for counted, raw in enumerate(handle):
            # A line still being written is not a line; leaving it unconsumed is what makes the
            # next read pick it up whole.
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                _apply(state, json.loads(raw.decode("utf-8", "replace")))
            except ValueError:
                pass
            if not counted % 256 and time.monotonic() > deadline:
                state["partial"] = True
                state["timed_out"] = True
                break
    state["offset"] = position
    return state


# --------------------------------------------------------------------------- subagents


def agent_transcript(transcript_path, session_id, agent_id):
    """`<dirname(transcript)>/<session>/subagents/agent-<id>.jsonl`, or None.

    A Workflow-tool agent sits one level deeper, under `subagents/workflows/wf_*/`. Both places
    are named, rather than walked: a recursive search of a session's whole subagent tree is
    unbounded work for a question with two possible answers.
    """
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    if not (isinstance(session_id, str) and IDENTIFIER.match(session_id)):
        return None
    if not transcript_path:
        return None
    base = Path(os.path.expanduser(str(transcript_path))).parent / session_id / "subagents"
    name = "agent-" + agent_id + ".jsonl"
    try:
        if (base / name).is_file():
            return base / name
        found = sorted(base.glob("workflows/*/" + name))
    except OSError:
        return None
    return found[0] if found else None


def agent_totals(path):
    """`{output, tool_calls, agent_type, partial}` from the subagent's own transcript, or None.

    The sum is `usage-log.py`'s per-agent row function, reused rather than reimplemented: it is
    the code that already counts one message id once at its largest figure, which is the only
    way past the last-response figure a tool response reports. It is given a byte cap and a
    clock here, because this runs inside a hook timeout and a very large agent would otherwise
    take the whole process down with it.
    """
    module = sibling("usage-log")
    if module is None or not path:
        return None
    try:
        row = module._agent_row(Path(path), budget=AGENT_BUDGET, max_bytes=AGENT_BYTES)
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    return {"output": int(row.get("output") or 0), "tool_calls": int(row.get("tool_calls") or 0),
            "agent_type": agent_name(row.get("agent_type")), "partial": bool(row.get("partial"))}


def agent_name(value, fallback="unknown"):
    """An agent type fit to inject and to journal. Free text becomes `other`, never itself."""
    if value is None or value == "":
        return fallback
    if isinstance(value, str) and AGENT_NAME.match(value):
        return value
    return UNNAMED


# --------------------------------------------------------------------------- the journal, ingested


def ingest(state, journal_file):
    """Fold the journal's new bytes into the locked state: running, pending and the totals.

    Only new bytes, from a saved offset, because a session long enough to outgrow one read is
    exactly the session whose totals must not start going down. A half-written last line is left
    unconsumed and read whole next time.
    """
    try:
        size = journal_file.stat().st_size
        handle = open(str(journal_file), "rb")
    except OSError:
        return state
    offset = state["journal_offset"]
    if offset > size:
        # A journal replaced under us: re-read it rather than trust an offset into another file.
        offset = 0
    position = offset
    with handle:
        handle.seek(offset)
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                record = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                continue
            agent_id = record["id"]
            if record.get("t") == "start":
                state["running"][agent_id] = int(record.get("at") or 0)
                continue
            if record.get("t") != "stop":
                continue
            state["running"].pop(agent_id, None)
            if agent_id in state["counted"]:
                continue
            state["counted"].append(agent_id)
            count(state, record)
            state["pending"].append(record)
    state["journal_offset"] = position
    return state


def count(state, record):
    """One finished agent against the session's subagent totals, exactly once."""
    totals = state["subagents"]
    totals["count"] += 1
    if record.get("output") is None and record.get("tool_calls") is None:
        totals["unknown"] += 1
        return
    totals["output"] += int(record.get("output") or 0)
    totals["tool_calls"] += int(record.get("tool_calls") or 0)


def running_now(state, now=None):
    """The agents still in flight, forgetting a start whose stop never came."""
    now = time.time() if now is None else now
    stale = [agent for agent, at in state["running"].items() if now - (at or 0) > RUNNING_TTL]
    for agent in stale:
        del state["running"][agent]
    return list(state["running"])


# --------------------------------------------------------------------------- the lines


def settings(env):
    """`(table, mode, nudges, width)` from the active cost variant, or the silent default."""
    module = sibling("posture")
    if module is None:
        return None, "off", [], None
    try:
        table = module.cost_table(env)
    except Exception:
        return None, "off", [], None
    switches = table.get("switches") if isinstance(table, dict) else None
    switches = switches if isinstance(switches, dict) else {}
    mode = switches.get("turn_feed")
    mode = mode if mode in MODES else "off"
    nudges = sorted(v for v in switches.get("nudge_at") or []
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)
    width = switches.get("max_parallel")
    width = width if isinstance(width, int) and not isinstance(width, bool) and width > 0 else None
    return table, mode, nudges, width


def budgets(row):
    """The row's two soft budgets, each only when it is a positive whole number."""
    if not isinstance(row, dict):
        return None, None
    out = []
    for key in ("budget_output_tokens", "budget_tool_calls"):
        value = row.get(key)
        out.append(value if isinstance(value, int) and not isinstance(value, bool) and value > 0
                   else None)
    return out[0], out[1]


def agent_line(agent_type, output, calls, row, nudges, partial=False):
    """`(line, ratio)` for one finished subagent; ratio is None when there is nothing to compare.

    Null counts are what a sum that could not be computed leaves behind, and the line says so:
    an agent reported at zero would read as an agent that did nothing. A row that budgets one
    half of the unit names that half, because `n / None` would read as a figure to act on.
    """
    if output is None and calls is None:
        return PREFIX + agent_type + " finished, spend unknown", None
    text = (PREFIX + agent_type + " finished at " + plural(output or 0, "output token")
            + " and " + plural(calls or 0, "tool call"))
    if partial:
        text += " (partial)"
    budget_out, budget_calls = budgets(row)
    ratios, halves = [], []
    if budget_out:
        ratios.append((output or 0) / float(budget_out))
        halves.append(plural(budget_out, "output token"))
    if budget_calls:
        ratios.append((calls or 0) / float(budget_calls))
        halves.append(plural(budget_calls, "tool call"))
    if not ratios:
        return text, None
    ratio = max(ratios)
    if budget_out and budget_calls:
        halves = ["{:,}".format(budget_out) + " / " + "{:,}".format(budget_calls)]
    clause = "{:.1f}".format(ratio) + "× its budget of " + " and ".join(halves)
    if any(ratio >= level for level in nudges):
        clause = "over budget " + clause
    return text + " — " + clause, ratio


def width_line(running, width):
    """One line when more agents are in flight than the posture's width. Never a decision."""
    if width is None or len(running) <= width:
        return None
    return (PREFIX + plural(len(running), "subagent") + " running against a posture width of "
            + "{:,}".format(width))


def turn_line(state):
    """The turn and the session so far. Subagent spend is the session's bill, so it is in both."""
    last = state["turn"] if (state["turn"]["output"] or state["turn"]["tool_calls"]) \
        else state["previous_turn"]
    totals = state["subagents"]
    text = (PREFIX + "last turn " + plural(last["output"], "output token") + ", "
            + plural(last["tool_calls"], "tool call") + " · session "
            + "{:,}".format(state["session"]["output"] + totals["output"]) + " output, "
            + plural(state["session"]["tool_calls"] + totals["tool_calls"], "tool call") + ", "
            + plural(totals["count"], "subagent"))
    if totals["unknown"] or state.get("partial"):
        text += " (partial)"
    return text


def shows(mode, ratio, nudges):
    """Whether a subagent's line is worth a line. `thresholds` wants the smallest nudge met."""
    if mode == "every-turn":
        return True
    if mode != "thresholds" or not nudges or ratio is None:
        return False
    return ratio >= nudges[0]


def row_for(table, agent_type):
    module = sibling("posture")
    try:
        return module.row_for(table, agent_type) if module else None
    except Exception:
        return None


def stop_line(table, nudges, record):
    return agent_line(agent_name(record.get("type")), record.get("output"),
                      record.get("tool_calls"), row_for(table, record.get("type")), nudges,
                      bool(record.get("partial")))


# --------------------------------------------------------------------------- the events


def on_subagent_event(payload, env, kind):
    """Journal one subagent lifecycle event. Never emits and never takes the lock.

    `SubagentStop`'s own `additionalContext` would reach the agent that has just finished, so
    there is nothing to say here even when there is something to record. The stop is written in
    a `finally`: an agent whose stop never landed would be counted as running for the rest of
    the session, so a stop with nothing in it beats no stop at all.
    """
    if payload.get("stop_hook_active"):
        return None
    agent_id = payload.get("agent_id")
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    _, mode, _, _ = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    record = {"t": kind, "id": agent_id, "type": agent_name(payload.get("agent_type")),
              "at": int(time.time())}
    if kind == "start":
        journal_append(found[1], record)
        return None
    record["output"], record["tool_calls"], record["partial"] = None, None, False
    try:
        totals = agent_totals(payload.get("agent_transcript_path") or agent_transcript(
            payload.get("transcript_path"), payload.get("session_id"), agent_id))
        if totals is not None:
            record["type"] = agent_name(payload.get("agent_type"), totals["agent_type"])
            record["output"], record["tool_calls"] = totals["output"], totals["tool_calls"]
            record["partial"] = totals["partial"]
    finally:
        journal_append(found[1], record)
    return None


def on_agent_return(payload, env):
    """A synchronous `Agent` completion, reported once, plus the width note on any Agent call."""
    response = payload.get("tool_response")
    response = response if isinstance(response, dict) else {}
    table, mode, nudges, width = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    state_file, journal_file, lock_file = found
    agent_id = response.get("agentId")
    # A background spawn's PostToolUse fires at launch with no totals at all; only the width
    # note applies to it.
    synchronous = (not response.get("isAsync") and response.get("status") == "completed"
                   and isinstance(agent_id, str) and IDENTIFIER.match(agent_id))
    fresh = None
    if synchronous:
        # Before the lock, always: this is the one slow thing either main-thread event does,
        # and a prompt waiting behind it would run out its wait and lose its line.
        totals = agent_totals(agent_transcript(payload.get("transcript_path"),
                                               payload.get("session_id"), agent_id))
        if totals is not None:
            fresh = {"id": agent_id, "output": totals["output"], "partial": totals["partial"],
                     "tool_calls": totals["tool_calls"],
                     "type": agent_name(response.get("agentType"), totals["agent_type"])}
    with Lock(lock_file) as held:
        if not held:
            return None
        state = ingest(load_state(state_file), journal_file)
        lines = []
        if synchronous:
            record = next((r for r in state["pending"] if r.get("id") == agent_id), None)
            if record is not None:
                line, ratio = stop_line(table, nudges, record)
                if shows(mode, ratio, nudges):
                    state["pending"].remove(record)
                    lines.append(line)
            elif fresh is not None and agent_id not in state["counted"]:
                # The stop has not been journalled yet. Reporting it now means counting it now,
                # so the journal's copy is skipped when it arrives.
                line, ratio = stop_line(table, nudges, fresh)
                if shows(mode, ratio, nudges):
                    state["counted"].append(agent_id)
                    count(state, fresh)
                    state["running"].pop(agent_id, None)
                    lines.append(line)
        note = width_line(running_now(state), width)
        if note:
            lines.append(note)
        save_state(state_file, state)
        return lines or None


def on_prompt(payload, env):
    """The turn line, the width note, then the subagents that finished since the last prompt."""
    table, mode, nudges, width = settings(env)
    if mode == "off":
        return None
    found = paths(payload.get("session_id"), env)
    if found is None:
        return None
    state_file, journal_file, lock_file = found
    with Lock(lock_file) as held:
        if not held:
            return None
        state = ingest(load_state(state_file), journal_file)
        prune(state_file.parent, state, state_file.name.split(".", 1)[0])
        state = advance(state, payload.get("transcript_path"),
                        save=lambda current: save_state(state_file, current))
        if state.get("timed_out"):
            save_state(state_file, state)
            return None
        lines = [turn_line(state)] if mode == "every-turn" else []
        note = width_line(running_now(state), width)
        if note:
            lines.append(note)
        said = []
        for record in list(state["pending"]):
            line, ratio = stop_line(table, nudges, record)
            if not shows(mode, ratio, nudges):
                continue
            said.append((record, line))
        # Only the agents this turn actually names are retired. The cap bounds how much is said
        # at once, so the rest are named at the next prompt rather than dropped unsaid.
        for record, line in said[:MAX_LISTED]:
            state["pending"].remove(record)
            lines.append(line)
        if len(said) > MAX_LISTED:
            lines.append("… and " + "{:,}".format(len(said) - MAX_LISTED) + " more")
        save_state(state_file, state)
    return lines or None


def run(payload, env=None):
    """The lines one event produces, or None. The parent thread is the only place a feed runs."""
    env = os.environ if env is None else env
    kind = payload.get("hook_event_name") or ""
    if kind in ("SubagentStop", "SubagentStart"):
        # The only events whose `agent_id` names somebody else: they fire in the parent's hooks.
        return on_subagent_event(payload, env, "stop" if kind == "SubagentStop" else "start")
    if payload.get("agent_id"):
        return None
    if kind == "UserPromptSubmit":
        return on_prompt(payload, env)
    if kind == "PostToolUse" and payload.get("tool_name") == "Agent":
        return on_agent_return(payload, env)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        lines = run(payload)
    except Exception:
        return
    if lines:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": payload.get("hook_event_name") or "",
            "additionalContext": "\n".join(lines)}}))


if __name__ == "__main__":
    main()
