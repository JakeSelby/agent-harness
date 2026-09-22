# SPDX-License-Identifier: MIT
"""Launch agents that keep a Claude Code Remote Control server running per configured folder.

One server serves one folder, so the `remote_control.folders` list in the user configuration
becomes one launchd agent each. The harness never accepts a folder's workspace-trust dialog on
the user's behalf: an untrusted folder is reported and skipped, because the server refuses it
and launchd would restart the refusal forever.
"""
import hashlib
import json
import plistlib
import re
from datetime import datetime, timedelta
from pathlib import Path

LABEL_PREFIX = "com.agent-harness.remote-control."
SPAWN_MODES = ("same-dir", "worktree", "session")
PERMISSION_MODES = ("acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")
DEFAULTS = {"folders": [], "spawn": "worktree", "permission_mode": "default", "keep_awake": False}
SYSTEM_PATH = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
# A server that cannot register (folder served from a terminal, no network) exits at once;
# launchd's ten-second default would hammer the registration endpoint.
THROTTLE_SECONDS = 60


def settings(cfg):
    """The `remote_control` block over its defaults, validated; folders resolved and de-duplicated."""
    block = cfg.get("remote_control") or {}
    if not isinstance(block, dict):
        raise ValueError("remote_control must be an object")
    unknown = set(block) - set(DEFAULTS)
    if unknown:
        raise ValueError("unknown remote_control key(s): " + ", ".join(sorted(unknown)))
    out = dict(DEFAULTS, **block)
    if out["spawn"] not in SPAWN_MODES:
        raise ValueError("remote_control.spawn must be one of " + ", ".join(SPAWN_MODES))
    if out["permission_mode"] not in PERMISSION_MODES:
        raise ValueError("remote_control.permission_mode must be one of " + ", ".join(PERMISSION_MODES))
    if not isinstance(out["folders"], list) or not all(isinstance(f, str) and f for f in out["folders"]):
        raise ValueError("remote_control.folders must be a list of paths")
    folders = []
    for raw in out["folders"]:
        folder = Path(raw).expanduser().resolve()
        if folder not in folders:
            folders.append(folder)
    out["folders"] = folders
    out["keep_awake"] = bool(out["keep_awake"])
    return out


def label(folder):
    """Stable launchd label: a readable slug plus a path hash, so two `api` folders never collide."""
    slug = re.sub(r"[^a-z0-9]+", "-", Path(folder).name.lower()).strip("-") or "folder"
    digest = hashlib.sha256(str(folder).encode("utf-8")).hexdigest()[:8]
    return f"{LABEL_PREFIX}{slug}-{digest}"


def command(folder, opts, claude_bin):
    argv = [str(claude_bin), "remote-control", "--name", Path(folder).name,
            "--spawn", opts["spawn"], "--permission-mode", opts["permission_mode"],
            # The pre-created session would reappear as an empty entry after every restart.
            "--no-create-session-in-dir"]
    if opts["keep_awake"]:
        # -i holds idle sleep, -s holds system sleep on AC power; neither survives a closed lid.
        argv = ["/usr/bin/caffeinate", "-is"] + argv
    return argv


def plist(folder, opts, claude_bin, home, log_dir):
    name = label(folder)
    path = [str(Path(claude_bin).parent)] + [p for p in SYSTEM_PATH if p != str(Path(claude_bin).parent)]
    return {
        "Label": name,
        "ProgramArguments": command(folder, opts, claude_bin),
        "WorkingDirectory": str(folder),
        "EnvironmentVariables": {"HOME": str(home), "PATH": ":".join(path)},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": THROTTLE_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(Path(log_dir) / (name + ".log")),
        "StandardErrorPath": str(Path(log_dir) / (name + ".log")),
    }


def render(folder, opts, claude_bin, home, log_dir):
    return plistlib.dumps(plist(folder, opts, claude_bin, home, log_dir), sort_keys=True)


def trusted(folder, claude_json):
    """Whether Claude Code's workspace-trust dialog was accepted for the folder or a parent."""
    try:
        projects = json.loads(Path(claude_json).read_text(encoding="utf-8")).get("projects", {})
    except (OSError, ValueError):
        return False
    if not isinstance(projects, dict):
        return False
    folder = Path(folder)
    for candidate in [folder] + list(folder.parents):
        entry = projects.get(str(candidate))
        if isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True:
            return True
    return False


def installed(agents_dir):
    """Label -> plist path for every agent this module owns."""
    agents_dir = Path(agents_dir)
    if not agents_dir.is_dir():
        return {}
    return {p.stem: p for p in sorted(agents_dir.glob(LABEL_PREFIX + "*.plist"))}


