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
from urllib.request import Request, urlopen

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
    """Whether Claude Code's workspace-trust dialog was accepted for this exact folder.

    A trusted parent does not trust a child: Claude Code keys trust by the directory it was
    started in, so a host in an untrusted child exits at the prompt and launchd restarts that
    refusal every minute forever.
    """
    try:
        projects = json.loads(Path(claude_json).read_text(encoding="utf-8")).get("projects", {})
    except (OSError, ValueError):
        return False
    if not isinstance(projects, dict):
        return False
    entry = projects.get(str(Path(folder)))
    return isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True


def trust_hint(folder):
    """The one line that fixes an untrusted folder, named in `install` and in `status`."""
    return f"workspace trust not accepted; run `bin/harness trust {folder}` then `claude` there once"


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
            skipped.append((folder, trust_hint(folder)))
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
# The host prints its own error-budget age, so it is read rather than recomputed from the clock:
# `[01:46:00] Connection error, retrying in 2m (541s elapsed): fetch failed`.
RETRY_LINE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\][^\n]*Connection error, retrying")
RETRY_ELAPSED = re.compile(r"Connection error, retrying[^\n]*?\((\d+)s elapsed\)")
# `[bridge:work] Detected system sleep (312s gap), resetting error budget` — the host starts the
# budget again on wake, so the supervisor must too or it would stop a host that is not failing.
SLEEP_RESET = re.compile(r"Detected system sleep \((\d+)s gap\), resetting error budget")
RECONNECTED = re.compile(r"Reconnected after (\d+)s")
GAVE_UP = re.compile(r"Persistent errors for \d+ minutes?, giving up\.")
SHUTTING_DOWN = re.compile(r"Shutting down (\d+) active session\(s\)")
REMOVED_WORKTREE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*removed worktree (\S.*?)\s*$")
# `connGiveUpMs` is hardcoded at ten minutes and its path archives every session and deregisters
# the environment; nine minutes leaves a minute to stop the host while a restart can still resume.
GIVE_UP_SECONDS = 600
STOP_AT_SECONDS = 540


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


def unreachable_seconds(log_text):
    """How long the host has been failing to reach the server, from the trailing run of
    `Connection error, retrying` lines.

    The `(Ns elapsed)` figure is the host's own error budget and wins; a log without one falls
    back to the `[HH:MM:SS]` span, which reads a run crossing midnight as a wrap rather than as
    a negative gap. Any other line ends the run, so a reconnect and the system-sleep reset both
    put the budget back to zero — as they do inside the host.
    """
    elapsed, stamps = 0, []
    for line in (log_text or "").splitlines():
        if not line.strip():
            continue
        found = RETRY_LINE.search(line)
        if not found:
            elapsed, stamps = 0, []
            continue
        stamps.append(tuple(int(part) for part in found.groups()))
        counted = RETRY_ELAPSED.search(line)
        if counted:
            elapsed = int(counted.group(1))
    span = 0
    if len(stamps) >= 2:
        first, last = stamps[0], stamps[-1]
        start = timedelta(hours=first[0], minutes=first[1], seconds=first[2])
        end = timedelta(hours=last[0], minutes=last[1], seconds=last[2])
        if end < start:
            end += timedelta(days=1)
        span = int((end - start).total_seconds())
    return max(elapsed, span)


def removed_worktrees(log_text):
    """`(stamp, path)` for every session worktree the give-up cleanup deleted.

    A `kept worktree … · uncommitted changes` line is not one: that checkout still exists.
    """
    out = []
    for line in (log_text or "").splitlines():
        found = REMOVED_WORKTREE.search(line)
        if found:
            out.append((found.group(1), found.group(2)))
    return out


def gave_up(log_text):
    """Whether the log's last give-up is more recent than its last registration."""
    return bool(GAVE_UP.search(log_text or ""))


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


# --------------------------------------------------------------------------- supervisor state

STATE_NAME = "supervisor-state.json"


def read_state(path):
    """What the supervisor already did: `{"stopped": {label: pid}, "recreated": [key]}`.

    A missing or unreadable file is an empty state, so the worst a lost file costs is one
    repeated SIGTERM to a host that is failing anyway.
    """
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = None
    value = value if isinstance(value, dict) else {}
    stopped = value.get("stopped")
    recreated = value.get("recreated")
    return {"stopped": stopped if isinstance(stopped, dict) else {},
            "recreated": recreated if isinstance(recreated, list) else []}


def stop_is_due(elapsed, label, pid, state):
    """Whether this host should be stopped now, and has not been stopped already.

    The guard is the pid: launchd's relaunch is a new process, so the next outage stops the new
    host once and this one never twice.
    """
    return elapsed >= STOP_AT_SECONDS and state["stopped"].get(label) != pid


