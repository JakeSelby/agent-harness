#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SessionEnd hook: record a session's token usage in ~/.local/state/agent-harness/usage.jsonl.

One local file, nothing over the network. SessionEnd shares a 1.5-second budget, so the hook
spawns a detached worker and returns; the worker streams the transcript line by line and upserts
one record keyed by session id. Read it with `harness usage`.
"""
import json
import os
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


def scan(transcript, session_id="", cwd=""):
    """One record from one transcript, or None when there is nothing worth recording."""
    totals = {name: 0 for name, _ in FIELDS}
    models, agents, seen = [], set(), set()
    started = ended = branch = ""
    turns = 0
    try:
        handle = open(os.path.expanduser(str(transcript)), encoding="utf-8", errors="replace")
    except OSError:
        return None
    with handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            stamp = entry.get("timestamp") or ""
            if stamp:
                started = stamp if not started or stamp < started else started
                ended = stamp if stamp > ended else ended
            session_id = session_id or entry.get("sessionId") or ""
            cwd = cwd or entry.get("cwd") or ""
            branch = entry.get("gitBranch") or branch
            if entry.get("type") != "assistant":
                continue
            message = entry.get("message") or {}
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Agent":
                    agents.add(block.get("id") or len(agents))
            # One API response is written as several entries, each repeating the same `usage`
            # object, so token sums must be taken once per message id, not once per line.
            mid = message.get("id")
            if mid and mid in seen:
                continue
            seen.add(mid)
            turns += 1
            model = message.get("model")
            if model and model not in models:
                models.append(model)
            usage = message.get("usage") or {}
            for name, key in FIELDS:
                try:
                    totals[name] += int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    pass
    if not session_id or not turns:
        return None
    top = git(cwd, "rev-parse", "--show-toplevel") if cwd and os.path.isdir(cwd) else ""
    record = {
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
    return record


def upsert(record, path=None):
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
            if isinstance(row, dict) and row.get("session_id") != record["session_id"]:
                rows.append(row)
        rows.append(record)
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


def rescan(days=30):
    cutoff = time.time() - max(days, 0) * 86400
    found = 0
    for path in sorted(projects_dir().glob("*/*.jsonl")):
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        record = scan(path)
        if record:
            upsert(record)
            found += 1
    return found


def main(argv):
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
    except Exception:
        sys.exit(0)
