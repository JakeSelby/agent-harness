#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Feed measured spend back to the orchestrator: one turn line, one line per finished subagent.

Three events, all on the parent thread. `SubagentStop` records what a finished subagent actually
cost. `PostToolUse` on `Agent` reports a synchronous return the moment it lands. `UserPromptSubmit`
reports the turn and every subagent that finished since the previous prompt — which is how a
background spawn, whose `PostToolUse` fires at launch with no totals, is reported at all.

Two facts shape the whole file:

- **A tool response's token figure describes only the subagent's last response.** Measured on a
  live return: `tool_response.usage.output_tokens` said 3,143 against 10,575 actually spent over
  nineteen responses. The real figure is summed from the subagent's own transcript, once per
  message id at the field-wise maximum, by `usage-log.py`'s row builder and not by a second copy
  of that logic here.
- **The parent transcript is read incrementally.** State under
  `~/.local/state/agent-harness/feed/<session-id>.json` holds the byte offset read so far, the
  running totals and the message-id maxima still open at the tail, so a prompt costs one read of
  whatever arrived since the last event. A transcript that shrank or an offset past EOF —
  compaction, or a new file — resets to the current EOF and says `(partial)`.

No budget, threshold, model name or role name lives here: every number comes from the cost
table's row for the agent type, and every switch from `switches.turn_feed` and `switches.nudge_at`.
A variant that sets neither feeds nothing, which is the null-variant guarantee. Any failure at
all — an unbuildable table, an unreadable transcript, a malformed state file — emits nothing and
exits 0; a feed must never be the reason anything is blocked.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PREFIX = "usage-feed: "
# The state file is a rolling record, not an archive: `usage-log.py` keeps the durable rows.
MAX_RECORDS = 200
# How many message ids stay open for a later line to raise. One API response is written as
# several lines that repeat its id contiguously, so a short tail is all that is ever needed.
OPEN_TAIL = 8
MAX_LISTED = 5
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
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


# --------------------------------------------------------------------------- state


def home(env):
    return Path(env.get("HARNESS_HOME") or env.get("HOME") or Path.home())


def feed_dir(env):
    return home(env) / ".local" / "state" / "agent-harness" / "feed"


def state_path(session_id, env):
    """The state file for one session, or None when the id is not a name we would write."""
    if not isinstance(session_id, str) or not IDENTIFIER.match(session_id):
        return None
    return feed_dir(env) / (session_id + ".json")


def new_state():
    return {"version": 1, "offset": 0, "size": 0, "partial": False,
            "session": {"output": 0, "tool_calls": 0},
            "turn": {"output": 0, "tool_calls": 0},
            "previous_turn": {"output": 0, "tool_calls": 0},
            "subagents": {"output": 0, "tool_calls": 0, "count": 0},
            "open": [], "records": []}


def _counter(state, key):
    value = state.get(key)
    if not isinstance(value, dict):
        value = {}
        state[key] = value
    names = ("output", "tool_calls", "count") if key == "subagents" else ("output", "tool_calls")
    for name in names:
        if not isinstance(value.get(name), int) or isinstance(value.get(name), bool):
            value[name] = 0
    return value


