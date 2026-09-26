#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SessionStart hook: the other folders of this session's workspace, and their instructions.

`lib/harness_core/workspaces.py` decides which workspace the session's folder belongs to; this
hook supplies what the surface does not load itself. Claude Code loads an added folder's
`CLAUDE.md` and rules only when `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` and the folder
was passed as `--add-dir`, so a member counts as loaded natively only when the variable is in
this hook's environment, the member is an `--add-dir` argument of `CLAUDE_PID`, and it has a
`CLAUDE.md`; a member with only `AGENTS.md` is always supplied. Codex loads nothing from an added
folder, so every member is supplied there.

It has its own SessionStart entry, and so its own 10,000-character output cap. A block of at most
`INLINE_LIMIT` characters goes inline; a longer one is written to
`~/.local/state/agent-harness/workspaces/<name>.md` and only the member list and that path are
inlined. Silent while `workspaces_dir` is unset or the folder is in no workspace; any failure
returns nothing, so a session is never blocked. Test:

    echo '{"hook_event_name":"SessionStart","cwd":"'"$PWD"'"}' | python3 workspace-session.py
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
LIB = HOOKS.parents[1] / "lib" / "harness_core" / "workspaces.py"
NATIVE_VAR = "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"
INLINE_LIMIT = 9000
BUDGET_SECONDS = 4.0

_started = time.monotonic()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config(env):
    """The resolved configuration, from the file `posture.config_path` names."""
    posture = _load("harness_posture", HOOKS / "posture.py")
    try:
        with open(str(posture.config_path(env)), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def bundle_dir(env):
    return Path(env.get("HOME") or Path.home()) / ".local" / "state" / "agent-harness" / "workspaces"


def parent_command(pid):
    """The parent runtime's argument vector, or [] when it cannot be read inside the budget."""
    if not pid or not str(pid).isdigit():
        return []
    proc = Path("/proc") / str(pid) / "cmdline"
    if proc.is_file():
        try:
            return [a for a in proc.read_bytes().decode("utf-8", "replace").split("\0") if a]
        except OSError:
            return []
    try:
        done = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True,
                              text=True, timeout=max(0.2, BUDGET_SECONDS / 4))
    except (OSError, subprocess.SubprocessError):
        return []
    # `ps` joins the vector with spaces, so a path holding one is matched by `add_dir_listed`.
    return done.stdout.split() if done.returncode == 0 else []


def add_dirs(argv, base):
    """Every folder passed as `--add-dir`, which takes one or more values, or `--add-dir=<path>`."""
    found, taking = [], False
    for arg in argv:
        if arg == "--add-dir":
            taking = True
            continue
        if arg.startswith("--add-dir="):
            found.append(arg.split("=", 1)[1])
            taking = False
            continue
        if arg.startswith("-"):
            taking = False
            continue
        if taking:
            found.append(arg)
    return [os.path.realpath(os.path.join(base, os.path.expanduser(p))) for p in found]


def add_dir_listed(member, given, argv):
    """Whether `member` was an `--add-dir`: by realpath, or by its literal text in the command."""
    if member in given:
        return True
    text = " " + " ".join(argv) + " "
    at = text.find(" --add-dir")
    return at >= 0 and (" " + member + " ") in text[at:]


def classify(members, folder, env, runtime, given, argv):
    """[(member, status)] for every member but the session's own: `native` or `supplied`."""
    native_on = runtime == "claude-code" and env.get(NATIVE_VAR) == "1"
    out = []
    for member in members:
        if member == folder:
            continue
        loaded = (native_on and os.path.isfile(os.path.join(member, "CLAUDE.md"))
                  and add_dir_listed(member, given, argv))
        out.append((member, "native" if loaded else "supplied"))
    return out


def instructions(ws_module, supplied):
    """The instruction text for the supplied members, and the path-scoped rules left out of it."""
    parts = []
    for member in supplied:
        found = ws_module.member_instructions(member)
        for path, text in found["files"]:
            parts.append("### " + path + "\n\n" + text.strip())
        if found["scoped"]:
            parts.append("### Path-scoped rules in " + member + "\n\nRead each before working on "
                         "files it covers:\n" + "\n".join("- " + p for p in found["scoped"]))
    return "\n\n".join(parts)


LABELS = {"native": "loaded natively", "supplied": "supplied by this hook"}


def header(ws, folder, rule, statuses):
    lines = ["Workspace " + ws["name"] + " (decided by: " + rule + "). This session's folder "
             + folder + " works together with these folders; follow their instructions when "
             "working in them:"]
    lines.extend("- " + member + ": " + LABELS[status] for member, status in statuses)
    lines.extend("- " + missing + ": missing, skipped" for missing in ws.get("missing", []))
    return "\n".join(lines)


def desktop_line(env):
    if env.get("CLAUDE_CODE_ENTRYPOINT") != "claude-desktop":
        return None
    return ("Before first reading or editing in a member folder, ask the app for that folder with "
            "the desktop folder-grant tool (`request_directory`, a deferred tool found through tool "
            "search); do not request them all now. The app passes a granted folder as --add-dir "
            "from this chat's next launch.")


def write_bundle(directory, name, text):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (re.sub(r"[^A-Za-z0-9._-]", "_", name) + ".md")
    fd, temp = tempfile.mkstemp(dir=str(directory), prefix=".bundle-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, str(target))
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
    return target


def context(event, env=None):
    """The block for this session, or None when there is nothing to say."""
    env = os.environ if env is None else env
    directory = config(env).get("workspaces_dir")
    if not isinstance(directory, str) or not directory.strip():
        return None
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        return None
    ws_module = _load("harness_workspaces", LIB)
    cwd = event.get("cwd") or env.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    runtime = env.get("HARNESS_RUNTIME", "claude-code")
    argv = parent_command(env.get("CLAUDE_PID")) if runtime == "claude-code" else []
    given = add_dirs(argv[1:], cwd)
    result = ws_module.resolve(cwd, directory, env=env, add_dirs=given)
    if result["rule"] == "ambiguous":
        return ("This folder is in the workspaces " + ", ".join(result["candidates"])
                + " and none was attached. Pin one in "
                + os.path.join(directory, ws_module.OVERRIDES)
                + ", or launch with `citizen workspace open <name>`.")
    ws = result["workspace"]
    if ws is None:
        return None
    statuses = classify(result["members"], result["folder"], env, runtime, set(given), argv)
    if not statuses and not ws.get("missing"):
        return None
    head = header(ws, result["folder"], result["rule"], statuses)
    grant = desktop_line(env)
    if grant:
        head += "\n\n" + grant
    body = instructions(ws_module, [m for m, s in statuses if s == "supplied"])
    whole = head + ("\n\n## Member instructions\n\n" + body if body else "")
    if len(whole) <= INLINE_LIMIT:
        return whole
    path = write_bundle(bundle_dir(env), ws["name"], "# Workspace " + ws["name"]
                        + " member instructions\n\n" + body + "\n")
    return (head + "\n\nThe supplied members' instructions (" + str(len(body)) + " characters) "
            "are part of your instructions for this session, but too long to show here: they are "
            "in " + str(path) + ". Read that file with your file-reading tool now, before you "
            "answer or take any other action.")


def main():
    try:
        event = json.loads(sys.stdin.read() or "{}")
        text = context(event if isinstance(event, dict) else {})
    except Exception:
        text = None
    if text and time.monotonic() - _started <= BUDGET_SECONDS:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": text}}))
    else:
        print("{}")


if __name__ == "__main__":
    main()
