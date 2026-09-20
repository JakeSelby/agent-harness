#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Feed measured spend back to the orchestrator: one turn line, one line per finished subagent.

Four events, all on the parent thread. `SubagentStart` and `SubagentStop` record when an agent
began and what it cost. `PostToolUse` on `Agent` reports a synchronous return the moment it lands,
and says how many agents are running when that is past the posture's width. `UserPromptSubmit`
reports the turn and every subagent that finished since the previous prompt — which is how a
background spawn, whose `PostToolUse` fires at launch with no totals, is reported at all.

Four facts shape the whole file:

- **A tool response's token figure describes only the subagent's last response.** Measured on a
  live return: `tool_response.usage.output_tokens` said 3,143 against 10,575 actually spent over
  nineteen responses. The real figure is summed from the subagent's own transcript, once per
  message id at the field-wise maximum, by `usage-log.py`'s per-agent row function and not by a
  second copy of that logic here.
- **These hooks run concurrently, as separate processes.** Parallel tool calls and several agents
  finishing at once are ordinary. So state is split in two. A subagent event is one line under
  4 KB appended to `<session>.events.jsonl` through an `O_APPEND` descriptor, which no handler
  ever rewrites and which therefore cannot lose a record. Everything the main thread must
  read-modify-write — the transcript offset, the running totals, the open message ids and which
  agents have been reported — lives in `<session>.json` and is touched only under an exclusive
  `flock` on `<session>.lock`, with a bounded wait. No lock, no write, and nothing emitted.
- **A transcript is read incrementally, and never unboundedly.** The saved offset is trusted only
  when the file is still the same file: the inode and a hash of its first 512 bytes say so, and a
  replacement that is *larger* is caught by that where a size comparison alone would miss it. With
  no usable state the read starts 8 MiB from the end, because a resumed session's transcript can
  be hundreds of megabytes and a hook killed at its timeout would stall every prompt after it.
  The offset is saved before the slow part begins, and a wall-clock budget ends the read.
- **The feed never decides anything.** No permission field, no deny, no budget, threshold, model
  name or role name in this file: every number comes from the cost table's row for the agent type,
  and every switch from `switches.turn_feed`, `switches.nudge_at` and `switches.max_parallel`. A
  variant that sets none of them feeds nothing, which is the null-variant guarantee. Any failure
  at all emits nothing and exits 0.
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
# several lines that repeat its id contiguously, so a short tail is all that is ever needed.
OPEN_TAIL = 8
MAX_LISTED = 5
# Reported ids are append-only under the lock. The cap is generous: an id evicted while its
# journal entry survives would be announced a second time.
MAX_REPORTED = 2000
# A cold start reads this much of the tail, not the whole file.
COLD_TAIL = 8 * 1024 * 1024
JOURNAL_TAIL = 1024 * 1024
READ_BUDGET = 3.0
LOCK_WAIT = 2.0
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


def _create(path, mode=0o600):
    """A file that is private from the moment it exists; `chmod` after the fact is a window."""
    return os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)


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
    line = json.dumps(record, ensure_ascii=True) + "\n"
    data = line.encode("utf-8")
    if len(data) > MAX_LINE:
        return False
    if not ensure_dir(path.parent):
        return False
    try:
        handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError:
        return False
    try:
        os.write(handle, data)
    except OSError:
        return False
    finally:
        os.close(handle)
    return True


def journal(path):
    """`(stops by agent id, running agent ids, totals)` from the append-only journal.

    A stop seen twice is one agent at its latest figure, and a start with no stop is an agent
    still running. Only the tail is read, because a session cannot spawn enough agents to make
    a megabyte of one-line records and a corrupt head must not cost the recent truth.
    """
    stops, started = {}, []
    totals = {"output": 0, "tool_calls": 0, "count": 0}
    try:
        size = path.stat().st_size
        with open(str(path), "rb") as handle:
            if size > JOURNAL_TAIL:
                handle.seek(size - JOURNAL_TAIL)
                handle.readline()
            raw = handle.read()
    except OSError:
        return stops, [], totals
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            continue
        if record.get("t") == "start":
            if record["id"] not in started:
                started.append(record["id"])
        elif record.get("t") == "stop":
            stops[record["id"]] = record
    for record in stops.values():
        totals["output"] += int(record.get("output") or 0)
        totals["tool_calls"] += int(record.get("tool_calls") or 0)
        totals["count"] += 1
    running = [agent for agent in started if agent not in stops]
    return stops, running, totals


# --------------------------------------------------------------------------- the reader's state


