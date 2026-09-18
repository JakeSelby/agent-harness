#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stop hook: run the repository's own gate and refuse to finish while it is red.

Opt-in per repository — the gate is the fenced block under the `## Gate` heading of the
repo's `AGENTS.md`, executed together in one shell. A repo without that block is untouched.
Trusted folders only: the block is a repository's own text, so it runs only where Claude
Code's folder-trust dialog has been accepted (the `hasTrustDialogAccepted` flag it records
per project), the same consent that gates a repository's `.claude/settings.json` hooks, or
where the root is listed in ~/.config/agent-harness/trusted.txt by `harness trust`.
Bounded: after MAX_BLOCKS consecutive blocks the turn is released, so a gate that can never
pass cannot trap a session. A timeout releases the turn as unverified; unexpected errors block. Neither records success.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_BLOCKS = 8
BUDGET_SECONDS = 240
TAIL_LINES = 30
GATE_FILES = ("AGENTS.md", "CLAUDE.md")
STATE = Path.home() / ".local" / "state" / "agent-harness" / "stop-gate"
TRUSTED = Path.home() / ".config" / "agent-harness" / "trusted.txt"


def git(root, *args):
    try:
        out = subprocess.run(["git", "-C", root, *args],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return ""
    return out.stdout if out.returncode == 0 else ""


def git_root(cwd):
    root = git(cwd, "rev-parse", "--show-toplevel").strip()
    return root or None


def claude_config():
    """Claude Code's per-user state file, honouring CLAUDE_CONFIG_DIR."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config_dir) if config_dir else Path.home()) / ".claude.json"


def listed_roots():
    """Roots recorded by `harness trust`, as written and resolved."""
    try:
        lines = TRUSTED.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    roots = set()
    for ln in lines:
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            roots.update((ln, str(Path(ln).resolve())))
    return roots


def trusted(root, cwd):
    """True when the folder-trust dialog has been accepted for the working directory, the
    repository root, or a directory between them, or when `harness trust` listed the root."""
    if os.environ.get("HARNESS_RUNTIME") == "codex":
        return bool(listed_roots() & {str(Path(root)), str(Path(root).resolve())})
    try:
        projects = json.loads(claude_config().read_text(encoding="utf-8")).get("projects") or {}
    except Exception:
        projects = {}
    if not isinstance(projects, dict):
        projects = {}
    top = Path(root).resolve()
    if listed_roots() & {str(Path(root)), str(top)}:
        return True
    keys = {str(Path(root)), str(top)}
    path = Path(cwd)
    while path.resolve() == top or top in path.resolve().parents:
        keys.update((str(path), str(path.resolve())))  # symlinked temp dirs record either form
        if path.resolve() == top:
            break
        path = path.parent
    return any(isinstance(projects.get(k), dict) and projects[k].get("hasTrustDialogAccepted") is True
               for k in keys)


def gate_file(root):
    for name in GATE_FILES:
        path = Path(root) / name
        if path.is_file():
            return path
    return None


def gate_commands(root):
    path = gate_file(root)
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    start = None
    for i, raw in enumerate(lines):
        if raw.strip().lower() == "## gate":
            start = i + 1
            break
    if start is None:
        return []
    commands = []
    fenced = False
    for raw in lines[start:]:
        text = raw.strip()
        if text.startswith("```"):
            if fenced:
                break
            fenced = True
        elif not fenced:
            if text.startswith("#"):  # the next heading, with no block between
                break
        elif text and not text.startswith("#"):
            commands.append(text)
    return commands


def tree_hash(root):
    digest = hashlib.sha256()
    digest.update(("gate-v2:" + str(Path(root).resolve())).encode())
    def checked(*args):
        return subprocess.run(["git", "-C", root, *args], capture_output=True,
                              check=True, timeout=10).stdout
    for args in (("rev-parse", "HEAD"), ("status", "--porcelain", "-z"),
                 ("diff", "--binary"), ("diff", "--cached", "--binary")):
        digest.update(hashlib.sha256(checked(*args)).digest())
    for name in checked("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not name:
            continue
        path = Path(root) / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.is_symlink():
            digest.update(os.fsencode(os.readlink(path)))
        elif path.is_file():
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    digest.update("\n".join(gate_commands(root)).encode())
    digest.update(str(BUDGET_SECONDS).encode())
    return digest.hexdigest()


def state_path(root):
    return STATE / (hashlib.sha256(root.encode("utf-8")).hexdigest() + ".json")


def read_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".gate-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_gate(root, commands):
    """The first red command as (command, exit code, output), or None when every one passes."""
    cmd = "\n".join(commands)
    out = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", cmd], cwd=root,
                         capture_output=True, text=True, timeout=BUDGET_SECONDS)
    if out.returncode != 0:
        return cmd, out.returncode, (out.stdout or "") + (out.stderr or "")
    return None


def reason(path, cmd, code, output):
    tail = "\n".join(output.splitlines()[-TAIL_LINES:]).strip()
    return (
        f"The gate in {path.name} is red: `{cmd}` exited {code}.\n\n"
        f"{tail}\n\n"
        "That command is the check block this repository defines under `## Gate`, run at the end "
        "of a turn once files have changed. Fix it and finish, or say why it cannot pass."
    )


def release(path, state, session, note):
    write_state(path, {"green_hash": None, "status": "unverified", "reason": note,
                       "blocks": 0, "session_id": session})
    sys.stderr.write("stop-gate: " + note + "\n")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    cwd = payload.get("cwd") or os.getcwd()
    root = git_root(cwd)
    if not root:
        return
    commands = gate_commands(root)
    if not commands:
        return
    if not trusted(root, cwd):
        sys.stderr.write("stop-gate: folder not trusted in Claude Code and not listed by "
                         "`harness trust`; gate skipped. Run `harness trust .` in this folder to "
                         "let it run the repository's own checks.\n")
        return

    current = tree_hash(root)
    path = state_path(root)
    state = read_state(path)
    if state.get("green_hash") == current:
        return

    session = payload.get("session_id") or ""
    try:
        failure = run_gate(root, commands)
    except subprocess.TimeoutExpired:
        release(path, state, session, f"gate ran past {BUDGET_SECONDS}s; letting the turn end")
        return
    if failure is None:
        if tree_hash(root) != current:
            release(path, state, session, "working tree changed during the gate; result unverified")
            return
        write_state(path, {"green_hash": current, "status": "passed", "blocks": 0, "session_id": session})
        return

    try:
        blocks = int(state.get("blocks", 0)) if state.get("session_id") == session else 0
    except (TypeError, ValueError):
        blocks = 0
    blocks += 1
    if blocks >= MAX_BLOCKS:
        release(path, state, session, f"released after {MAX_BLOCKS} blocks; gate still red")
        return
    write_state(path, {"green_hash": None, "status": "failed", "blocks": blocks, "session_id": session})
    cmd, code, output = failure
    print(json.dumps({"decision": "block", "reason": reason(gate_file(root), cmd, code, output)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"decision": "block", "reason": "Gate is unverified: " + str(exc)}))