def plan(opts, agents_dir, claude_json):
    """Split the configured folders into those to serve and those to skip, and find stale agents.

    Returns (serve, skipped, stale): folders; (folder, reason) pairs; labels no folder claims.
    """
    serve, skipped = [], []
    for folder in opts["folders"]:
        if not folder.is_dir():
            skipped.append((folder, "not a directory"))
        elif not trusted(folder, claude_json):
            skipped.append((folder, "workspace trust not accepted; run `claude` there once"))
        else:
            serve.append(folder)
    wanted = {label(f) for f in serve}
    stale = [name for name in installed(agents_dir) if name not in wanted]
    return serve, skipped, stale


# --------------------------------------------------------------------------- bridge pointer

HEAL_LABEL = "com.agent-harness.remote-control-heal"
HEAL_INTERVAL_SECONDS = 60
POINTER_NAME = "bridge-pointer.json"
# Claude Code 2.1.278 reuses the environment in a pointer only while the file's mtime is inside
# BRIDGE_POINTER_TTL_MS, so a pointer nobody rewrites expires and the next host registers fresh.
POINTER_TTL_SECONDS = 4 * 60 * 60
# The reader's schema is closed: an unknown key fails validation and the file is deleted.
POINTER_KEYS = ("sessionId", "environmentId", "source", "pid", "procStart",
                "activeSessionIds", "activeSessionIdsPersistedAt",
                "projectThreadSessionIds", "projectThreadSessionIdsPersistedAt")
CARRIED_KEYS = POINTER_KEYS[5:]
ENV_ID = re.compile(r"env_01[A-Za-z0-9]+")
RETRY_LINE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\][^\n]*Connection error, retrying")


def project_slug(folder):
    """Claude Code's per-directory key under `~/.claude/projects`: every other character a dash."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(folder))


def pointer_path(projects_root, folder):
    return Path(projects_root) / project_slug(folder) / POINTER_NAME


def read_pointer(path):
    """The pointer as a dict, or None when it is missing, unreadable or not an object."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def pointer_payload(environment_id, pid, proc_start, previous=None):
    """What the host itself writes, with the previous file's carried session ids kept.

    Only keys the reader validates survive: it rejects the whole file on an unknown one. Ids
    from a different environment are dropped, as the client drops them — a session id is only
    meaningful to the environment it was created on, and `bridge/reconnect` refuses the rest.
    """
    previous = previous if isinstance(previous, dict) else {}
    if previous.get("environmentId") != environment_id:
        previous = {}
    out = {"sessionId": previous.get("sessionId") if isinstance(previous.get("sessionId"), str) else "",
           "environmentId": environment_id,
           "source": "standalone",
           "pid": int(pid),
           "procStart": str(proc_start)}
    for key in CARRIED_KEYS:
        if key in previous:
            out[key] = previous[key]
    return out


def environment_id(log_text):
    """The environment the host most recently registered: the last one its log names."""
    found = ENV_ID.findall(log_text or "")
    return found[-1] if found else None


def retry_run_seconds(log_text, now=None):
    """How long the host has been failing to reach the server, from the trailing run of
    `Connection error, retrying` lines. Zero when the log ends on anything else, because a
    later line means the poll loop recovered. Times are `[HH:MM:SS]` with no date, so a run
    crossing midnight reads as a wrap, not as a negative gap."""
    stamps = []
    for line in (log_text or "").splitlines():
        found = RETRY_LINE.search(line)
        if found:
            stamps.append(tuple(int(part) for part in found.groups()))
        elif line.strip():
            stamps = []
    if len(stamps) < 2:
        return 0
    first, last = stamps[0], stamps[-1]
    start = timedelta(hours=first[0], minutes=first[1], seconds=first[2])
    end = timedelta(hours=last[0], minutes=last[1], seconds=last[2])
    if end < start:
        end += timedelta(days=1)
    return int((end - start).total_seconds())


def pointer_is_current(existing, wanted, path, now=None):
    """Whether the file already says what this run would write, and is young enough to be read.

    Freshness is the file's mtime, not a field, so an unchanged but expiring pointer still
    needs rewriting.
    """
    if existing != wanted:
        return False
    try:
        age = (now or datetime.now().timestamp()) - Path(path).stat().st_mtime
    except OSError:
        return False
    return age < POINTER_TTL_SECONDS / 2


def heal_plist(harness_bin, home, log_dir, claude_bin=None):
    """A launchd agent that runs `harness remote-control heal --once` on an interval."""
    path = [str(Path(claude_bin).parent)] if claude_bin else []
    path += [p for p in SYSTEM_PATH if p not in path]
    return {
        "Label": HEAL_LABEL,
        "ProgramArguments": [str(harness_bin), "remote-control", "heal", "--once"],
        "EnvironmentVariables": {"HOME": str(home), "PATH": ":".join(path)},
        "RunAtLoad": True,
        "StartInterval": HEAL_INTERVAL_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(Path(log_dir) / (HEAL_LABEL + ".log")),
        "StandardErrorPath": str(Path(log_dir) / (HEAL_LABEL + ".log")),
    }


def render_heal(harness_bin, home, log_dir, claude_bin=None):
    return plistlib.dumps(heal_plist(harness_bin, home, log_dir, claude_bin), sort_keys=True)
