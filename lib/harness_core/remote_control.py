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
from urllib.error import HTTPError
from urllib.request import Request, urlopen

LABEL_PREFIX = "com.agent-harness.remote-control."
SPAWN_MODES = ("same-dir", "worktree", "session")
PERMISSION_MODES = ("acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")
DEFAULTS = {"folders": [], "spawn": "worktree", "permission_mode": "default", "keep_awake": False}
# A `folders` entry is a path, or an object naming a path plus what differs for that one host.
FOLDER_KEYS = ("path", "spawn", "env")
SYSTEM_PATH = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
# Every host's sessions inherit this. Without it, Claude Code 2.1.280 gives a session a host
# starts no upload route, so a file the agent sends with SendUserFile reaches the app as "not
# delivered" and cannot be opened there; with it set, the file is uploaded with the signed-in
# account. The variable is undocumented. A folder's own `env` wins, so "" turns it off there.
HOST_ENV = {"CLAUDE_CODE_BRIEF_UPLOAD": "1"}
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
    if not isinstance(out["folders"], list):
        raise ValueError("remote_control.folders must be a list of paths or folder objects")
    folders, options = [], {}
    for index, raw in enumerate(out["folders"]):
        folder, extra = folder_entry(raw, index)
        if folder in options and options[folder] != extra:
            raise ValueError(f"remote_control.folders lists {folder} twice with different options")
        if folder not in folders:
            folders.append(folder)
            options[folder] = extra
    out["folders"] = folders
    out["folder_options"] = options
    out["keep_awake"] = bool(out["keep_awake"])
    return out


def folder_entry(raw, index):
    """One `folders` entry as `(resolved path, {"spawn"?: mode, "env": {name: value}})`."""
    where = f"remote_control.folders[{index}]"
    if isinstance(raw, str):
        raw = {"path": raw}
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be a path or an object with a `path`")
    unknown = set(raw) - set(FOLDER_KEYS)
    if unknown:
        raise ValueError(f"unknown {where} key(s): " + ", ".join(sorted(unknown)))
    path = raw.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError(f"{where}.path must be a non-empty path")
    extra = {}
    if "spawn" in raw:
        if raw["spawn"] not in SPAWN_MODES:
            raise ValueError(f"{where}.spawn must be one of " + ", ".join(SPAWN_MODES))
        extra["spawn"] = raw["spawn"]
    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(
            isinstance(k, str) and k and isinstance(v, str) for k, v in env.items()):
        raise ValueError(f"{where}.env must be an object of string names to string values")
    extra["env"] = dict(env)
    return Path(path).expanduser().resolve(), extra


def folder_options(folder, opts):
    """The block's options with one folder's own `spawn` and `env` laid over them."""
    extra = (opts.get("folder_options") or {}).get(Path(folder), {})
    return {"spawn": extra.get("spawn", opts["spawn"]), "env": dict(extra.get("env") or {})}


def label(folder):
    """Stable launchd label: a readable slug plus a path hash, so two `api` folders never collide."""
    slug = re.sub(r"[^a-z0-9]+", "-", Path(folder).name.lower()).strip("-") or "folder"
    digest = hashlib.sha256(str(folder).encode("utf-8")).hexdigest()[:8]
    return f"{LABEL_PREFIX}{slug}-{digest}"


def command(folder, opts, claude_bin):
    # No `--no-create-session-in-dir`: Claude Code 2.1.280 reads the bridge pointer, and so
    # reuses the environment on a relaunch, only while createSessionInDir is on. The session it
    # pre-creates is reused across restarts for as long as the pointer stays fresh.
    argv = [str(claude_bin), "remote-control", "--name", Path(folder).name,
            "--spawn", folder_options(folder, opts)["spawn"],
            "--permission-mode", opts["permission_mode"]]
    if opts["keep_awake"]:
        # -i holds idle sleep, -s holds system sleep on AC power; neither survives a closed lid.
        argv = ["/usr/bin/caffeinate", "-is"] + argv
    return argv