def record_stop(state, label, pid):
    state["stopped"][str(label)] = int(pid)
    return state


def worktree_key(stamp, path):
    return f"{stamp} {path}"


def unseen_worktrees(removed, state):
    """The `removed worktree` lines this run has not already acted on, oldest first."""
    seen = set(state["recreated"])
    return [(stamp, path) for stamp, path in removed if worktree_key(stamp, path) not in seen]


def record_worktree(state, stamp, path):
    state["recreated"].append(worktree_key(stamp, path))
    # One outage's worth of keys is all that matters; the log itself rotates far more slowly.
    state["recreated"] = state["recreated"][-256:]
    return state


def worktree_branch(path):
    """The branch name Claude Code gives a spawned session's worktree: `worktree-<dirname>`."""
    return "worktree-" + Path(path).name


def worktree_add_argv(root, path, branch, base, branch_exists):
    """`git worktree add`, attaching the session's branch when it survived the cleanup.

    The host deletes the checkout but not always the branch, and re-creating a branch that
    exists fails, so the two cases take different argument forms.
    """
    argv = ["git", "-C", str(root), "worktree", "add"]
    return argv + ([str(path), branch] if branch_exists else [str(path), "-b", branch, str(base)])


# --------------------------------------------------------------------------- lost sessions

# The cap is a budget, so the page has to be spent on the newest sessions: a lost session is
# recovered within minutes or not at all, and server order would let 50 stale rows hide it. An
# unknown query parameter is ignored rather than rejected, which is why `descending_by_update`
# checks the answer instead of trusting the request.
SESSIONS_URL = "https://api.anthropic.com/v1/code/sessions?limit=50&sort=updated_at&order=desc"
KEYCHAIN_SERVICE = "Claude Code-credentials"
API_HEADERS = {"anthropic-version": "2023-06-01", "anthropic-beta": "oauth-2025-04-20"}
# `--session-id` reattach hosts register the lost environment a second time, as a single-session
# environment that then takes new chats from the client, so the command is printed and never run.
REATTACH_WARNING = ("reattaching registers a second environment for this Mac and new chats may "
                    "land on it; stop the host as soon as the session has answered")


def oauth_token(keychain_payload):
    """The claude.ai access token out of the keychain item's JSON. Never logged or stored."""
    try:
        value = json.loads(keychain_payload or "")
    except ValueError:
        return None
    token = (value.get("claudeAiOauth") or {}).get("accessToken") if isinstance(value, dict) else None
    return token if isinstance(token, str) and token else None


def sessions_request(token):
    return Request(SESSIONS_URL, headers=dict(API_HEADERS, Authorization="Bearer " + token))


def descending_by_update(rows):
    """Whether a page is newest-first by `updated_at`, which is the order the cap assumes.

    A row with no timestamp sorts oldest, so a page that omits the field entirely is only
    descending when it holds fewer than two rows.
    """
    stamps = [str(row.get("updated_at") or "") for row in rows]
    return all(a >= b for a, b in zip(stamps, stamps[1:]))


def fetch_sessions(token, opener=None):
    """The account's recent Remote Control sessions, or None when the call fails.

    A page that did not come back newest-first is refused the same way, because under a cap the
    rows it dropped are then unknown rather than merely old.

    A failure here is a report line, never an exit code: the supervisor's other work does not
    depend on the network.
    """
    try:
        with (opener or urlopen)(sessions_request(token), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any network or parse failure reads the same to the caller
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return None
    rows = [row for row in data if isinstance(row, dict)]
    return rows if descending_by_update(rows) else None


def disconnected_sessions(rows, environment_ids):
    """Sessions still `active` whose bridge is `disconnected`, on an environment this Mac ran.

    An archived session is past recovery and one on another device's environment is not ours,
    so both are left out.
    """
    wanted = {str(e) for e in (environment_ids or [])}
    out = []
    for row in rows or []:
        if row.get("status") != "active" or row.get("connection_status") != "disconnected":
            continue
        if row.get("environment_id") not in wanted:
            continue
        out.append(row)
    return sorted(out, key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def reattach_command(session, permission_mode="default"):
    """The manual recovery line for one lost session. Printed for the user to run, not run."""
    return (f"claude remote-control --session-id {session.get('id')} "
            f"--permission-mode {permission_mode}")


def is_host_process(command):
    """Whether a `ps -o command=` line is the `claude` host itself, not its caffeinate wrapper.

    `keep_awake` makes the launchd job pid caffeinate's, and signalling that leaves the host
    running, so the signal has to find the child.
    """
    parts = (command or "").split()
    return bool(parts) and Path(parts[0]).name != "caffeinate" and "remote-control" in parts
