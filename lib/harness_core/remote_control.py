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
