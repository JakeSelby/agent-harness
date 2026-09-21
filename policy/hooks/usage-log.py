#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SessionEnd hook: record a session's token usage in ~/.local/state/agent-harness/usage.jsonl.

One local file, nothing over the network. SessionEnd shares a 1.5-second budget, so the hook
spawns a detached worker and returns; the worker streams the transcript line by line and upserts
one row for the session, one for each subagent it spawned and one for each recent role-run
worker. Read it with `harness usage`.

The same pass builds the event list `rule-detectors.py` documents, so the rule telemetry costs
one read of the transcript rather than two: the record gains `rules`, `counts` and `stances`.
A registry that will not import costs the record its `rules` key and nothing else.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

FIELDS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
)

# A tool result worth keeping the text of: the two the detectors read. 64 KB is far past any
# brief or fenced block and far short of a transcript's largest result.
TEXT_KEPT_FOR = ("Bash", "Agent")
MAX_RESULT_TEXT = 64 * 1024


def sibling(name, required=True):
    """A module beside this one. Raises when required, so the caller can record why it is absent."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    try:
        spec = importlib.util.spec_from_file_location("harness_" + name.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        if required:
            raise
        return None


def detectors():
    """The sibling detector registry. Raises, so the caller can record why it is absent."""
    return sibling("rule-detectors")


def stances(env=None):
    """The resolved `{dimension: variant}` map, from `posture.py` and nowhere else.

    A copy of this hook running away from its sibling resolver records no stances rather
    than a second opinion about them; the record keeps every other field.
    """
    module = sibling("posture", required=False)
    return module.resolve(env, strict=False)["stances"] if module else {}


# Re-exported, not re-declared: the defaults are `posture.py`'s, and a reader of a usage record
# should not have to know which file holds them.
DEFAULT_STANCES = getattr(sibling("posture", required=False), "DEFAULT_STANCES", {})


def usage_path():
    return Path.home() / ".local" / "state" / "agent-harness" / "usage.jsonl"


def projects_dir():
    return Path.home() / ".claude" / "projects"


def git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, timeout=5)
    except Exception:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _result_text(content, tool_name):
    """A tool result's text, whether the transcript wrote a string or a block list.

    Only the two tools a detector reads keep their text, and only the first 64 KB of it: the
    event list is held whole in memory, and a `Read` of a large file would otherwise be carried
    through the entire scan for nothing.
    """
    if tool_name not in TEXT_KEPT_FOR:
        return ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(b.get("text") or "" for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    else:
        return ""
    return text[:MAX_RESULT_TEXT]


def record_usage(per_message, key, usage):
    """Keep the largest figure a message id ever reported for each field.

    One API response is written as several records. The early ones carry a partial streaming
    `output_tokens` and the last carries the true figure, so taking the first undercounts the
    response badly — on a real subagent transcript, 7,126 output tokens against 40,868. The
    field-wise maximum keeps the final figure without trusting the file's order, which a
    reordered or truncated tail would otherwise lower.
    """
    slot = per_message.setdefault(key, {name: 0 for name, _ in FIELDS})
    for name, field in FIELDS:
        try:
            value = int(usage.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if value > slot[name]:
            slot[name] = value


def summed(per_message):
    """The four token totals over the messages, each counted once at its largest figure."""
    return {name: sum(slot[name] for slot in per_message.values()) for name, _ in FIELDS}


def reported_model(counts):
    """The model a transcript's assistant records name most often; the later one on a tie.

    A record is one vote, so a response written as several records weighs as much as it cost to
    write. The tie-break is the last model seen, because a session that changed model mid-run
    ran most recently on the later one.
    """
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]


def note_model(counts, name, order):
    """One assistant record's model against the tally: `{name: (hits, last seen)}`."""
    if not isinstance(name, str) or not name:
        return
    hits = counts.get(name, (0, 0))[0]
    counts[name] = (hits + 1, order)