def new_state():
    return {"version": 2, "offset": 0, "size": 0, "inode": None, "head": None, "partial": False,
            "session": {"output": 0, "tool_calls": 0},
            "turn": {"output": 0, "tool_calls": 0},
            "previous_turn": {"output": 0, "tool_calls": 0},
            "open": [], "reported": [], "pruned": 0}


def _counter(state, key):
    value = state.get(key)
    if not isinstance(value, dict):
        value = {}
        state[key] = value
    for name in ("output", "tool_calls"):
        if not isinstance(value.get(name), int) or isinstance(value.get(name), bool):
            value[name] = 0
    return value


def _whole(state, key):
    if not isinstance(state.get(key), int) or isinstance(state.get(key), bool):
        state[key] = 0


def load_state(path):
    """The session's state, or a fresh one. A file we cannot read is a file we start over from."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return new_state()
    if not isinstance(data, dict) or data.get("version") != 2:
        return new_state()
    state = new_state()
    state.update(data)
    for key in ("session", "turn", "previous_turn"):
        _counter(state, key)
    for key in ("offset", "size", "pruned"):
        _whole(state, key)
    state["open"] = [item for item in state.get("open") or []
                     if isinstance(item, list) and len(item) == 3 and isinstance(item[1], int)]
    state["reported"] = [i for i in state.get("reported") or [] if isinstance(i, str)]
    return state


def save_state(path, state):
    """Atomic and private. Called before the slow read as well as after it."""
    state["reported"] = state.get("reported", [])[-MAX_REPORTED:]
    if not ensure_dir(path.parent):
        return
    tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        handle = _create(tmp)
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

    The reader's state is the only thing this guards, and every writer of it is a hook process
    that must finish inside a ten-second timeout. Waiting longer than a couple of seconds for a
    number the next prompt will recompute anyway is worse than skipping the line.
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


def prune(directory, state, now=None):
    """Once a day at most, drop feed files nothing has touched in a fortnight."""
    now = time.time() if now is None else now
    if now - state.get("pruned", 0) < PRUNE_EVERY:
        return
    state["pruned"] = int(now)
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_file() and now - entry.stat().st_mtime > FEED_TTL:
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
            # Compaction, a rotation, a replacement — of any size. What came before is unknowable.
            seen = state.get("inode") is not None
            reported, pruned = state.get("reported", []), state.get("pruned", 0)
            state = new_state()
            state["reported"], state["pruned"] = reported, pruned
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
        counted = 0
        handle.seek(position)
        for raw in handle:
            # A line still being written is not a line; leaving it unconsumed is what makes the
            # next read pick it up whole.
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                _apply(state, json.loads(raw.decode("utf-8", "replace")))
            except ValueError:
                pass
            counted += 1
            if counted % 256 == 0 and time.monotonic() > deadline:
                state["partial"] = True
                state["timed_out"] = True
                break
    state["offset"] = position
    return state


# --------------------------------------------------------------------------- subagents


def agent_transcript(transcript_path, session_id, agent_id):
    """`<dirname(transcript)>/<session>/subagents/**/agent-<id>.jsonl`, or None.

    Recursive because a Workflow-tool agent sits a level deeper, under `subagents/workflows/wf_*/`.
    """
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    if not (isinstance(session_id, str) and IDENTIFIER.match(session_id)):
        return None
    if not transcript_path:
        return None
    base = Path(os.path.expanduser(str(transcript_path))).parent / session_id / "subagents"
    try:
        found = sorted(base.rglob("agent-" + agent_id + ".jsonl"))
    except OSError:
        return None
    return found[0] if found else None


def agent_totals(path):
    """`{output, tool_calls, agent_type}` summed from the subagent's own transcript, or None.

    The sum is `usage-log.py`'s per-agent row function, reused rather than reimplemented: it is
    the code that already counts one message id once at its largest figure, which is the only
    way past the last-response figure a tool response reports.
    """
    module = sibling("usage-log")
    if module is None or not path:
        return None
    try:
        row = module._agent_row(Path(path))
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    return {"output": int(row.get("output") or 0), "tool_calls": int(row.get("tool_calls") or 0),
            "agent_type": agent_name(row.get("agent_type"))}


def agent_name(value, fallback="unknown"):
    """An agent type fit to inject and to journal. Free text becomes `other`, never itself."""
    if value is None or value == "":
        return fallback
    if isinstance(value, str) and AGENT_NAME.match(value):
        return value
    return UNNAMED


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


def agent_line(agent_type, output, calls, row, nudges):
    """`(line, ratio)` for one finished subagent; ratio is None when the row budgets nothing.

    A row that budgets one half of the unit names that half and says which it is; a budget
    printed as `n / None` would read as a figure somebody could act on.
    """
    text = (PREFIX + agent_type + " finished at " + str(output) + " output tokens and "
            + str(calls) + " tool calls")
    budget_out, budget_calls = budgets(row)
    ratios, halves = [], []
    if budget_out:
        ratios.append(output / float(budget_out))
        halves.append(str(budget_out) + " output tokens")
    if budget_calls:
        ratios.append(calls / float(budget_calls))
        halves.append(str(budget_calls) + " tool calls")
    if not ratios:
        return text, None
    ratio = max(ratios)
    if budget_out and budget_calls:
        halves = [str(budget_out) + " / " + str(budget_calls)]
    clause = "{:.1f}".format(ratio) + "× its budget of " + " and ".join(halves)
    if any(ratio >= level for level in nudges):
        clause = "over budget " + clause
    return text + " — " + clause, ratio


def width_line(running, width):
    """One line when more agents are in flight than the posture's width. Never a decision."""
    if width is None or len(running) <= width:
        return None
    return (PREFIX + str(len(running)) + " subagents running against a posture width of "
            + str(width))