def load_state(path):
    """The session's state, or a fresh one. A file we cannot read is a file we start over from."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return new_state()
    if not isinstance(data, dict) or data.get("version") != 1:
        return new_state()
    state = new_state()
    state.update(data)
    for key in ("session", "turn", "previous_turn", "subagents"):
        _counter(state, key)
    if not isinstance(state.get("offset"), int) or isinstance(state.get("offset"), bool):
        state["offset"] = 0
    if not isinstance(state.get("size"), int) or isinstance(state.get("size"), bool):
        state["size"] = 0
    state["open"] = [item for item in state.get("open") or []
                     if isinstance(item, list) and len(item) == 3 and isinstance(item[1], int)]
    state["records"] = [r for r in state.get("records") or []
                        if isinstance(r, dict) and isinstance(r.get("agent_id"), str)]
    return state


def save_state(path, state):
    """Atomic, 0700 on the directory and 0600 on the file: counts and agent types are still spend."""
    state["records"] = state.get("records", [])[-MAX_RECORDS:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(str(path.parent), 0o700)
    except OSError:
        return
    tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    try:
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.chmod(str(tmp), 0o600)
        os.replace(str(tmp), str(path))
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


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


def advance(state, transcript):
    """Read from the saved offset to EOF and nothing else. Returns the state, always."""
    path = Path(os.path.expanduser(str(transcript)))
    try:
        size = path.stat().st_size
    except OSError:
        return state
    offset = state["offset"]
    if offset > size or size < state["size"]:
        # Compaction, a rotated file or a truncated one: what came before is unknowable now.
        fresh = new_state()
        fresh["records"] = state.get("records", [])
        fresh["subagents"] = _counter(state, "subagents")
        fresh["partial"] = True
        fresh["offset"] = fresh["size"] = size
        return fresh
    if offset == size:
        return state
    position = offset
    try:
        handle = _open(path)
    except OSError:
        return state
    with handle:
        handle.seek(offset)
        for raw in handle:
            # A line still being written is not a line; leaving it unconsumed is what makes the
            # next read pick it up whole.
            if not raw.endswith(b"\n"):
                break
            position += len(raw)
            try:
                _apply(state, json.loads(raw.decode("utf-8", "replace")))
            except ValueError:
                continue
    state["offset"], state["size"] = position, size
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
            "agent_type": row.get("agent_type") or "unknown"}


def agent_name(value, fallback="unknown"):
    """An agent type fit to inject. Free text never reaches the orchestrator through this hook."""
    return value if isinstance(value, str) and IDENTIFIER.match(value) else fallback


def remember(state, agent_id, agent_type, totals):
    """Add or refresh one subagent record; the session's subagent totals count it once."""
    for record in state["records"]:
        if record.get("agent_id") == agent_id:
            record["agent_type"], record["output"] = agent_type, totals["output"]
            record["tool_calls"] = totals["tool_calls"]
            return record
    record = {"agent_id": agent_id, "agent_type": agent_type, "output": totals["output"],
              "tool_calls": totals["tool_calls"], "reported": False}
    state["records"].append(record)
    totals_of = state["subagents"]
    totals_of["output"] += totals["output"]
    totals_of["tool_calls"] += totals["tool_calls"]
    totals_of["count"] += 1
    return record


# --------------------------------------------------------------------------- the lines


def settings(env):
    """`(table, mode, nudges)` from the active cost variant, or `(None, "off", [])`."""
    module = sibling("posture")
    if module is None:
        return None, "off", []
    try:
        table = module.cost_table(env)
    except Exception:
        return None, "off", []
    switches = table.get("switches") if isinstance(table, dict) else None
    switches = switches if isinstance(switches, dict) else {}
    mode = switches.get("turn_feed")
    mode = mode if mode in MODES else "off"
    nudges = sorted(v for v in switches.get("nudge_at") or []
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)
    return table, mode, nudges


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
    """`(line, ratio)` for one finished subagent; ratio is None when the row budgets nothing."""
    text = (PREFIX + agent_type + " finished at " + str(output) + " output tokens and "
            + str(calls) + " tool calls")
    budget_out, budget_calls = budgets(row)
    ratios = [output / float(budget_out)] if budget_out else []
    if budget_calls:
        ratios.append(calls / float(budget_calls))
    if not ratios:
        return text, None
    ratio = max(ratios)
    clause = "{:.1f}".format(ratio) + "× its budget of " + str(budget_out) + " / " + str(budget_calls)
    if any(ratio >= level for level in nudges):
        clause = "over budget " + clause
    return text + " — " + clause, ratio