def _agent_row(path, shared=None, budget=None, max_bytes=None):
    """One `kind: "subagent"` row from one `agent-<id>.jsonl`, or None when it holds no turn.

    The sibling `agent-<id>.meta.json` names the agent type and the spawn depth; the transcript
    carries the tokens, the tool calls, the model and, on some records, the effort. Counts only:
    no prompt text and no command text reaches the record.

    The model is the transcript's, not the meta file's: a routed spawn's meta carries the alias
    the spawn hook asked for while a directly spawned agent's carries the full id, and
    one model under two names splits `usage --by model` in half. The alias is the fallback for
    an agent that recorded no model at all.

    `shared` is the session's message-id map. The row keeps its own total, but the session's
    total is taken over that shared map, so a message id written both here and as a sidechain
    line in the session file is one message and is paid for once.

    `budget` in seconds and `max_bytes` from the tail are for a caller working against a hook
    timeout: the detached `SessionEnd` worker has all the time in the world and passes neither,
    while a live hook cannot be killed halfway through a very large agent's file. When either
    bites, the row carries `partial: True` and its totals are of the part that was read.
    """
    per_message, anonymous = {}, 0
    partial = False
    try:
        meta = json.loads(path.with_name(path.stem + ".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    seen, tools, models = set(), set(), {}
    calls = turns = records = 0
    effort = started = ended = ""
    try:
        handle = path.open("rb")
    except OSError:
        return None
    deadline = None if budget is None else time.monotonic() + budget
    with handle:
        if max_bytes:
            try:
                size = os.fstat(handle.fileno()).st_size
            except OSError:
                size = 0
            if size > max_bytes:
                # The tail, because the last responses carry the largest figures and a file
                # this size will not be finished inside a hook's timeout either way.
                handle.seek(size - max_bytes)
                handle.readline()
                partial = True
        for index, raw in enumerate(handle):
            if deadline is not None and not index % 256 and time.monotonic() > deadline:
                partial = True
                break
            try:
                entry = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            stamp = entry.get("timestamp") or ""
            if stamp:
                started = stamp if not started or stamp < started else started
                ended = stamp if stamp > ended else ended
            if not effort and isinstance(entry.get("effort"), str):
                effort = entry["effort"].strip()
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            mid = message.get("id")
            records += 1
            note_model(models, message.get("model"), records)
            for index, block in enumerate(message.get("content") or []):
                # The same block-repetition the session scan guards against: one API response
                # is written as several lines that repeat its blocks.
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                key = block.get("id") or (mid, block.get("apiBlockIndex", index))
                if key in tools:
                    continue
                tools.add(key)
                calls += 1
            usage = message.get("usage") or {}
            # A line with no message id cannot be matched across files, so its key names the
            # file it came from: two such lines from two sources are two messages, not one.
            key = mid if mid else ("line", str(path), anonymous)
            if not mid:
                anonymous += 1
            record_usage(per_message, key, usage)
            if shared is not None:
                record_usage(shared, key, usage)
            if mid and mid in seen:
                continue
            seen.add(mid)
            turns += 1
    if not turns:
        # Nothing readable, whether the file held no turn or the budget stopped before one:
        # the caller records that as spend unknown rather than as zero.
        return None
    workflow = path.parent.name if path.parent.name.startswith("wf_") else None
    row = {"kind": "subagent", "runtime": "claude-code", "session_id": "", "repo": "",
           "agent_id": path.stem[len("agent-"):],
           # A Workflow-tool agent may have no meta file at all; unnamed is a fact about the
           # record, and "unknown" says so where an empty string would read as a missing field.
           "agent_type": meta.get("agentType") or "unknown",
           "model": reported_model(models) or meta.get("model") or "",
           "effort": effort or meta.get("effort") or "",
           "tool_calls": calls, "spawn_depth": meta.get("spawnDepth"), "workflow": workflow,
           # `mark_reroutes` fills these from the parent's record of the call, joined on this id.
           "tool_use_id": meta.get("toolUseId") or "",
           "requested_type": "", "rerouted": False,
           "turns": turns, "started": started, "ended": ended}
    if partial:
        row["partial"] = True
    row.update(summed(per_message))
    return row


# The two spellings of "this spawn named no agent definition"; they are one request, so a spawn
# that ran as `general-purpose` after asking for nothing was not rerouted.
UNNAMED_TYPES = ("", "general-purpose")
# A requested type is model-authored text. Only a name the tool could actually have resolved is
# kept; anything else is recorded as the fact that it was something else, because a usage row is
# a count and must not become a place free text is stored.
AGENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def mark_reroutes(agents, requested):
    """Fill `requested_type` and `rerouted` from the parent's `Agent` inputs, joined on tool use id.

    A transcript records a tool input as the model wrote it, before any `PreToolUse` hook
    rewrote it, while the subagent's `.meta.json` records the type it actually ran as. The two
    disagreeing is the reroute — measured from what happened, never announced by the hook that
    did it, so orchestrator compliance is a number and not a claim. Verified on a real
    transcript: the parent recorded `general-purpose`, the subagent's meta said `Explore`,
    under the one tool use id.
    """
    for row in agents:
        use_id = row.get("tool_use_id")
        if not use_id or use_id not in requested:
            continue
        asked = requested[use_id]
        asked = asked.strip() if isinstance(asked, str) else ""
        ran = row.get("agent_type") or ""
        row["requested_type"] = asked if not asked or AGENT_NAME.fullmatch(asked) else "other"
        if ran and ran != "unknown":
            row["rerouted"] = asked != ran and not (asked in UNNAMED_TYPES and ran in UNNAMED_TYPES)


def agent_rows(transcript, session_id="", shared=None):
    """Every subagent row belonging to one session transcript, by path.

    Claude Code writes each subagent to `<session>/subagents/agent-<id>.jsonl` beside the
    session's own `<session>.jsonl`, and a Workflow-tool agent one level deeper still, under
    `subagents/workflows/wf_<id>/`. The walk is recursive for that reason. Those tokens were
    spent by this session, so the session row counts them too; the per-agent rows are what
    makes `usage --by role` true.
    """
    path = Path(os.path.expanduser(str(transcript)))
    rows = []
    try:
        files = sorted((path.with_suffix("") / "subagents").rglob("agent-*.jsonl"))
    except OSError:
        return rows
    for file in files:
        row = _agent_row(file, shared)
        if row:
            row["session_id"] = session_id or path.stem
            rows.append(row)
    return rows


def scan_all(transcript, session_id="", cwd="", prior=None, rescan=False):
    """Every row one transcript yields: the session first, then one row per subagent."""
    shared = {}
    agents = agent_rows(transcript, session_id, shared)
    record = scan(transcript, session_id, cwd, prior, rescan, agents=agents, shared=shared)
    if record is None:
        return []
    if record.get("runtime") != "claude-code":
        return [record]
    for row in agents:
        row["session_id"] = record["session_id"]
        row["repo"] = record.get("repo", "")
    return [record] + agents


def scan(transcript, session_id="", cwd="", prior=None, rescan=False, agents=None, shared=None):
    """One record from one transcript, or None when there is nothing worth recording.

    `prior` is the record this session already has, when there is one; `rescan` says the read
    is a backfill rather than the session's own end. Together they decide the `stances` field,
    which a backfill can only guess at. `agents` is the subagent rows when the caller has
    already read them, so `scan_all` reads each subagent file once rather than twice, and
    `shared` is the message-id map those reads filled.

    The session's totals are taken over that one map, never as a sum of two sources. Older
    Claude Code wrote a subagent's turns into the session file as sidechain lines while newer
    Claude Code writes them to the subagent's own file; a transcript carrying both would pay
    for every delegated token twice if the two were added.
    """
    per_message = {} if shared is None else shared
    anonymous = 0
    models, agent_calls, seen, requested = [], set(), set(), {}
    started = ended = branch = ""
    turns = 0
    events, tool_names, blocks_seen = [], {}, set()
    turn, pending_final = 0, None
    try:
        handle = open(os.path.expanduser(str(transcript)), encoding="utf-8", errors="replace")
    except OSError:
        return None
    with handle:
        first = handle.readline()
        handle.seek(0)
        if '"session_meta"' in first:
            return scan_codex(transcript, session_id, cwd, prior, rescan)
        if agents is None:
            agents = agent_rows(transcript, session_id, per_message)
        for line in handle:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            # A subagent has its own transcript file today, but older Claude Code wrote its
            # turns into this one as sidechain lines. They are that agent's work, so they make
            # no event here; their tokens were spent by this session and are summed as ever.
            sidechain = bool(entry.get("isSidechain"))
            stamp = entry.get("timestamp") or ""
            if stamp:
                started = stamp if not started or stamp < started else started
                ended = stamp if stamp > ended else ended
            session_id = session_id or entry.get("sessionId") or ""
            cwd = cwd or entry.get("cwd") or ""
            branch = entry.get("gitBranch") or branch
            kind = entry.get("type")
            message = entry.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else None
            mid = message.get("id") if isinstance(message, dict) else None
            if kind == "system":
                if entry.get("subtype") == "compact_boundary" and not sidechain:
                    events.append({"kind": "compact", "turn": turn})
                continue
            if kind == "user":
                blocks = content if isinstance(content, list) else []
                results = [b for b in blocks
                           if isinstance(b, dict) and b.get("type") == "tool_result"]
                if sidechain:
                    continue
                for block in results:
                    tool_use_id = block.get("tool_use_id") or ""
                    name = tool_names.get(tool_use_id, "")
                    events.append({"kind": "tool_result", "turn": turn,
                                   "tool_use_id": tool_use_id, "tool_name": name,
                                   "text": _result_text(block.get("content"), name)})
                if results or entry.get("isMeta") or entry.get("isCompactSummary"):
                    continue
                turn += 1
                if pending_final is not None:
                    pending_final["final"] = True
                    pending_final = None
                events.append({"kind": "user_prompt", "turn": turn})
                continue
            if kind != "assistant":
                continue
            model = message.get("model")
            for index, block in enumerate(content or []):
                # One API response is written as several lines that repeat the same message id,
                # each carrying one block; a block seen twice is one block, not two events.
                if sidechain or not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text") or ""
                    key = ("text", mid, block.get("apiBlockIndex", index), text)
                    if key in blocks_seen:
                        continue
                    blocks_seen.add(key)
                    pending_final = {"kind": "assistant_text", "turn": turn, "text": text,
                                     "final": False, "model": model or ""}
                    events.append(pending_final)
                elif block.get("type") == "tool_use":
                    use_id = block.get("id") or ""
                    key = ("tool_use", mid, block.get("apiBlockIndex", index), use_id)
                    if key in blocks_seen:
                        continue
                    blocks_seen.add(key)
                    tool_names[use_id] = block.get("name") or ""
                    events.append({"kind": "tool_use", "turn": turn, "id": use_id,
                                   "name": block.get("name") or "", "input": block.get("input")})
            for block in content or []:
                if isinstance(block, dict) and block.get("type") == "tool_use" \
                        and block.get("name") == "Agent":
                    agent_calls.add(block.get("id") or len(agent_calls))
                    called = block.get("input")
                    if block.get("id") and isinstance(called, dict):
                        requested.setdefault(block["id"], called.get("subagent_type") or "")
            # The same repetition is why the token sums are taken once per message id, not once
            # per line, and at that id's largest figure rather than its first: the early lines
            # of one response carry a partial streaming count.
            if mid:
                record_usage(per_message, mid, message.get("usage") or {})
            else:
                anonymous += 1
                record_usage(per_message, ("line", "session", anonymous),
                             message.get("usage") or {})
            if mid and mid in seen:
                continue
            seen.add(mid)
            turns += 1
            if model and model not in models:
                models.append(model)
    if pending_final is not None:
        pending_final["final"] = True
    mark_reroutes(agents, requested)
    if not session_id or not turns:
        return None
    totals = summed(per_message)
    top = git(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    record = {
        "kind": "session",
        "runtime": "claude-code",
        "runtime_version": None,
        "session_id": session_id,
        "repo": os.path.basename(top or str(cwd).rstrip("/")),
        "branch": (git(cwd, "rev-parse", "--abbrev-ref", "HEAD") if top else "") or branch,
        "models": models,
        "started": started,
        "ended": ended,
    }
    # A subagent's tokens are the session's bill, so the session row carries them — once,
    # because `totals` is taken over the one map both reads filled. The per-agent rows carry
    # the same tokens again, attributed, which is why no grouping sums both.
    for name, _ in FIELDS:
        record[name] = totals[name]
    record["subagents"] = max(len(agents), len(agent_calls))
    record["turns"] = turns
    # A live SessionEnd write knows the stances the session actually ran under. A rescan does
    # not — the environment it reads is this minute's — so it keeps whatever the record already
    # carries, and stamps a record that has none as a guess, which the report then excludes.
    prior_stances = (prior or {}).get("stances") if isinstance(prior, dict) else None
    if isinstance(prior_stances, dict) and prior_stances:
        record["stances"] = prior_stances
        if (prior or {}).get("stances_source"):
            record["stances_source"] = prior["stances_source"]
    else:
        record["stances"] = stances()
        if rescan:
            record["stances_source"] = "rescan"
    try:
        module = detectors()
        record["counts"] = module.counts(events)
        errors = []
        record["rules"] = dict((did, len(hits))
                               for did, hits in module.run(events, record["stances"], errors=errors).items())
        if errors:
            record["rules_errors"] = errors
    except Exception as exc:
        # A registry that is missing, broken or a version apart costs the record its rule
        # fields and nothing else; the gap is named so a report never reads it as a quiet zero.
        record.pop("counts", None)
        record.pop("rules", None)
        record["rules_error"] = "{}: {}".format(type(exc).__name__, exc).split("\n")[0][:200]
    return record


def scan_codex(transcript, session_id="", cwd="", prior=None, rescan=False):
    events, models, totals, meta = [], [], None, {}
    started = ended = ""
    turn = 0
    tool_names = {}
    malformed = 0
    with open(transcript, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
                payload = item.get("payload") or {}
                if not isinstance(payload, dict):
                    raise ValueError("invalid payload")
            except (ValueError, AttributeError):
                malformed += 1
                continue
            timestamp = item.get("timestamp") or ""
            started = started or timestamp
            ended = timestamp or ended
            if item.get("type") == "session_meta":
                meta = payload
                session_id = session_id or meta.get("id", "")
                cwd = cwd or meta.get("cwd", "")
            elif item.get("type") == "turn_context":
                turn += 1
                if payload.get("model") and payload["model"] not in models:
                    models.append(payload["model"])
            elif item.get("type") == "event_msg" and payload.get("type") == "token_count":
                value = (payload.get("info") or {}).get("total_token_usage")
                if isinstance(value, dict):
                    totals = value  # Cumulative snapshot; summing snapshots double counts usage.
            elif item.get("type") == "response_item":
                kind = payload.get("type")
                call_id = payload.get("call_id", "")
                if kind in ("function_call", "custom_tool_call"):
                    name = payload.get("name", "")
                    name = {"exec_command": "Bash", "spawn_agent": "Agent"}.get(name, name)
                    arguments = payload.get("arguments", payload.get("input", {}))
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            arguments = {"command": arguments}
                    if isinstance(arguments, dict) and "cmd" in arguments:
                        arguments = dict(arguments, command=arguments["cmd"])
                    tool_names[call_id] = name
                    events.append({"kind": "tool_use", "turn": turn, "id": call_id,
                                   "name": name, "input": arguments})
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    name = tool_names.get(call_id, "")
                    events.append({"kind": "tool_result", "turn": turn, "tool_use_id": call_id,
                                   "tool_name": name, "text": _result_text(payload.get("output"), name)})
                elif kind == "message" and payload.get("role") == "assistant":
                    text = "\n".join(x.get("text", "") for x in payload.get("content", []) if isinstance(x, dict))
                    events.append({"kind": "assistant_text", "turn": turn, "text": text,
                                   "final": payload.get("phase") == "final_answer"})
    if not session_id:
        return None
    record = {"kind": "session", "runtime": "codex",
              "runtime_version": meta.get("cli_version"), "session_id": session_id,
              "repo": Path(cwd).name, "branch": git(cwd, "rev-parse", "--abbrev-ref", "HEAD") if cwd else "",
              "models": models, "started": started, "ended": ended, "turns": turn,
              "subagents": sum(e.get("name") == "Agent" and e["kind"] == "tool_use" for e in events),
              "stances": (prior or {}).get("stances") or stances(), "input": None, "output": None,
              "cache_read": None, "cache_write": None, "parse_failures": malformed}
    if rescan and not (prior or {}).get("stances"):
        record["stances_source"] = "rescan"
    if totals:
        cached = totals.get("cached_input_tokens")
        total_input = totals.get("input_tokens")
        record.update(input=max(0, total_input - cached) if isinstance(total_input, int) and isinstance(cached, int) else None,
                      output=totals.get("output_tokens"), cache_read=cached)
    errors = []
    try:
        module = detectors()
        record["counts"] = module.counts(events)
        record["rules"] = {did: len(hits) for did, hits in module.run(events, record["stances"], errors=errors).items()}
        if errors:
            record["rules_errors"] = errors
    except Exception as exc:
        record["rules_error"] = type(exc).__name__
    return record


def row_key(row):
    """What identifies a row. A row written before `kind` existed is a session, as it was."""
    return (row.get("session_id"), row.get("runtime", "claude-code"),
            row.get("kind") or "session", row.get("agent_id") or "")


def upsert(record, path=None):
    """Replace the rows these records identify, or append them. Takes one record or many.

    A batch keeps the last record for a key, so one locked rewrite is what a whole rescan costs.
    """
    records = [record] if isinstance(record, dict) else list(
        {row_key(r): r for r in record}.values())
    if not records:
        return Path(path) if path else usage_path()
    path = Path(path) if path else usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    held = False
    for _ in range(20):
        try:
            os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            held = True
            break
        except FileExistsError:
            time.sleep(0.05)
        except OSError:
            break
    if not held:
        raise RuntimeError("usage lock unavailable; no record was overwritten")
    try:
        rows = []
        replaced = {row_key(r) for r in records}
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict) and row_key(row) not in replaced:
                rows.append(row)
        rows.extend(records)
        tmp = path.with_name("{}.{}.tmp".format(path.name, os.getpid()))
        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if held:
            try:
                lock.unlink()
            except OSError:
                pass
    return path


def recorded(path=None):
    """The records already on file, by session id, so a rescan can keep what it cannot know."""
    try:
        text = (Path(path) if path else usage_path()).read_text(encoding="utf-8")
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("session_id") and (row.get("kind") or "session") == "session":
            out[row["session_id"]] = row
    return out


def workers_dir():
    return Path.home() / ".local" / "state" / "agent-harness" / "workers"


def stamp(epoch):
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(float(epoch)))
    except (TypeError, ValueError):
        return ""


def worker_rows(cutoff=0.0):
    """One `kind: "worker"` row per `harness role run` worker, from its own `status.json`.

    A worker is an isolated CLI session whose runtime reports its own token totals; `workers.py`
    writes them into the status record. A worker that reported none keeps its row and leaves the
    token fields unknown, which the report then excludes from its sums rather than reading as
    zero. The role name is the agent type, so a worker and a subagent group the same way.

    Only a completed run is recorded: a run that timed out, failed or is still running has no
    total worth comparing against another role's. The window is applied by file modification
    time before the file is opened, so a sweep reads the recent runs and not the archive, and
    a record whose own timestamps are unusable is dated by that same mtime rather than by a
    stamp the report could never place in a window.
    """
    rows = []
    try:
        paths = sorted(workers_dir().glob("*/status.json"))
    except OSError:
        return rows
    for path in paths:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or not record.get("id") or not record.get("role"):
            continue
        if record.get("status") != "completed":
            continue
        ended = stamp(record.get("finished_at") or record.get("started_at")) or stamp(mtime)
        usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
        row = {"kind": "worker", "runtime": record.get("runtime") or "claude-code",
               "session_id": record["id"], "agent_id": record["id"],
               "agent_type": record["role"], "repo": os.path.basename(str(record.get("workspace") or "").rstrip("/")),
               "model": record.get("model") or "", "effort": record.get("effort") or "",
               "tool_calls": usage.get("tool_calls"), "spawn_depth": 1, "rerouted": False,
               # A worker is launched by name from the CLI, so there is no requested type and no
               # parent tool call to join on; null is that absence, not an empty answer. Present
               # so every non-session row carries the same keys.
               "requested_type": None, "tool_use_id": None,
               "status": record.get("status"), "stances": record.get("stances") or {},
               "started": stamp(record.get("started_at")) or ended, "ended": ended}
        for name, _ in FIELDS:
            row[name] = usage.get(name)
        rows.append(row)
    return rows


def rescan(days=30):
    """Re-read every transcript in the window and rewrite the file once.

    A backfill of a month reads hundreds of transcripts. Upserting each one separately would
    take the lock and rewrite the whole file that many times, so the rows are collected and
    written in a single locked pass; `SessionEnd` keeps the one-session path.
    """
    cutoff = time.time() - max(days, 0) * 86400
    prior = recorded()
    found, batch = 0, []
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    paths = list(projects_dir().glob("*/*.jsonl")) + list((codex_home / "sessions").rglob("*.jsonl"))
    for path in sorted(paths):
        # A subagent transcript is read from its session, never as one: it carries no session
        # id of its own, so recording it here would invent a session that never ran.
        if path.name.startswith("agent-") or path.parent.name == "subagents":
            continue
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        # A transcript is named for its session, which is how a backfill finds the record it
        # is refreshing before it has read a line of the file.
        ident = path.stem
        try:
            with path.open() as stream:
                first = json.loads(stream.readline())
            if first.get("type") == "session_meta":
                ident = first.get("payload", {}).get("id", ident)
        except (OSError, ValueError):
            pass
        records = scan_all(path, prior=prior.get(ident), rescan=True)
        if records:
            batch.extend(records)
            found += 1
    batch.extend(worker_rows(cutoff))
    if batch:
        upsert(batch)
    return found


def main(argv):
    if argv and argv[0] == "--worker":
        transcript, session_id, cwd = (list(argv[1:]) + ["", "", ""])[:3]
        # Role-run workers have no session of their own to end, so the detached worker that
        # records this session also sweeps the recent ones into rows.
        records = scan_all(transcript, session_id, cwd) + worker_rows(time.time() - 30 * 86400)
        if records:
            upsert(records)
        return 0
    if argv and argv[0] == "--rescan":
        try:
            days = int(argv[1]) if len(argv) > 1 else 30
        except ValueError:
            days = 30
        print("recorded {} session(s) from transcripts of the last {} day(s)".format(rescan(days), days))
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    transcript = (payload or {}).get("transcript_path") or ""
    if not transcript:
        return 0
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--worker", str(transcript),
         payload.get("session_id") or "", payload.get("cwd") or ""],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        failure = usage_path().with_suffix(".errors.jsonl")
        failure.parent.mkdir(parents=True, exist_ok=True)
        with failure.open("a") as stream:
            stream.write(json.dumps({"time": time.time(), "error": type(exc).__name__}) + "\n")
        sys.exit(1)