def plist(folder, opts, claude_bin, home, log_dir):
    name = label(folder)
    path = [str(Path(claude_bin).parent)] + [p for p in SYSTEM_PATH if p != str(Path(claude_bin).parent)]
    env = dict({"HOME": str(home), "PATH": ":".join(path)}, **HOST_ENV)
    env.update(folder_options(folder, opts)["env"])
    return {
        "Label": name,
        "ProgramArguments": command(folder, opts, claude_bin),
        "WorkingDirectory": str(folder),
        "EnvironmentVariables": env,
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
                "projectThreadSessionIds", "projectThreadSessionIdsPersistedAt",
                # Added by 2.1.280.
                "parkedProjectThreadSessionIds", "parkedProjectThreadSessionIdsPersistedAt")
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

    A `pid` of None writes no `pid` and no `procStart`: the pointer `install` leaves for a host
    it is about to replace, which the next host reads as belonging to no live process.
    """
    previous = previous if isinstance(previous, dict) else {}
    if previous.get("environmentId") != environment_id:
        previous = {}
    out = {"sessionId": previous.get("sessionId") if isinstance(previous.get("sessionId"), str) else "",
           "environmentId": environment_id,
           "source": "standalone"}
    if pid is not None:
        out["pid"] = int(pid)
        out["procStart"] = str(proc_start)
    for key in CARRIED_KEYS:
        if key in previous:
            out[key] = previous[key]
    return out


def install_step(loaded, unchanged, pid, environment):
    """What `install` does with one folder's agent: `unchanged`, `adopt` or `load`.

    An unchanged, loaded agent is left alone: reloading it would cut off its sessions. A changed
    one whose host is running on a known environment is adopted — the pointer is written for
    that environment and the host is SIGKILLed before the reload, because a host that did not
    reuse an environment at start archives its sessions and deregisters on SIGTERM, and
    `launchctl bootout` sends exactly that. Anything else is a plain load.
    """
    if loaded and unchanged:
        return "unchanged"
    if pid is not None and environment:
        return "adopt"
    return "load"


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
    """What the supervisor already did:
    `{"stopped": {label: pid}, "recreated": [key], "reconnected": {session: epoch}}`.

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
    reconnected = value.get("reconnected")
    return {"stopped": stopped if isinstance(stopped, dict) else {},
            "recreated": recreated if isinstance(recreated, list) else [],
            "reconnected": reconnected if isinstance(reconnected, dict) else {}}


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


def reconnect_is_due(session_id, state, now):
    """Whether heal may re-queue this session now: at most once per `RECONNECT_EVERY_SECONDS`."""
    last = state.get("reconnected", {}).get(str(session_id))
    return not isinstance(last, (int, float)) or now - last >= RECONNECT_EVERY_SECONDS


def record_reconnect(state, session_id, now):
    """Stamp one attempt, and forget the ones old enough that they no longer hold anything back."""
    kept = {sid: when for sid, when in state.get("reconnected", {}).items()
            if isinstance(when, (int, float)) and now - when < RECONNECT_EVERY_SECONDS}
    kept[str(session_id)] = int(now)
    state["reconnected"] = kept
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
# recovered within minutes or not at all. The endpoint takes no sort parameter — `sort` and
# `order` were measured on 2026-09-22 to return the identical page — so the order is checked on
# arrival by `descending_by_event` and never requested.
PAGE_LIMIT = 50
SESSIONS_URL = "https://api.anthropic.com/v1/code/sessions?limit=%d" % PAGE_LIMIT
KEYCHAIN_SERVICE = "Claude Code-credentials"
API_HEADERS = {"anthropic-version": "2023-06-01", "anthropic-beta": "oauth-2025-04-20"}
# Heal re-queues these through `bridge/reconnect`. A `--session-id` reattach host registers the
# lost environment a second time, as a single-session environment that then takes new chats from
# the client, so that command is printed for the sessions heal cannot reconnect and never run.
REATTACH_WARNING = ("heal reconnects these automatically each minute; the command below is for a "
                    "session it cannot reconnect. Reattaching registers a second environment for "
                    "this Mac and new chats may land on it; stop the host as soon as the session "
                    "has answered")
RECONNECT_URL = "https://api.anthropic.com/v1/environments/%s/bridge/reconnect"
ENVIRONMENTS_BETA = "environments-2025-11-01"
RECONNECT_EVERY_SECONDS = 600


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


def reconnect_request(token, environment, session_id):
    """`POST bridge/reconnect`, which puts a disconnected session back in its environment's queue."""
    headers = dict(API_HEADERS, Authorization="Bearer " + token)
    headers["anthropic-beta"] = ",".join([API_HEADERS["anthropic-beta"], ENVIRONMENTS_BETA])
    headers["Content-Type"] = "application/json"
    body = json.dumps({"session_id": str(session_id)}).encode("utf-8")
    return Request(RECONNECT_URL % environment, data=body, headers=headers, method="POST")