def turn_line(state):
    """The turn and the session so far. Subagent spend is the session's bill, so it is in both."""
    last = state["turn"] if (state["turn"]["output"] or state["turn"]["tool_calls"]) \
        else state["previous_turn"]
    agents = state["subagents"]
    text = (PREFIX + "last turn " + str(last["output"]) + " output tokens, "
            + str(last["tool_calls"]) + " tool calls · session "
            + str(state["session"]["output"] + agents["output"]) + " output, "
            + str(state["session"]["tool_calls"] + agents["tool_calls"]) + " tool calls, "
            + str(agents["count"]) + " subagents")
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


# --------------------------------------------------------------------------- the events


def on_subagent_stop(payload, env):
    """Record what the finished subagent cost. Emits nothing: its context would reach itself."""
    if payload.get("stop_hook_active"):
        return None
    agent_id = payload.get("agent_id")
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    _, mode, _ = settings(env)
    if mode == "off":
        return None
    path = state_path(payload.get("session_id"), env)
    if path is None:
        return None
    transcript = payload.get("agent_transcript_path") or agent_transcript(
        payload.get("transcript_path"), payload.get("session_id"), agent_id)
    totals = agent_totals(transcript)
    if totals is None:
        return None
    state = load_state(path)
    remember(state, agent_id, agent_name(payload.get("agent_type"), totals["agent_type"]), totals)
    save_state(path, state)
    return None


def on_agent_return(payload, env):
    """A synchronous `Agent` completion, reported once, on the spot."""
    response = payload.get("tool_response")
    if not isinstance(response, dict) or response.get("isAsync"):
        # A background spawn's PostToolUse fires at launch with no totals; the next prompt
        # reports it instead.
        return None
    if response.get("status") != "completed":
        return None
    agent_id = response.get("agentId")
    if not (isinstance(agent_id, str) and IDENTIFIER.match(agent_id)):
        return None
    table, mode, nudges = settings(env)
    if mode == "off":
        return None
    path = state_path(payload.get("session_id"), env)
    if path is None:
        return None
    state = load_state(path)
    record = next((r for r in state["records"] if r.get("agent_id") == agent_id), None)
    if record is None:
        # The SubagentStop record has not landed yet, so the transcript is read directly.
        totals = agent_totals(agent_transcript(payload.get("transcript_path"),
                                               payload.get("session_id"), agent_id))
        if totals is None:
            return None
        record = remember(state, agent_id,
                          agent_name(response.get("agentType"), totals["agent_type"]), totals)
    elif record.get("reported"):
        return None
    record["reported"] = True
    save_state(path, state)
    line, ratio = agent_line(agent_name(record.get("agent_type")), record.get("output", 0),
                             record.get("tool_calls", 0),
                             row_for(table, record.get("agent_type")), nudges)
    return [line] if shows(mode, ratio, nudges) else None


def on_prompt(payload, env):
    """The turn line, then the subagents that finished since the previous prompt."""
    table, mode, nudges = settings(env)
    if mode == "off":
        return None
    path = state_path(payload.get("session_id"), env)
    if path is None:
        return None
    state = advance(load_state(path), payload.get("transcript_path"))
    lines = [turn_line(state)] if mode == "every-turn" else []
    listed = []
    for record in state["records"]:
        if record.get("reported"):
            continue
        # Reported means said once, whether or not it cleared the threshold to be printed.
        record["reported"] = True
        line, ratio = agent_line(agent_name(record.get("agent_type")), record.get("output", 0),
                                 record.get("tool_calls", 0),
                                 row_for(table, record.get("agent_type")), nudges)
        if shows(mode, ratio, nudges):
            listed.append(line)
    save_state(path, state)
    lines.extend(listed[:MAX_LISTED])
    if len(listed) > MAX_LISTED:
        lines.append("… and " + str(len(listed) - MAX_LISTED) + " more")
    return lines or None


def run(payload, env=None):
    """The lines one event produces, or None. The parent thread is the only place a feed runs."""
    env = os.environ if env is None else env
    kind = payload.get("hook_event_name") or ""
    if kind == "SubagentStop":
        # The only event whose `agent_id` names somebody else: it fires in the parent's hooks.
        return on_subagent_stop(payload, env)
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