def turn_line(state, totals):
    """The turn and the session so far. Subagent spend is the session's bill, so it is in both."""
    last = state["turn"] if (state["turn"]["output"] or state["turn"]["tool_calls"]) \
        else state["previous_turn"]
    text = (PREFIX + "last turn " + str(last["output"]) + " output tokens, "
            + str(last["tool_calls"]) + " tool calls · session "
            + str(state["session"]["output"] + totals["output"]) + " output, "
            + str(state["session"]["tool_calls"] + totals["tool_calls"]) + " tool calls, "
            + str(totals["count"]) + " subagents")
    return text + " (partial)" if state.get("partial") else text


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
    return agent_line(agent_name(record.get("type")), int(record.get("output") or 0),
                      int(record.get("tool_calls") or 0),
                      row_for(table, record.get("type")), nudges)


# --------------------------------------------------------------------------- the events


def on_subagent_event(payload, env, kind):
    """Journal one subagent lifecycle event. Never emits, never locks, never rewrites a file.

    `SubagentStop`'s own `additionalContext` would reach the agent that has just finished, so
    there is nothing to say here even when there is something to record.
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
    transcript = payload.get("agent_transcript_path") or agent_transcript(
        payload.get("transcript_path"), payload.get("session_id"), agent_id)
    totals = agent_totals(transcript)
    if totals is None:
        return None
    record["type"] = agent_name(payload.get("agent_type"), totals["agent_type"])
    record["output"], record["tool_calls"] = totals["output"], totals["tool_calls"]
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
    with Lock(lock_file) as held:
        if not held:
            return None
        stops, running, _ = journal(journal_file)
        state = load_state(state_file)
        lines = []
        if synchronous:
            record = stops.get(agent_id)
            if record is None:
                # The SubagentStop entry has not landed yet, so the transcript is read directly.
                totals = agent_totals(agent_transcript(payload.get("transcript_path"),
                                                       payload.get("session_id"), agent_id))
                if totals is not None:
                    record = {"id": agent_id, "output": totals["output"],
                              "tool_calls": totals["tool_calls"],
                              "type": agent_name(response.get("agentType"), totals["agent_type"])}
                    running = [a for a in running if a != agent_id]
            if record is not None and agent_id not in state["reported"]:
                line, ratio = stop_line(table, nudges, record)
                if shows(mode, ratio, nudges):
                    # Only a line that was said counts as reported, so a quiet return under
                    # `thresholds` stays listable at the next prompt.
                    state["reported"].append(agent_id)
                    lines.append(line)
        note = width_line(running, width)
        if note:
            lines.append(note)
        if lines:
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
        state = load_state(state_file)
        prune(state_file.parent, state)
        state = advance(state, payload.get("transcript_path"),
                        save=lambda current: save_state(state_file, current))
        stops, running, totals = journal(journal_file)
        if state.get("timed_out"):
            save_state(state_file, state)
            return None
        lines = [turn_line(state, totals)] if mode == "every-turn" else []
        note = width_line(running, width)
        if note:
            lines.append(note)
        listed = []
        for agent_id, record in stops.items():
            if agent_id in state["reported"]:
                continue
            line, ratio = stop_line(table, nudges, record)
            if not shows(mode, ratio, nudges):
                continue
            listed.append((agent_id, line))
        # Only the agents this turn actually names are retired. The cap bounds how much is said
        # at once, so the rest are named at the next prompt rather than dropped unsaid.
        for agent_id, line in listed[:MAX_LISTED]:
            state["reported"].append(agent_id)
            lines.append(line)
        if len(listed) > MAX_LISTED:
            lines.append("… and " + str(len(listed) - MAX_LISTED) + " more")
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