def reconnect(token, environment, session_id, opener=None):
    """Re-queue one session; the HTTP status as text, or `failed: <reason>`. Never raises."""
    try:
        with (opener or urlopen)(reconnect_request(token, environment, session_id),
                                 timeout=20) as response:
            return str(getattr(response, "status", None) or response.getcode())
    except HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001 - a network failure is a log line, not a crash
        return "failed: " + (type(exc).__name__ + (f" {exc}" if str(exc) else ""))


def owned_environments(host_ids, pointers):
    """Every environment this Mac's hosts hold: those their logs name plus those their pointers name."""
    out = []
    for env in list(host_ids or []) + [p.get("environmentId") for p in pointers or []
                                       if isinstance(p, dict)]:
        if isinstance(env, str) and env and env not in out:
            out.append(env)
    return out


def session_rows(payload):
    """The rows of one sessions page, or None when the payload is not a page of session objects.

    An entry that is not an object refuses the whole page rather than being dropped: what is left
    would pass the order check trivially, and a page this malformed says nothing about the rest.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        return None
    return data


def event_time(row):
    """One row's `last_event_at` as a datetime, or None when it carries no readable one.

    The field is ISO-8601 with microseconds and a `Z`, which 3.9's parser does not take.
    """
    stamp = row.get("last_event_at")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
    except ValueError:
        return None


def descending_by_event(rows):
    """Whether a page is newest-first by `last_event_at`, the field the server orders by.

    Measured against a live account on 2026-09-22: a 50-row page is descending by `last_event_at`
    with no violations, while `updated_at` goes backwards seven times within it and `created_at`
    twenty-two, so `last_event_at` is the only field the cap can be read under.

    A page of more than one row holding a row with no readable timestamp is not descending: its
    order cannot be read, and under a cap an order that cannot be read is refused rather than
    assumed.
    """
    times = [event_time(row) for row in rows]
    if len(times) < 2:
        return True
    if any(when is None for when in times):
        return False
    return all(a >= b for a, b in zip(times, times[1:]))


class SessionPage(object):
    """One capped read of the sessions endpoint: what came back, or why nothing did.

    The three statuses are kept apart because a caller must never print one as another — a
    refused page is not an account with no lost sessions. `truncated` is whether the account
    holds more sessions than this page, which is as far as a capped read can honestly speak.
    """

    FAILED, REFUSED, OK = "failed", "refused", "ok"

    def __init__(self, status, rows=(), truncated=False):
        self.status = status
        self.rows = list(rows)
        self.truncated = truncated

    @property
    def ok(self):
        return self.status == self.OK

    def with_rows(self, rows):
        return SessionPage(self.status, rows, self.truncated)

    def scope(self):
        """What the count on this page may claim: the account, or only the newest `PAGE_LIMIT`."""
        return " in the newest %d" % PAGE_LIMIT if self.truncated else ""


def fetch_sessions(token, opener=None):
    """One page of the account's recent Remote Control sessions, newest first.

    A page that did not arrive newest-first is refused rather than read, because under a cap the
    rows such a page dropped are unknown rather than merely old.

    A failure here is a report line, never an exit code: the supervisor's other work does not
    depend on the network.
    """
    try:
        with (opener or urlopen)(sessions_request(token), timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any network or parse failure reads the same to the caller
        return SessionPage(SessionPage.FAILED)
    rows = session_rows(payload)
    if rows is None:
        return SessionPage(SessionPage.FAILED)
    if not descending_by_event(rows):
        return SessionPage(SessionPage.REFUSED)
    return SessionPage(SessionPage.OK, rows, bool(payload.get("next_cursor")))


def disconnected_sessions(rows, environment_ids):
    """Sessions still `active` whose bridge is `disconnected`, on an environment this Mac ran.

    An archived session is past recovery and one on another device's environment is not ours,
    so both are left out. The page's own order is kept: it has already been checked newest-first
    by `last_event_at`, and re-sorting on `updated_at` would scramble it.
    """
    wanted = {str(e) for e in (environment_ids or [])}
    out = []
    for row in rows or []:
        if row.get("status") != "active" or row.get("connection_status") != "disconnected":
            continue
        if row.get("environment_id") not in wanted:
            continue
        out.append(row)
    return out


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
