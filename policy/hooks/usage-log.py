#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SessionEnd hook: record a session's token usage in ~/.local/state/agent-harness/usage.jsonl.

One local file, nothing over the network. SessionEnd shares a 1.5-second budget, so the hook
spawns a detached worker and returns; the worker streams the transcript line by line and upserts
one record keyed by session id. Read it with `harness usage`.

The same pass builds the event list `rule-detectors.py` documents, so the rule telemetry costs
one read of the transcript rather than two: the record gains `rules`, `counts` and `stances`.
A registry that will not import costs the record its `rules` key and nothing else.
"""
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from harness_core import preferences

FIELDS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
)

# The eight dimensions `bin/harness` resolves and the variant each falls back to, which is
# `config.example.json`'s — the file the CLI layers the user config over, and a test here holds
# the two together. Resolution is that same ladder: defaults, then the user config, then
# `HARNESS_STANCE_<NAME>` (upper-cased, hyphens as underscores), which hooks inherit.
DEFAULT_STANCES = preferences.read(preferences.ROOT / "config.example.json")["stances"]

# A tool result worth keeping the text of: the two the detectors read. 64 KB is far past any
# brief or fenced block and far short of a transcript's largest result.
TEXT_KEPT_FOR = ("Bash", "Agent")
MAX_RESULT_TEXT = 64 * 1024


def detectors():
    """The sibling detector registry. Raises, so the caller can record why it is absent."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rule-detectors.py")
    spec = importlib.util.spec_from_file_location("harness_rule_detectors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stances(env=None):
    return preferences.current(env=env)["stances"]


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


def scan(transcript, session_id="", cwd="", prior=None, rescan=False):
    """One record from one transcript, or None when there is nothing worth recording.

    `prior` is the record this session already has, when there is one; `rescan` says the read
    is a backfill rather than the session's own end. Together they decide the `stances` field,
    which a backfill can only guess at.
    """
    totals = {name: 0 for name, _ in FIELDS}
    models, agents, seen = [], set(), set()
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
                    agents.add(block.get("id") or len(agents))
            # The same repetition is why the token sums are taken once per message id, not
            # once per line: every one of those lines repeats the same `usage` object.
            if mid and mid in seen:
                continue
            seen.add(mid)
            turns += 1
            if model and model not in models:
                models.append(model)
            usage = message.get("usage") or {}
            for name, key in FIELDS:
                try:
                    totals[name] += int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    pass
    if pending_final is not None:
        pending_final["final"] = True
    if not session_id or not turns:
        return None
    top = git(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    record = {
        "runtime": "claude-code",
        "runtime_version": None,
        "session_id": session_id,
        "repo": os.path.basename(top or str(cwd).rstrip("/")),
        "branch": (git(cwd, "rev-parse", "--abbrev-ref", "HEAD") if top else "") or branch,
        "models": models,
        "started": started,
        "ended": ended,
    }
    for name, _ in FIELDS:
        record[name] = totals[name]
    record["subagents"] = len(agents)
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
        record["operational_settings"] = (prior or {}).get("operational_settings") or preferences.current()["settings"]
        record["settings_source"] = (prior or {}).get("settings_source", "rescan" if rescan else "session")
        module = detectors()
        record["counts"] = module.counts(events)
        errors = []
        record["rules"] = dict((did, len(hits))
                               for did, hits in module.run(events, record["stances"], errors=errors, settings=record["operational_settings"]).items())
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
    record = {"runtime": "codex", "runtime_version": meta.get("cli_version"), "session_id": session_id,
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
        record["operational_settings"] = (prior or {}).get("operational_settings") or preferences.current()["settings"]
        record["settings_source"] = (prior or {}).get("settings_source", "rescan" if rescan else "session")
        module = detectors()
        record["counts"] = module.counts(events)
        record["rules"] = {did: len(hits) for did, hits in module.run(events, record["stances"], errors=errors, settings=record["operational_settings"]).items()}
        if errors:
            record["rules_errors"] = errors
    except Exception as exc:
        record["rules_error"] = type(exc).__name__
    return record


def upsert(record, path=None):
    options = preferences.current()["settings"]["observability"]
    if not options["enabled"]:
        return None
    record = dict(record)
    for field in ("repo", "branch"):
        if not options["include_" + field]:
            record.pop(field, None)
    first_recorded = record.get("recorded_at")
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
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                if (row.get("session_id"), row.get("runtime", "claude-code")) == (record["session_id"], record.get("runtime", "claude-code")):
                    first_recorded = row.get("recorded_at") or first_recorded
                else:
                    rows.append(row)
        record["recorded_at"] = first_recorded or datetime.now(timezone.utc).isoformat()
        rows.append(record)
        if options["retention_days"]:
            cutoff = time.time() - options["retention_days"] * 86400
            def keep(row):
                value = row.get("ended") or row.get("recorded_at")
                try:
                    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    return stamp.tzinfo is None or stamp.timestamp() >= cutoff
                except (ValueError, TypeError):
                    return True  # unknown age is not proof that a record expired
            rows = [row for row in rows if keep(row)]
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
        if isinstance(row, dict) and row.get("session_id"):
            out[row["session_id"]] = row
    return out


def rescan(days=30):
    if not preferences.current()["settings"]["observability"]["enabled"]:
        return 0
    cutoff = time.time() - max(days, 0) * 86400
    prior = recorded()
    found = 0
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    paths = list(projects_dir().glob("*/*.jsonl")) + list((codex_home / "sessions").rglob("*.jsonl"))
    for path in sorted(paths):
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
        record = scan(path, prior=prior.get(ident), rescan=True)
        if record:
            upsert(record)
            found += 1
    return found


def main(argv):
    if not preferences.current()["settings"]["observability"]["enabled"]:
        return 0
    if argv and argv[0] == "--worker":
        transcript, session_id, cwd = (list(argv[1:]) + ["", "", ""])[:3]
        record = scan(transcript, session_id, cwd)
        if record:
            upsert(record)
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
