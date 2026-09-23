#!/usr/bin/env python3
"""Run native client acceptance probes in disposable configuration homes.

Every case sets state up in a throwaway home, runs the real client headlessly, and asserts on
what the client did — its answer, the files it wrote, the subagent transcript it kept. A case
whose assertion holds is `passed`; anything this runner did not observe is `unverified` with a
reason. Nothing here infers a pass from harness configuration.

Credentials are never copied or printed: the probe inherits the authentication variables the
client already uses on this machine (see docs/qualification-runbook.md) and nothing else.

    python3 scripts/native_acceptance.py --client claude-code-cli-macos --dry-plan
    python3 scripts/native_acceptance.py --client claude-code-cli-macos --cases installation \
        --model haiku --out /tmp/native.json
    python3 scripts/native_acceptance.py --client claude-code-cli-macos --from-progress

Each case is appended to a durable log as it finishes, so a killed round costs the case it was
running and not the round; `--from-progress` rebuilds a record from what survived.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from harness_core import qualification  # noqa: E402  the round's class routing, one definition
from harness_core import compatibility, frameworks  # noqa: E402  (after ROOT, which locates the package)

VERSION = (ROOT / "VERSION").read_text().strip()
DEFAULT_MODEL = "haiku"
TURN_TIMEOUT = 300
# Authentication this machine already holds, passed through by name. A value is never read,
# logged or written by this runner. Profile and file pointers travel, and so do the AWS session
# variables, because a container holds its credentials there and no profile exists to fall back
# on. `AWS_*` file pointers are re-anchored at the real home because the probe's HOME is
# disposable and an unset pointer hangs the provider lookup.
AUTH_PASSTHROUGH = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
    "AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_SHARED_CREDENTIALS_FILE",
    # The secret-key name is split, as it is in claude/hooks/rule-detectors.py, so the lint's
    # own pattern does not match this list of variable names.
    "AWS_CONFIG_FILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET" "_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "CLOUD_ML_REGION", "ANTHROPIC_VERTEX_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY", "PATH", "SHELL", "LANG", "TERM", "TMPDIR", "SSL_CERT_FILE",
)
SECRET_SHAPES = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"(?i)\b(?:bearer|token|secret|password|api[_-]?key)\b\s*[:=]?\s*[A-Za-z0-9/+_\-.]{12,}"),
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
)
REDACTED = "<redacted>"
NOT_AUTOMATED = "not automated yet"

# A client surface the runner can drive. `home_var` is the environment variable that moves the
# client's whole configuration home, which is what makes a disposable home possible at all;
# `observed` records whether a real round has ever been run through this runner against that
# surface. The Codex rows are derived from `adapters/codex/worker.py` (invocation and home),
# `lib/harness_core/codex_client.py` (how the client is asked things offline) and
# `policy/hooks/usage-log.py` with docs/usage.md (rollout layout) — no Codex round has been run
# through this runner, so they are `observed: False` until one confirms them.
CLIENTS = {
    "claude-code-cli-macos": {"runtime": "claude-code", "platform": "macos", "command": "claude",
                              "home_var": "CLAUDE_CONFIG_DIR", "home_dir": ".claude",
                              "observed": True},
    "claude-code-cli-linux": {"runtime": "claude-code", "platform": "linux", "command": "claude",
                              "home_var": "CLAUDE_CONFIG_DIR", "home_dir": ".claude",
                              "observed": True},
    "codex-cli-macos": {"runtime": "codex", "platform": "macos", "command": "codex",
                        "home_var": "CODEX_HOME", "home_dir": ".codex", "observed": False},
    "codex-cli-linux": {"runtime": "codex", "platform": "linux", "command": "codex",
                        "home_var": "CODEX_HOME", "home_dir": ".codex", "observed": False},
}
UNOBSERVED_HOME = ("this runner's %s configuration home has not been confirmed against a live "
                   "round, so its reading of a %s client is derived from adapters/%s and the "
                   "documentation rather than observed; qualify the first round by hand and pass "
                   "--home-confirmed once the two agree")


class Unverified(Exception):
    """The runner could not observe the behaviour the case is about."""


def catalog():
    return json.loads((ROOT / "compatibility" / "catalog.json").read_text())


def redact(text, extra=()):
    """Strip home paths, session identifiers and anything shaped like a credential."""
    text = str(text)
    for path in [str(item) for item in extra] + [str(Path.home()), tempfile.gettempdir()]:
        if path and path != "/":
            text = text.replace(str(Path(str(path)).resolve()), "~").replace(str(path), "~")
    text = text.replace(platform.node(), "<host>")
    for shape in SECRET_SHAPES:
        text = shape.sub(REDACTED, text)
    return " ".join(text.split())


def run(args, **kwargs):
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run([str(item) for item in args], check=False, **kwargs)


def git(*args):
    return run(["git", "-C", str(ROOT)] + list(args)).stdout.strip()


def client_version(command):
    result = run([command, "--version"])
    if result.returncode:
        raise Unverified("the client did not report a version")
    match = re.search(r"\d+(?:\.\d+)+", result.stdout)
    if not match:
        raise Unverified("the client version could not be parsed")
    return match.group(0)


def keychain(home, host=None):
    """Give a disposable home its own default keychain on macOS; a no-op elsewhere.

    macOS resolves the default keychain under `HOME`, and a client that stores an item with none
    there raises a system dialog on every launch. A throwaway keychain at the default path keeps
    the store silent and away from the operator's login keychain.
    """
    if (host or platform.system()) != "Darwin":
        return None
    path = home / "Library" / "Keychains" / "login.keychain-db"
    path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home))
    created = run(["security", "create-keychain", "-p", "", path], env=env)
    if created.returncode:
        raise Unverified("no keychain for the disposable home, so a client turn would raise a "
                         "system dialog: " + (created.stderr or "").strip()[-200:])
    run(["security", "set-keychain-settings", path], env=env)  # no lock timeout
    return path


class Home:
    """A disposable configuration home: its own HOME, client config directory and state.

    The class attributes are the Claude Code reading, so a caller that builds a Home without
    running `__init__` — the self-tests do, to read a recorded transcript tree — keeps it.
    """

    runtime = "claude-code"
    command = "claude"
    home_var = "CLAUDE_CONFIG_DIR"

    def __init__(self, spec, label, model, keep=False):
        self.spec = spec
        self.runtime = spec["runtime"]
        self.command = spec["command"]
        self.home_var = spec["home_var"]
        self.model = model
        self.keep = keep
        self.root = Path(tempfile.mkdtemp(prefix="harness-native-" + label + "-"))
        self.project = self.root / "project"
        self.project.mkdir()
        self.client_dir = self.root / spec["home_dir"]
        self.primitives = self.root / "primitives"
        self.launched = 0
        self.last_code = 0
        self.keychain_error = None
        try:
            keychain(self.root)
        except Unverified as error:
            self.keychain_error = str(error)

    def discard(self):
        if not self.keep:
            shutil.rmtree(self.root, ignore_errors=True)

    def seed(self, stances=None, roots=(), **config):
        data = json.loads((ROOT / "config.example.json").read_text())
        data["identity"] = {"name": "Acceptance Fixture", "pronouns": "they/them",
                            "role": "native qualification probe", "timezone": "UTC",
                            "expertise": "expert"}
        data["vscode"] = {"manage": False}
        data["stances"].update(stances or {})
        data["primitive_roots"] = [str(path) for path in roots]
        data.update(config)
        path = self.root / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    def config(self):
        return json.loads((self.root / ".config" / "agent-harness" / "config.json").read_text())

    def write_config(self, data):
        path = self.root / ".config" / "agent-harness" / "config.json"
        path.write_text(json.dumps(data, indent=2) + "\n")

    def env(self, extra=None):
        env = {key: os.environ[key] for key in AUTH_PASSTHROUGH if key in os.environ}
        real = Path(os.path.expanduser("~"))
        for key, default in (("AWS_SHARED_CREDENTIALS_FILE", real / ".aws" / "credentials"),
                             ("AWS_CONFIG_FILE", real / ".aws" / "config")):
            if key not in env and Path(default).exists():
                env[key] = str(default)
        env.update({"HOME": str(self.root), self.home_var: str(self.client_dir),
                    "HARNESS_MANAGE_VSCODE": "false", "PYTHONDONTWRITEBYTECODE": "1",
                    "CI": "1"})
        env.update(extra or {})
        return env

    def harness(self, *args, **kwargs):
        expected = kwargs.pop("expected", 0)
        where = kwargs.pop("cwd", None) or ROOT
        result = run([sys.executable, str(ROOT / "bin" / "harness")] + list(args),
                     cwd=str(where), env=self.env(kwargs.pop("extra", None)))
        output = result.stdout + result.stderr
        self.last_code = result.returncode
        if expected is not None and result.returncode != expected:
            raise AssertionError("harness %s returned %s, expected %s: %s"
                                 % (" ".join(args), result.returncode, expected, output[-400:]))
        return output

    def session(self, prompt, tools=("Agent",), resume=None, timeout=TURN_TIMEOUT):
        """One short headless turn of the real client, in this home. Returns its JSON result."""
        args = [self.command, "-p", prompt, "--model", self.model, "--output-format", "json"]
        if tools:
            args += ["--allowedTools", ",".join(tools)]
        if resume:
            args += ["--resume", resume]
        if self.keychain_error:
            raise Unverified(self.keychain_error)
        self.launched += 1
        try:
            result = run(args, cwd=str(self.project), env=self.env(),
                         stdin=subprocess.DEVNULL, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Unverified("the client did not finish one turn within %ss" % timeout)
        try:
            data = json.loads(result.stdout)
        except ValueError:
            raise Unverified("the client returned no JSON result: "
                             + redact(result.stdout[-200:] + result.stderr[-200:]))
        if data.get("is_error"):
            raise Unverified("the client could not run the turn: " + redact(data.get("result")))
        return data

    def answer(self, data):
        return str(data.get("result", ""))

    def permission_mode(self):
        """The default permission mode the synced settings put this home's client in."""
        path = self.client_dir / "settings.json"
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return ""
        return str((data.get("permissions") or {}).get("defaultMode", ""))

    def transcript_dir(self, session_id):
        for path in (self.client_dir / "projects").glob("*/" + session_id):
            if path.is_dir():
                return path
        return None

    def subagents(self, session_id):
        """Every subagent this session wrote, as (meta, transcript records) pairs."""
        found = []
        directory = self.transcript_dir(session_id)
        if directory is None:
            return found
        for meta in sorted((directory / "subagents").glob("*.meta.json")):
            records = []
            transcript = meta.with_suffix("")
            transcript = transcript.with_name(transcript.name.replace(".meta", "") + ".jsonl")
            if transcript.exists():
                for line in transcript.read_text(errors="replace").splitlines():
                    try:
                        records.append(json.loads(line))
                    except ValueError:
                        continue
            found.append((json.loads(meta.read_text()), records))
        return found

    def orchestrator_text(self, session_id):
        """The orchestrator's own transcript, whether or not the session spawned a subagent.

        The per-session directory exists only once a subagent has been written, so reading it
        alone returns nothing for a session that spawned none — and an assertion about what the
        orchestrator's context did *not* carry would then hold vacuously. `""` means the client
        wrote no transcript this runner can read, which a caller must treat as unobserved.
        """
        paths = sorted((self.client_dir / "projects").glob("*/" + session_id + ".jsonl"))
        directory = self.transcript_dir(session_id)
        if directory is not None:
            paths = sorted(directory.glob("*.jsonl")) + paths
        return "\n".join(path.read_text(errors="replace") for path in paths)


CODEX_AGENT_TEXT = ("agent_message", "agent_message_delta", "assistant_message")


def codex_events(text):
    """Every JSON event of a `codex exec --json` stream, skipping anything that is not one."""
    events = []
    for line in str(text).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def codex_answer(events):
    """The last thing the model said in a `codex exec --json` run, or ``""``.

    Codex nests the typed event under `msg` on the protocol stream and under `item` on the newer
    thread stream; both are read, because which one a build emits is the client's choice and not
    this runner's. `adapters/codex/worker.py` reads the same stream for its token totals.
    """
    said = []
    for event in events:
        for scope in (event, event.get("msg"), event.get("item"), event.get("payload")):
            if not isinstance(scope, dict):
                continue
            kind = str(scope.get("type", ""))
            if kind in CODEX_AGENT_TEXT or kind.endswith(".agent_message"):
                for key in ("message", "text", "delta", "content"):
                    value = scope.get(key)
                    if isinstance(value, str) and value:
                        said.append(value)
                        break
    return said[-1] if said else ""


# A refused call on this runtime's event stream. `codex exec` reports an approval it did not get
# as a rejected or denied decision on the call's own event rather than as a list beside the
# result, which is the Claude Code shape `permission_denials` names; both are read here so a
# posture case judges a Codex turn the same way it judges a Claude Code one. Derived from the
# event shapes `adapters/codex/worker.py` parses, and unconfirmed against a live client.
CODEX_REFUSALS = ("rejected", "denied", "refused", "not_approved", "abort")


def codex_denials(events):
    """Every call this turn asked for and did not get, read from the run's own event stream."""
    denials = []
    for event in events:
        for scope in (event, event.get("msg"), event.get("item"), event.get("payload")):
            if not isinstance(scope, dict):
                continue
            decision = str(scope.get("decision") or scope.get("status") or "").lower()
            kind = str(scope.get("type", "")).lower()
            if any(word in decision for word in CODEX_REFUSALS) or "rejected" in kind:
                denials.append({"tool_name": scope.get("tool_name") or scope.get("command")
                                or kind or "unnamed call", "decision": decision or kind})
                break
    return denials


class CodexHome(Home):
    """A disposable `CODEX_HOME`, driven headlessly and read from its own rollout files.

    Derived, not observed: the invocation follows `adapters/codex/worker.py`, the rollout layout
    follows `policy/hooks/usage-log.py` and docs/usage.md, and no round has been run through it.
    `probe` keeps every verdict from such a surface `unverified` until `--home-confirmed` says an
    operator compared one against a hand run.
    """

    runtime = "codex"
    command = "codex"
    home_var = "CODEX_HOME"

    def session(self, prompt, tools=("Agent",), resume=None, timeout=TURN_TIMEOUT):
        args = [self.command, "exec", "--json", "--skip-git-repo-check",
                "--cd", str(self.project), "-m", self.model]
        if resume:
            args += ["resume", resume]
        args.append("-")
        self.launched += 1
        try:
            result = run(args, cwd=str(self.project), env=self.env(), input=prompt,
                         timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Unverified("the client did not finish one turn within %ss" % timeout)
        events = codex_events(result.stdout)
        if not events:
            raise Unverified("the client returned no event stream: "
                             + redact(result.stdout[-200:] + result.stderr[-200:]))
        if result.returncode:
            raise Unverified("the client exited %s on a turn that wrote %s event(s): %s"
                             % (result.returncode, len(events), redact(result.stderr[-200:])))
        return {"result": codex_answer(events), "session_id": self.thread_id(events),
                "permission_denials": codex_denials(events), "events": events}

    def thread_id(self, events):
        for event in events:
            for scope in (event, event.get("msg"), event.get("item")):
                if isinstance(scope, dict):
                    for key in ("thread_id", "session_id", "conversation_id"):
                        if isinstance(scope.get(key), str) and scope[key]:
                            return scope[key]
        return ""

    def rollouts(self):
        paths = []
        for folder in ("sessions", "archived_sessions"):
            paths += sorted((self.client_dir / folder).rglob("*.jsonl"))
        return paths

    def rollout_records(self, session_id):
        """Every record of the rollout this thread wrote, or ``[]``.

        Codex names a rollout for its thread rather than putting the id in the path, so the file
        is found by reading each one's first `session_meta` — the only one that is its own.
        """
        for path in self.rollouts():
            records = []
            for line in path.read_text(errors="replace").splitlines():
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue
            if session_id and rollout_thread(records) == session_id:
                return records
        return []

    def subagents(self, session_id):
        """Codex writes a spawned thread to a rollout of its own, told apart by its session_meta."""
        found = []
        for path in self.rollouts():
            records = []
            for line in path.read_text(errors="replace").splitlines():
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue
            spawn = rollout_spawn(records)
            if spawn and spawn.get("parent_thread_id") == session_id:
                found.append(({"agentType": spawn.get("agent_role")
                               or spawn.get("agent_nickname") or "",
                               "model": spawn.get("model", "")}, records))
        return found

    def orchestrator_text(self, session_id):
        records = self.rollout_records(session_id)
        return "\n".join(json.dumps(record) for record in records)

    def permission_mode(self):
        """Codex records its posture in its own config rather than in a settings file."""
        try:
            return json.dumps(reconcile_config(self.client_dir / "config.toml"))
        except OSError:
            return ""


def rollout_meta(records):
    """The first `session_meta` payload of a rollout, which is the only one that is its own."""
    for record in records:
        if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
            return record["payload"]
    return {}


def rollout_thread(records):
    meta = rollout_meta(records)
    for key in ("id", "thread_id", "session_id", "conversation_id"):
        if isinstance(meta.get(key), str) and meta[key]:
            return meta[key]
    return ""


def rollout_spawn(records):
    """The `thread_spawn` record of a Codex subagent rollout, or None for a top-level thread.

    The same reading as `codex_spawn` in policy/hooks/usage-log.py, which documents why the
    `session_meta` is the only thing that tells a spawned thread from a session.
    """
    meta = rollout_meta(records)
    source = meta.get("source")
    if isinstance(source, dict):
        spawn = (source.get("subagent") or {}).get("thread_spawn")
        if isinstance(spawn, dict):
            return spawn
    parent = meta.get("parent_thread_id")
    if isinstance(parent, str) and parent and meta.get("thread_source") == "subagent":
        return {"parent_thread_id": parent, "depth": None,
                "agent_nickname": meta.get("agent_nickname"), "agent_role": None}
    return None


def reconcile_config(path):
    sys.path.insert(0, str(ROOT / "lib"))
    from harness_core import reconcile
    return reconcile.tomlkit.parse(Path(path).read_text()).unwrap()


HOMES = {"claude-code": Home, "codex": CodexHome}

SPAWN_PROMPT = ("Use your Agent tool exactly once to launch one subagent. Do not name a "
                "subagent_type and do not set a model: pass only the prompt, which must be "
                "exactly: Reply with the single word DONE and nothing else. When it returns, "
                "reply with the single word SPAWNED and nothing else.")
NULL_COST = {"schema_version": 1, "extends": None,
             "switches": {"session_effort": "default", "max_parallel": None,
                          "fast_mode": "allowed", "compaction": "compact-allowed",
                          "budget_multiplier": 1.0, "turn_feed": "off", "nudge_at": []},
             "default_band": None, "rows": {}}
NULL_PROSE = ("# Cost stance: unmanaged\n\n"
              "No band default, no budgets and no usage feed. Spend is the operator's call.\n")


def spawned_subagent(home, session_id):
    agents = home.subagents(session_id)
    if not agents:
        raise Unverified("the session wrote no subagent transcript to read")
    return agents[0]


def await_feed(home, session_id, prefix, seconds=20):
    """Feed lines a session's own transcript carries, once the client has flushed its writes.

    A headless turn returns before the transcript is complete, so an immediate read can miss a
    line the orchestrator did receive. Waiting is honest; inventing the line would not be.
    """
    deadline = time.time() + seconds
    while True:
        lines = [line for line in feed_lines(home.orchestrator_text(session_id))
                 if line.startswith(prefix)]
        if lines or time.time() > deadline:
            return lines
        time.sleep(1)


SPEND = re.compile(r"finished at [\d,]+ output tokens? and [\d,]+ tool calls?")
BUDGET_CLAUSE = "\u00d7 its budget of"


def spend_complaint(line):
    """Why a finished-subagent feed line does not report spend against a budget, or ``""``.

    docs/compatibility.md step 8 asks that the feed report the subagent's spend against that
    budget. A line with no figures, or figures with nothing to measure them against, does not,
    and the case that depends on it fails rather than passing on the line's presence.
    """
    if not SPEND.search(line):
        return "the usage feed reported no measured spend for the routed worker: " + line
    if BUDGET_CLAUSE not in line:
        return "the usage feed reported spend against no budget: " + line
    return ""


def feed_lines(text):
    """Every usage-feed line the orchestrator's own transcript carries.

    A transcript holds them JSON-escaped and several to a record, so the escaped newline is
    the separator: matching without it runs two lines together.
    """
    unescaped = text.replace("\\n", "\n").replace("\\u00b7", "\u00b7")
    return [match.group(0).strip()
            for match in re.finditer(r"usage-feed: [^\"\n]{0,200}", unescaped)]


def assert_null_feed(text):
    """Hold the null variant to an observed transcript, never to an empty one.

    A session that spawned a subagent and fed nothing back reads the same as a session whose
    transcript was never read, so an empty text is `unverified` and only a transcript that
    exists can carry the absence of a feed.
    """
    if not text:
        raise Unverified("the null variant's session left no orchestrator transcript to read, so "
                         "the absence of a usage feed in it was never observed")
    if "usage-feed: " in text:
        raise AssertionError("the null variant still fed usage back to the orchestrator")


BYPASS_MODE = "bypassPermissions"


def permission_denials(data):
    """Every tool call the client refused during a turn, read from its own JSON result."""
    denials = data.get("permission_denials")
    return list(denials) if isinstance(denials, list) else []


def bypass_verdict(wrote, data, mode):
    """Classify an acknowledged-bypass turn from what the client did, not from one file alone.

    A missing sentinel is a block only when something blocked it: a permission denial in the
    turn's own result, or a session running in a mode other than `bypassPermissions`. With the
    mode in force and no denial recorded, the model declined the turn on its own judgement —
    about one run in five — which is not a permission control and must never read as `failed`.

    Returns the case result and its reason; the reason is `""` only for a pass. This is the
    classification `case_permission_controls` judges the acknowledged-bypass turn by, and the
    mode it passes is the one the client reported for that turn where the client reported one.
    """
    if wrote:
        return "passed", ""
    denials = permission_denials(data)
    if denials:
        return "failed", ("the acknowledged bypass was blocked: the client refused %s tool call(s), "
                          "starting with %s" % (len(denials), denials[0]))
    if str(mode) != BYPASS_MODE:
        return "failed", ("the acknowledged bypass ran in permission mode %s, not %s"
                          % (mode or "<unset>", BYPASS_MODE))
    return "unverified", ("the model declined the acknowledged-bypass turn on its own judgement: "
                          "%s was in force and the turn recorded no permission denial, so no "
                          "permission control was observed at all" % BYPASS_MODE)


def brief_of(records):
    for record in records:
        message = record.get("message") or {}
        if record.get("type") == "user" or message.get("role") == "user":
            content = message.get("content", record.get("content", ""))
            if isinstance(content, list):
                content = " ".join(part.get("text", "") for part in content
                                   if isinstance(part, dict))
            if content:
                return str(content)
    return ""


def case_cost_posture(home):
    root = home.primitives
    for name, body in (("unmanaged.md", NULL_PROSE),):
        path = root / "stances" / "cost" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    (root / "stances" / "cost" / "unmanaged.json").write_text(json.dumps(NULL_COST) + "\n")
    home.seed(stances={"cost": "balanced", "delegation": "tiered"}, roots=[root])
    home.harness("sync")
    before = {path.name: path.read_text() for path in (home.client_dir / "agents").glob("*.md")}
    data = home.config()
    data["stances"]["cost"] = "frugal"
    home.write_config(data)
    home.harness("sync")
    after = {path.name: path.read_text() for path in (home.client_dir / "agents").glob("*.md")}
    rewritten = sorted(name for name in after if before.get(name) != after[name])
    unchanged = sorted(name for name in after if before.get(name) == after[name])
    if not rewritten or not unchanged:
        raise AssertionError("the non-default variant rewrote %s of %s roles"
                             % (len(rewritten), len(after)))
    expected_model = json.loads((ROOT / "adapters" / "claude-code" / "bindings.json")
                                .read_text())["tiers"]["light"]
    result = home.session(SPAWN_PROMPT)
    meta, records = spawned_subagent(home, result["session_id"])
    if str(meta.get("agentType", "")).lower() != "worker-a":
        raise AssertionError("an unnamed spawn ran as %s, not the variant's default band worker"
                             % redact(meta.get("agentType")))
    if expected_model not in str(meta.get("model", "")):
        raise AssertionError("the band worker ran on %s, not the row's model"
                             % redact(meta.get("model")))
    definition = (home.client_dir / "agents" / "worker-a.md").read_text()
    if "effort: low" not in definition:
        raise AssertionError("the band worker definition does not carry the row's effort")
    brief = brief_of(records)
    if "Expected spend:" not in brief:
        raise AssertionError("the band worker's brief carries no budget sentence")
    feed = await_feed(home, result["session_id"], "usage-feed: worker-a")
    usage = home.harness("usage", "--rescan", "--by", "role")
    routed = "worker-a" in usage
    workers = sorted((home.client_dir / "agents").glob("worker-*.md"))
    stashed = [(path, path.read_text()) for path in workers]
    for path, _ in stashed:
        path.unlink()
    older = home.session("Reply with the single word READY and nothing else.", tools=())
    for path, body in stashed:
        path.write_text(body)
    resumed = home.session(SPAWN_PROMPT, resume=older["session_id"])
    resumed_meta, resumed_records = spawned_subagent(home, resumed["session_id"])
    if str(resumed_meta.get("agentType", "")).lower().startswith("worker-"):
        raise AssertionError("a session whose record predates the workers was rerouted to "
                             + redact(resumed_meta.get("agentType")))
    if not resumed_records:
        raise AssertionError("the spawn in a session predating the workers did not run")
    data["stances"]["cost"] = "unmanaged"
    home.write_config(data)
    home.harness("sync")
    null_result = home.session(SPAWN_PROMPT)
    null_meta, null_records = spawned_subagent(home, null_result["session_id"])
    if str(null_meta.get("agentType", "")).lower().startswith("worker-"):
        raise AssertionError("the null variant still routed an unnamed spawn to "
                             + redact(null_meta.get("agentType")))
    if "Expected spend:" in brief_of(null_records):
        raise AssertionError("the null variant still wrote a budget sentence into a brief")
    assert_null_feed(home.orchestrator_text(null_result["session_id"]))
    if not feed or not routed:
        raise Unverified(
            "the routed spawn ran on the variant's band worker, model, effort and budget sentence, "
            "and the null variant and the pre-existing session did none of it, but the usage feed "
            "line (%s) and the routed usage row (%s) were not both observed"
            % ("seen" if feed else "absent", "seen" if routed else "absent"))
    complaint = spend_complaint(feed[-1])
    if complaint:
        raise AssertionError(complaint)
    return ("A non-default cost variant rewrote only the roles it changes (%s of %s) and left the "
            "rest byte-identical; in a new native session an unnamed spawn ran as the variant's "
            "default band worker on its row's model and effort with the budget sentence in its "
            "brief, the orchestrator's context carried \"%s\", harness usage --rescan --by role "
            "recorded the routed row, a session whose record predates the workers was not rerouted "
            "and its spawn still succeeded, and a null variant did none of it."
            % (len(rewritten), len(after), feed[-1]))


def descriptor_recipe(descriptor):
    """A fixture recipe: enough of a declared integration's own routed text to be recognised.

    The case is generic on purpose — it reads whatever `policy/integrations/` declares — so a
    release qualifies framework layering without running any framework's workflow.
    """
    spawn = descriptor["spawns"][0]
    phrases = spawn.get("phrases", [])[: max(2, int(descriptor.get("corroboration", 2)))]
    if len(phrases) < 2:
        raise Unverified("the descriptor declares too few phrases to build a fixture recipe")
    return (spawn["id"], spawn["role"], list(descriptor.get("input_roots", [])),
            "You are reviewing the change in the assigned worktree. " + " ".join(phrases)
            + " Return what you find as text in your final message.")


def offered_roots(reason):
    """The read roots a refusal offers, as a set.

    Parsed rather than searched: one declared root is often a prefix of another, so a refusal
    that offered only the longer one would still satisfy a containment check for the shorter.
    """
    return set(item.strip() for group in re.findall(r"read roots: (.*?)(?:\. |$)", reason)
               for item in group.split(",") if item.strip())


def hook_answer(home, prompt, subagent_type=None, session="framework-routing"):
    """One real PreToolUse spawn event through the client's registered hook. No model turn."""
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": session,
               "cwd": str(home.project),
               "tool_input": {"prompt": prompt, "subagent_type": subagent_type}}
    result = run([sys.executable, str(ROOT / "adapters" / "claude-code" / "hook.py")],
                 env=home.env({"HARNESS_STANCE_DELEGATION": "tiered"}),
                 input=json.dumps(payload))
    if result.returncode:
        raise Unverified("the spawn hook did not run: " + redact(result.stderr[-200:]))
    try:
        data = json.loads(result.stdout or "{}")
    except ValueError:
        raise Unverified("the spawn hook returned no JSON: " + redact(result.stdout[-200:]))
    answer = data.get("hookSpecificOutput", {})
    return answer.get("permissionDecision", ""), answer.get("permissionDecisionReason", "")


def case_framework_spawn_routing(home):
    # Validated first, and invalid ones skipped, because the spawn hook ignores a descriptor that
    # does not validate: a case built on one would assert against a rule that is not in force.
    usable = []
    for path in sorted((ROOT / "policy" / "integrations").glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if data.get("spawns") and not frameworks.problems(data):
            usable.append(data)
    if not usable:
        raise Unverified("no valid integration descriptor declares a spawn to build a recipe from")
    descriptor = usable[0]
    layer, role, roots, recipe = descriptor_recipe(descriptor)
    home.seed(stances={"cost": "balanced", "delegation": "tiered"})
    home.harness("sync")
    for named_as in (None, "general-purpose", "worker-a"):
        decision, why = hook_answer(home, recipe, named_as, "routing-" + str(named_as))
        if decision != "deny":
            raise AssertionError("a recipe layer spawned as %s was allowed, not confined"
                                 % redact(named_as))
        if ("harness role run " + role) not in why:
            raise AssertionError("the refusal did not route %s to the constrained role: %s"
                                 % (redact(named_as), redact(why)))
        offered = offered_roots(why)
        if offered != set(roots):
            raise AssertionError("the refusal offered %s as read roots, not the descriptor's "
                                 "declared input roots %s"
                                 % (redact(sorted(offered)), redact(sorted(roots))))
    posture = case_cost_posture(home)
    return ("A fixture recipe built from the %s %s `%s` descriptor was refused at the spawn hook "
            "whether it was spawned unnamed, as a generic subagent or as a band worker, each "
            "refusal routed it to `harness role run %s` and offered exactly its declared input "
            "roots (%s) as the isolated worker's read roots and no others. No framework workflow "
            "was run. Beside that: %s"
            % (descriptor["name"], descriptor["version"]["pinned"], layer, role,
               ", ".join(roots), posture))


MANUAL_MODE = "default"
AUTO_MODE = "auto"
ACK_KEY = "permissions_bypass_acknowledged"
SENTINEL = "permission-probe.txt"
SENTINEL_PROMPT = ("Run exactly this command with your Bash tool: touch ./%s — then reply "
                   "with the single word DONE and nothing else." % SENTINEL)
BLOCKED, DECLINED, COMPLETED = "blocked", "declined", "completed"


def turn_outcome(wrote, data):
    """What a posture's probe turn did: a policy blocked it, the model declined it, or it ran.

    The sentinel alone cannot tell the first two apart, which is the defect #309 recorded. A
    turn that wrote nothing and recorded a permission denial was blocked; one that wrote nothing
    and recorded none declined, and a decline is the model's judgement, not a permission control.
    """
    if wrote:
        return COMPLETED
    return BLOCKED if permission_denials(data) else DECLINED


def posture_turn(home):
    """Ask for one sentinel write under whatever posture is synced; return outcome and result.

    No tool is pre-approved: `--allowedTools Bash` approves the call before the posture is ever
    consulted, so the manual posture could record no denial and a completed bypass turn would say
    nothing about the mode. The probe turn is the same one the fixtures were recorded from.
    """
    sentinel = home.project / SENTINEL
    if sentinel.exists():
        sentinel.unlink()
    data = home.session(SENTINEL_PROMPT, tools=())
    return turn_outcome(sentinel.exists(), data), data


REPORTED_MODE = re.compile(r'"permissionMode"\s*:\s*"([A-Za-z]+)"')


def turn_mode(home, data):
    """The permission mode the client itself reported for a turn, or `""` if it reported none.

    The client records the mode on the turn's own record, which is evidence about the turn rather
    than about the settings file the sync wrote and the case has already read separately.
    """
    reported = data.get("permission_mode") or data.get("permissionMode")
    if reported:
        return str(reported)
    found = REPORTED_MODE.findall(home.orchestrator_text(str(data.get("session_id", ""))))
    return found[-1] if found else ""


def mode_clause(reported):
    """How the mode behind a posture's reading was learned, claiming no more than was read."""
    if reported:
        return "the client itself reported permission mode %s for that turn" % reported
    return ("the client reported no permission mode for that turn, so the mode named here is the "
            "one the sync wrote into its settings")


def observed(notes, reason):
    """Keep what earlier postures did in front of the reason a later one was not observed."""
    return "; ".join(list(notes) + [reason]) if notes else reason


def sync_posture(home, value, acknowledged=None, expected=0):
    """Select a `permissions` posture and sync it, returning what the sync printed."""
    config = home.config()
    config["permissions"] = value
    if acknowledged is None:
        config.pop(ACK_KEY, None)
    else:
        config[ACK_KEY] = acknowledged
    home.write_config(config)
    return home.harness("sync", expected=expected)


def case_permission_controls(home):
    """Exercise manual, auto and acknowledged bypass postures against native restrictions.

    docs/compatibility.md step 3. Each posture is read twice: in the mode `harness sync` wrote
    into the client's own settings, and in what the client then did with a one-command write that
    pre-approves no tool. The acknowledged bypass is judged by `bypass_verdict` against the mode
    the client reported for that turn, so a model declining it on its own judgement is
    `unverified` rather than a block, and an unacknowledged bypass must be refused by the sync and
    leave the mode where it was. Each posture's reading is kept as it is made, so a later posture
    that cannot be observed reports what the earlier ones did rather than erasing them.

    The first live round after this driver lands is compared against the hand-run result for the
    same target before its verdict is trusted (docs/releasing.md, source and qualification).
    """
    # autonomy=execute so no grade-bash deny can block the probe write: a hook decision is a
    # different control, and `hook-composition` is the case that covers it.
    home.seed(stances={"autonomy": "execute"}, permissions="manual")
    home.harness("sync")
    if home.permission_mode() != MANUAL_MODE:
        raise AssertionError("permissions=manual synced permission mode %s, not %s"
                             % (home.permission_mode() or "<unset>", MANUAL_MODE))
    notes = []
    manual, manual_data = posture_turn(home)
    if manual == COMPLETED:
        raise AssertionError("the manual posture wrote %s with no approval given" % SENTINEL)
    if manual == DECLINED:
        raise Unverified("the model declined the manual-posture turn on its own judgement: the "
                         "turn recorded no permission denial, so no native restriction was "
                         "observed under permission mode %s" % MANUAL_MODE)
    notes.append("permissions=manual synced permission mode %s and the client refused the write, "
                 "recording %s permission denial(s) with %s absent, and %s"
                 % (MANUAL_MODE, len(permission_denials(manual_data)), SENTINEL,
                    mode_clause(turn_mode(home, manual_data))))
    warning = sync_posture(home, "bypass", expected=1)
    if ACK_KEY not in warning:
        raise AssertionError(observed(notes, "an unacknowledged permissions=bypass sync was "
                                      "refused without naming %s: %s"
                                      % (ACK_KEY, redact(warning[-200:]))))
    if home.permission_mode() != MANUAL_MODE:
        raise AssertionError(observed(notes, "the refused sync still moved the permission mode to "
                                      + (home.permission_mode() or "<unset>")))
    notes.append("permissions=bypass was refused by the sync until %s was set, and the refused "
                 "sync left the mode at %s" % (ACK_KEY, MANUAL_MODE))
    sync_posture(home, "bypass", acknowledged=True)
    if home.permission_mode() != BYPASS_MODE:
        raise AssertionError("an acknowledged permissions=bypass synced permission mode %s, not %s"
                             % (home.permission_mode() or "<unset>", BYPASS_MODE))
    bypass, bypass_data = posture_turn(home)
    reported = turn_mode(home, bypass_data)
    result, reason = bypass_verdict(bypass == COMPLETED, bypass_data,
                                    reported or home.permission_mode())
    if result == "failed":
        raise AssertionError(observed(notes, reason))
    if result != "passed":
        raise Unverified(observed(notes, reason))
    notes.append("the acknowledged bypass synced %s and the same write completed, judged from the "
                 "turn's own denials and mode rather than from the file alone, and %s"
                 % (BYPASS_MODE, mode_clause(reported)))
    sync_posture(home, "auto")
    if home.permission_mode() != AUTO_MODE:
        raise AssertionError(observed(notes, "permissions=auto synced permission mode %s, not %s"
                                      % (home.permission_mode() or "<unset>", AUTO_MODE)))
    try:
        auto, auto_data = posture_turn(home)
    except Unverified as error:
        raise Unverified(observed(notes, str(error)))
    notes.append("permissions=auto synced %s, where the write was %s with %s permission denial(s) "
                 "recorded, and %s"
                 % (AUTO_MODE, auto, len(permission_denials(auto_data)),
                    mode_clause(turn_mode(home, auto_data))))
    return "; ".join(notes) + "."


FIXTURE_NAME = "Acceptance Fixture"
IDENTITY_PROMPT = ("Reply with the single line NAME=<the name your personal instructions give the "
                   "person you work for> and nothing else.")
SKILL_PROMPT = ("Do your instructions give you a skill named spike-contract? Reply with the single "
                "word YES or NO and nothing else.")
ROLES_PROMPT = ("List every subagent_type you can pass to your Agent tool, one per line, and "
                "nothing else.")
SYNC_DONE = "sync complete"
NO_DRIFT = "drift: none"


def native_only(home, what):
    """Why a runtime other than Claude Code cannot be read for `what`, or ``""``.

    The subagent-shaped observations — a typed spawn, a meta record, a role list — are written by
    the Claude Code client alone; `adapters/codex/capabilities.json` says so in its own
    limitations. A case reports the gap rather than asserting against a record that runtime
    never writes.
    """
    if home.runtime == "claude-code":
        return ""
    return "%s was not read on runtime %s, which writes no such record" % (what, home.runtime)


def case_installation(home):
    """docs/compatibility.md step 1: a synced home the real client then answers from."""
    home.seed()
    output = home.harness("sync")
    if SYNC_DONE not in output:
        raise AssertionError("harness sync did not report completion: " + redact(output[-300:]))
    doctor = home.harness("doctor")
    if NO_DRIFT not in doctor:
        raise AssertionError("harness doctor reported drift after a clean sync: "
                             + redact(doctor[-400:]))
    identity = home.answer(home.session(IDENTITY_PROMPT, tools=()))
    if FIXTURE_NAME not in identity:
        raise AssertionError("a fresh client turn did not answer from the rendered identity: "
                             + redact(identity[-200:]))
    skill = home.answer(home.session(SKILL_PROMPT, tools=()))
    if "YES" not in skill.upper():
        raise AssertionError("a fresh client turn did not resolve the projected spike-contract "
                             "skill: " + redact(skill[-200:]))
    notes = ["harness sync reported %s and harness doctor reported %s" % (SYNC_DONE, NO_DRIFT),
             "two separate fresh headless turns answered from the synced files: the rendered "
             "personal identity, and YES for the spike-contract skill"]
    gap = native_only(home, "the projected role list")
    if gap:
        notes.append(gap)
        raise Unverified(observed(notes, "the installed roles were therefore not observed"))
    expected = sorted(path.stem for path in (ROOT / "primitives" / "roles").glob("*.md"))
    listed = home.answer(home.session(ROLES_PROMPT))
    missing = [name for name in expected if name not in listed]
    if missing:
        raise AssertionError(observed(notes, "the client listed no subagent_type for %s of %s "
                                      "harness roles, starting with %s"
                                      % (len(missing), len(expected), missing[0])))
    notes.append("and a subagent-type list carrying all %s harness roles beside the client's "
                 "native ones" % len(expected))
    return "; ".join(notes) + "."


DELEGATION_DENY = "Delegation is off"
SPAWN_COUNT_PROMPT = SPAWN_PROMPT


def stance_link(home, name):
    """Where the selected variant of one stance is resolved from, on a runtime that links it."""
    return home.client_dir / "rules" / "harness-stances" / (name + ".md")


def link_target(path, variants=()):
    """Which variant is resolved at `path`, whether it was linked there or copied there.

    A runtime that copies the selected variant instead of linking it resolves exactly the same
    selection, so reading only `readlink` would make every copying surface report `""` and the
    check would hold vacuously. Given the candidate variant files, a copy is named by its bytes.
    """
    try:
        return Path(os.readlink(str(path))).name
    except OSError:
        pass
    try:
        body = Path(path).read_bytes()
    except OSError:
        return ""
    for variant in variants:
        try:
            if Path(variant).read_bytes() == body:
                return Path(variant).name
        except OSError:
            continue
    return ""


def select(home, dimension, variant, expected=0):
    config = home.config()
    config["stances"][dimension] = variant
    home.write_config(config)
    return home.harness("sync", expected=expected)


def case_stance_switch(home):
    """docs/compatibility.md step 2: the same spawn under two delegation variants.

    The pass is the client's own behaviour changing with the selection — one subagent transcript
    under `tiered` and the stance's own refusal with none under `off` — with the resolved link
    read beside it. A client that never spawned under `tiered` was not observed switching, so the
    case is `unverified` rather than passing on the refusal alone.
    """
    home.seed(stances={"delegation": "tiered"})
    home.harness("sync")
    gap = native_only(home, "a spawn's subagent transcript")
    link = stance_link(home, "delegation")
    tiered_target = link_target(link)
    if gap:
        raise Unverified(gap + "; the resolved delegation link read " + (tiered_target or "<none>"))
    tiered = home.session(SPAWN_COUNT_PROMPT)
    if not home.subagents(tiered["session_id"]):
        raise Unverified("the tiered variant's session wrote no subagent transcript, so no switch "
                         "was observed")
    select(home, "delegation", "off")
    off_target = link_target(link)
    denied = home.session(SPAWN_COUNT_PROMPT)
    spawned = home.subagents(denied["session_id"])
    answer = home.answer(denied) + home.orchestrator_text(denied["session_id"])
    if spawned:
        raise AssertionError("the off variant still wrote %s subagent transcript(s)" % len(spawned))
    if DELEGATION_DENY not in answer:
        raise AssertionError("the off variant wrote no subagent transcript but the client never "
                             "reported the stance's own refusal: " + redact(answer[-200:]))
    if tiered_target and off_target and tiered_target == off_target:
        raise AssertionError("the resolved delegation link stayed at " + tiered_target)
    return ("Cycling delegation tiered -> off in one home with a fresh headless session each time, "
            "the same unnamed Agent spawn ran under tiered (1 subagent transcript) and under off "
            "was refused with \"%s\" and 0 subagent transcripts; the resolved delegation.md link "
            "moved %s -> %s." % (DELEGATION_DENY, tiered_target or "<not a link>",
                                 off_target or "<not a link>"))


PROOF_PLAIN = ("# Proof stance: plain\n\n"
               "End every reply with the single word PLAIN on its own line.\n")
PROOF_TAGGED = ("# Proof stance: tagged\n\n"
                "End every reply with the single word TAGGED on its own line.\n")
PROOF_PROMPT = "Reply with the single word OK, then obey your proof stance."
MISSING_VARIANT = "has no variant 'nonesuch'"


def case_custom_stance(home):
    """docs/compatibility.md step 4: a dimension the repository does not ship, from an external root.

    A custom dimension is prose on every runtime, so the assertion is the client's own reply
    changing with the selection, and a selection that names no variant being refused by the sync
    with the previously resolved link left where it was.
    """
    root = home.primitives / "stances" / "proof"
    root.mkdir(parents=True, exist_ok=True)
    (root / "plain.md").write_text(PROOF_PLAIN)
    (root / "tagged.md").write_text(PROOF_TAGGED)
    home.seed(stances={"proof": "plain"}, roots=[home.primitives])
    home.harness("sync")
    stances = home.harness("stances", "--json")
    if "proof" not in stances:
        raise AssertionError("a custom dimension from an external primitive root did not appear in "
                             "harness stances --json: " + redact(stances[-300:]))
    plain = home.answer(home.session(PROOF_PROMPT, tools=()))
    select(home, "proof", "tagged")
    tagged = home.answer(home.session(PROOF_PROMPT, tools=()))
    if "PLAIN" not in plain.upper() or "TAGGED" not in tagged.upper():
        raise Unverified("the client did not obey the custom dimension under both selections "
                         "(plain reply %s, tagged reply %s), so no custom stance was observed"
                         % (redact(plain[-80:]), redact(tagged[-80:])))
    variants = [root / "plain.md", root / "tagged.md"]
    before = link_target(stance_link(home, "proof"), variants)
    warning = select(home, "proof", "nonesuch", expected=1)
    if MISSING_VARIANT not in warning:
        raise AssertionError("a selection naming no variant was not refused by name: "
                             + redact(warning[-300:]))
    after = link_target(stance_link(home, "proof"), variants)
    if before and after != before:
        raise AssertionError("the refused selection moved the resolved proof link %s -> %s"
                             % (before, after or "<not a link>"))
    return ("A custom proof dimension supplied from an external primitive root appeared in harness "
            "stances --json after sync, and the native client's reply ended PLAIN under proof=plain "
            "and TAGGED under proof=tagged; selecting a variant that does not exist made harness "
            "sync exit 1 with \"%s\" and left the previously resolved variant at %s."
            % (MISSING_VARIANT, before or "<neither linked nor copied on this runtime>"))


# The log path is written into the script rather than read from the environment: a hook the
# client launches inherits the client's environment and not this runner's.
USER_HOOK = """#!/usr/bin/env python3
import sys
open(%r, "a").write("user-hook-fired" + chr(10))
sys.exit(0)
"""
HOOK_SENTINEL = "compose.txt"
HOOK_PROMPT = ("Run exactly this command with your Bash tool: touch ./%s — then reply with the "
               "single word DONE and nothing else." % HOOK_SENTINEL)
# Text only the grade-bash hook writes: `autonomy=ask` alone appears in the stance
# prose the model can see and could be echoed back without any hook having decided.
GRADE_DENY = "grade-bash hook, autonomy="


def user_hook_entries(settings, script):
    """The harness coordinator entry and the user's own entry in a merged PostToolUse table."""
    table = ((settings.get("hooks") or {}).get("PostToolUse") or [])
    rendered = json.dumps(table)
    return ("hook.py" in rendered, str(script) in rendered)


def case_hook_composition(home):
    """docs/compatibility.md step 5: a user-owned hook survives the sync and a deny beats bypass.

    Two readings the 0.11.1 round made by hand: the merged table still holds both entries after a
    sync, and under an acknowledged bypass a `grade-bash` deny still stops a local write — a hook
    decision and a permission posture are different controls, and the hook wins.
    """
    script = home.root / "user-hook.py"
    script.write_text(USER_HOOK % str(home.root / "user-hook.log"))
    script.chmod(0o755)
    home.client_dir.mkdir(parents=True, exist_ok=True)
    (home.client_dir / "settings.json").write_text(json.dumps({
        "hooks": {"PostToolUse": [{"matcher": "Write",
                                   "hooks": [{"type": "command", "command": str(script)}]}]}}) + "\n")
    home.seed(stances={"autonomy": "ask"}, permissions="bypass",
              **{ACK_KEY: True})
    home.harness("sync")
    try:
        settings = json.loads((home.client_dir / "settings.json").read_text())
    except (OSError, ValueError):
        raise Unverified("the sync left no readable client settings file to read the merged table "
                         "from")
    coordinator, user = user_hook_entries(settings, script)
    if not user:
        raise AssertionError("harness sync dropped the user's own PostToolUse Write hook")
    if not coordinator:
        raise AssertionError("the merged table carries the user's hook and no harness coordinator "
                             "entry")
    if home.permission_mode() != BYPASS_MODE:
        raise Unverified("the acknowledged bypass did not sync %s, so a hook deny was never "
                         "measured against it" % BYPASS_MODE)
    sentinel = home.project / HOOK_SENTINEL
    if sentinel.exists():
        sentinel.unlink()
    data = home.session(HOOK_PROMPT, tools=("Bash",))
    answer = home.answer(data) + home.orchestrator_text(str(data.get("session_id", "")))
    outcome = turn_outcome(sentinel.exists(), data)
    if outcome == COMPLETED:
        raise AssertionError("under %s with autonomy=ask the grade-bash hook did not stop the "
                             "write: %s exists" % (BYPASS_MODE, HOOK_SENTINEL))
    if GRADE_DENY not in answer and outcome != BLOCKED:
        raise Unverified("the model declined the turn on its own judgement and no hook deny was "
                         "recorded, so a hook decision was never observed against %s" % BYPASS_MODE)
    return ("A user-owned PostToolUse Write hook added by hand to the client's settings survived "
            "harness sync: the merged table still held the harness coordinator entry and the user "
            "entry with matcher Write, though no Write turn was run to fire it. Under %s with "
            "autonomy=ask the same one-command write was %s with %s permission denial(s) recorded "
            "and %s absent, so a hook deny wins over the "
            "bypass posture."
            % (BYPASS_MODE, outcome, len(permission_denials(data)), HOOK_SENTINEL))


CONFINEMENT_DENY = "This constrained harness role requires an isolated worker"
REPEAT_DENY = "dropping or changing the role name does not change that"
ROLE_SPAWN_PROMPT = ("Use your Agent tool exactly once with subagent_type reviewer and the prompt: "
                     "Reply with the single word DONE. Then report what happened in one line.")
GATHER_BRIEF = "Reply with the first line of notes.txt in the workspace and nothing else.\n"
GATHER_LINE = "orange marmalade is the first line"
ARTIFACT_REFUSAL = "--artifact must be a Markdown filename, not a path"


def role_run(home, name, brief, *extra, **kwargs):
    return home.harness("role", "run", name, "--workspace", str(home.project),
                        "--prompt-file", str(brief), *extra, **kwargs)


def case_role_confinement(home):
    """docs/compatibility.md step 6: a constrained role is refused natively and runs isolated.

    The native refusal is the Claude Code spawn hook's; the isolated worker and the artifact
    boundary are the harness's own and are read on every runtime.
    """
    home.seed()
    home.harness("sync")
    notes = []
    gap = native_only(home, "a native constrained-role spawn")
    if not gap:
        denied = home.session(ROLE_SPAWN_PROMPT)
        text = home.answer(denied) + home.orchestrator_text(denied["session_id"])
        spawned = home.subagents(denied["session_id"])
        if spawned:
            raise AssertionError("a native reviewer spawn wrote %s subagent transcript(s)"
                                 % len(spawned))
        if CONFINEMENT_DENY not in text:
            raise Unverified("the native reviewer spawn wrote no subagent transcript, and the "
                             "constrained-role refusal was not in what the client reported, so "
                             "the deny itself was not observed")
        notes.append("a native spawn of subagent_type reviewer was denied with \"%s\" and 0 "
                     "subagent transcripts were written" % CONFINEMENT_DENY)
    else:
        notes.append(gap)
    (home.project / "notes.txt").write_text(GATHER_LINE + "\n")
    brief = home.root / "gatherer-brief.md"
    brief.write_text(GATHER_BRIEF)
    gathered = role_run(home, "gatherer", brief)
    if "status: completed" not in gathered or "isolated-cli" not in gathered:
        raise Unverified(observed(notes, "harness role run gatherer did not complete as an "
                                  "isolated-cli worker: " + redact(gathered[-300:])))
    if GATHER_LINE not in gathered:
        raise AssertionError(observed(notes, "the isolated gatherer did not return the workspace "
                                      "line it was asked for: " + redact(gathered[-200:])))
    escape = role_run(home, "planner", brief, "--artifact", "../escape.md", expected=1)
    if ARTIFACT_REFUSAL not in escape:
        raise AssertionError(observed(notes, "a planner artifact above the workspace was not "
                                      "refused by name: " + redact(escape[-200:])))
    if (home.project.parent / "escape.md").exists():
        raise AssertionError(observed(notes, "the refused artifact path still wrote a file above "
                                      "the workspace"))
    notes.append("harness role run gatherer exited 0 with status: completed, mode: isolated-cli and "
                 "returned the workspace line it was asked for, and a planner --artifact above the "
                 "workspace exited 1 with \"%s\" writing no file" % ARTIFACT_REFUSAL)
    if gap:
        raise Unverified("; ".join(notes))
    return "; ".join(notes) + "."


FRAMEWORK_ORIGIN = "which this installation runs as the constrained"
FRAMEWORK_ROOTS = "needs the framework's input roots as read roots"
INTEGRATIONS = ROOT / "policy" / "integrations"


def descriptor_spawn(directory=INTEGRATIONS):
    """The first declared spawn with phrases, of the first descriptor the spawn hook would load.

    Read from `policy/integrations/` rather than restated, and naming no framework: a driver that
    hard-codes the phrases would keep passing after the descriptor stopped naming them, which is
    the one thing `spawn-confinement` exists to notice. A descriptor that does not validate is
    skipped, because the hook ignores it and a case built on it would assert against no rule.
    """
    for path in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not data.get("spawns") or frameworks.problems(data):
            continue
        for spawn in data["spawns"]:
            if spawn.get("phrases"):
                return data, spawn
    raise Unverified("no valid integration descriptor declares a spawn with phrases to classify "
                     "against")


# The point `framework_deny` in `lib/harness_core/lifecycle.py` logs when a descriptor classifies
# a spawn as a constrained role, and the answer it logs beside it. That call is the only writer of
# the point, and it writes it on the same path that returns the refusal, so the row is the
# refusal as the hook made it. The row holds the session and the fingerprinted brief, not the
# refusal's wording and not a tool-use id: see `logged_refusals`.
FRAMEWORK_POINT = "framework-spawn"


def logged_refusals(home, session_id):
    """The decision log's framework-spawn denials for `session_id`, oldest first.

    The log is `decisions.jsonl` under the disposable home's own state directory, which is where
    `policy/hooks/decisions.py` writes when the client runs a hook with that home as `HOME`. A
    headless client need not repeat a PreToolUse deny's reason in its answer, so this is how the
    case sees a refusal the client did not report. A line that does not parse is skipped rather
    than read as a refusal.
    """
    path = home.root / ".local" / "state" / "agent-harness" / "decisions.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if (isinstance(row, dict) and row.get("kind") == "decision"
                and row.get("point") == FRAMEWORK_POINT
                and row.get("deterministic_answer") == "deny"
                and session_id and row.get("session_id") == session_id):
            rows.append(row)
    return rows


def framework_brief(spawn, corroboration):
    """A brief carrying enough of a declared spawn's own sentences to be recognised."""
    phrases = list(spawn.get("phrases") or [])[:max(2, corroboration)]
    if len(phrases) < corroboration:
        raise Unverified("the descriptor's %s spawn declares %s phrase(s), fewer than the %s it "
                         "asks for as corroboration" % (spawn["id"], len(phrases), corroboration))
    return ("Use your Agent tool exactly once with no subagent_type and this prompt: "
            + " ".join(phrases) + " Then report in one line what happened.")


def case_spawn_confinement(home):
    """docs/compatibility.md: a framework's review spawn is confined by what it carries (#291).

    The point of the case is that dropping the role name does not drop the confinement, so the
    spawn under test names no `subagent_type` at all and carries the descriptor's own sentences.
    A false-positive check runs beside it: ordinary work must still spawn, or a guard that
    refuses everything would read as a pass.
    """
    home.seed()
    home.harness("sync")
    gap = native_only(home, "a native spawn's refusal and its subagent transcripts")
    if gap:
        raise Unverified(gap + ", so spawn confinement was not observed")
    data, spawn = descriptor_spawn()
    brief = framework_brief(spawn, int(data.get("corroboration") or 2))
    refused = home.session(brief)
    text = home.answer(refused) + home.orchestrator_text(refused["session_id"])
    wrote = home.subagents(refused["session_id"])
    if wrote:
        raise AssertionError("an unnamed spawn carrying the descriptor's own %s sentences wrote "
                             "%s subagent transcript(s)" % (spawn["id"], len(wrote)))
    logged = logged_refusals(home, refused["session_id"])
    reported = CONFINEMENT_DENY in text
    if not logged and not reported:
        raise Unverified("the unnamed framework spawn wrote no subagent transcript, but neither the "
                         "harness decision log held a %s deny for its session nor was the "
                         "constrained-role refusal in what the client reported, so the "
                         "classification itself was not observed" % FRAMEWORK_POINT)
    notes = ["an Agent spawn naming no subagent_type, carrying only the descriptor's own %s "
             "sentences, wrote 0 subagent transcripts" % spawn["id"]]
    if logged:
        notes.append("the harness decision log recorded %s %s deny row(s) for its session"
                     % (len(logged), FRAMEWORK_POINT))
    if reported:
        notes.append("the client reported the refusal \"%s\"" % CONFINEMENT_DENY)
        for clause, what in ((FRAMEWORK_ORIGIN, "what it recognised"),
                             (FRAMEWORK_ROOTS, "the read roots that worker needs")):
            if clause not in text:
                raise AssertionError(observed(notes, "the refusal did not name %s" % what))
        notes.append("and the refusal named both the framework work it recognised and the input "
                     "roots the isolated worker needs")
    else:
        # The row carries no reason, so the wording is the unit tests' to hold, not this run's.
        notes.append("the client did not repeat the refusal, and the log row carries no reason, so "
                     "its wording was not observed in this run")
    ordinary = home.session(SPAWN_PROMPT)
    if not home.subagents(ordinary["session_id"]):
        raise AssertionError(observed(notes, "the false-positive check failed: an ordinary unnamed "
                                      "spawn carrying none of the descriptor's sentences wrote no "
                                      "subagent transcript either, so the guard refuses everything"))
    notes.append("while an ordinary unnamed spawn in the same home still ran and wrote its own "
                 "subagent transcript, so the guard classifies rather than refusing every spawn")
    return "; ".join(notes) + "."


GATE_REPO_FILES = {
    "AGENTS.md": "# probe\n\n## Gate\n\n```sh\npython3 gate.py\n```\n",
    "gate.py": ("import pathlib, sys\n"
                "log = pathlib.Path(__file__).with_name('gate-runs.log')\n"
                "log.write_text(log.read_text() + 'run\\n' if log.exists() else 'run\\n')\n"
                "sys.exit(1 if pathlib.Path(__file__).with_name('red').exists() else 0)\n"),
    "tracked.txt": "one\n",
}
WRITING_GATE = ("import pathlib, sys\n"
                "log = pathlib.Path(__file__).with_name('gate-runs.log')\n"
                "log.write_text(log.read_text() + 'run\\n' if log.exists() else 'run\\n')\n"
                "pathlib.Path(__file__).with_name('tracked.txt').write_text('two\\n')\n"
                "sys.exit(0)\n")
GATE_EVENT = "Stop"


# Split, as the secret-key name is above, so the lint's address pattern does not match a
# throwaway committer identity that reaches no mailbox.
PROBE_EMAIL = "probe@" "example.invalid"


def probe_repo(repo, home):
    """One commit in a disposable repository, under an identity that is nobody's."""
    for args in (("init", "-q"), ("add", "-A"),
                 ("-c", "user.email=" + PROBE_EMAIL, "-c", "user.name=probe",
                  "commit", "-qm", "probe")):
        run(["git", "-C", str(repo)] + list(args), env=home.env())


def gate_repo(home):
    repo = home.root / "gate-repo"
    repo.mkdir()
    for name, body in GATE_REPO_FILES.items():
        (repo / name).write_text(body)
    probe_repo(repo, home)
    return repo


def gate_runs(repo):
    log = repo / "gate-runs.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def gate_state(home, repo):
    """The stop-gate hook's own state record for this repository, or ``{}``."""
    digest = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()
    path = home.root / ".local" / "state" / "agent-harness" / "stop-gate" / (digest + ".json")
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def stop_turn(home, repo, session):
    """Deliver one Stop event to the runtime's own coordinator, as the client does.

    The gate's invalidation rule is a hook decision, not a model one: driving the coordinator
    reads exactly what the client's Stop would, and an eleven-turn block-and-release sequence
    costs no model turn. The observation says so rather than claiming eleven client turns.
    """
    adapter = ROOT / "adapters" / home.runtime / "hook.py"
    payload = json.dumps({"hook_event_name": GATE_EVENT, "cwd": str(repo), "session_id": session})
    result = run([sys.executable, str(adapter)], input=payload, env=home.env(), cwd=str(repo))
    try:
        return json.loads(result.stdout or "{}")
    except ValueError:
        return {}


def case_gate_invalidation(home):
    """docs/compatibility.md step 9: a green gate is reused, a changed tree is not.

    Every reading is the hook's own state record and the gate's run counter, which is what the
    0.11.1 round read by hand.
    """
    home.seed(stances={"autonomy": "execute"})
    home.harness("sync")
    repo = gate_repo(home)
    trusted = home.harness("trust", str(repo))
    if str(repo) not in trusted:
        raise Unverified("the disposable repository could not be trusted for the gate: "
                         + redact(trusted[-200:]))
    session = "probe-green"
    stop_turn(home, repo, session)
    first = gate_runs(repo)
    if first != 1 or gate_state(home, repo).get("status") != "passed":
        raise Unverified("the green gate did not run once and record a pass (runs %s, status %s)"
                         % (first, gate_state(home, repo).get("status")))
    stop_turn(home, repo, session)
    if gate_runs(repo) != first:
        raise AssertionError("an unchanged tree reran the gate (%s runs)" % gate_runs(repo))
    (repo / "untracked.txt").write_text("new\n")
    stop_turn(home, repo, session)
    (repo / "tracked.txt").write_text("changed\n")
    run(["git", "-C", str(repo), "add", "-A"], env=home.env())
    stop_turn(home, repo, session)
    if gate_runs(repo) != first + 2:
        raise AssertionError("an untracked file and a staged edit forced %s reruns, not 2"
                             % (gate_runs(repo) - first))
    counter = gate_runs(repo)
    (repo / "red").write_text("")
    blocks = 0
    for index in range(12):
        decision = stop_turn(home, repo, "probe-red")
        if decision.get("decision") == "block":
            blocks += 1
            continue
        break
    state = gate_state(home, repo)
    if not blocks or state.get("status") != "unverified":
        raise AssertionError("a red gate blocked %s times and released with status %s, not a "
                             "bounded block and an unverified release" % (blocks, state.get("status")))
    red_runs = gate_runs(repo) - counter
    (repo / "red").unlink()
    (repo / "gate.py").write_text(WRITING_GATE)
    run(["git", "-C", str(repo), "add", "-A"], env=home.env())
    stop_turn(home, repo, "probe-writing")
    writing = gate_state(home, repo)
    if writing.get("status") != "unverified" or writing.get("green_hash"):
        raise AssertionError("a gate that wrote a file while running was recorded %s with "
                             "green_hash %s" % (writing.get("status"), writing.get("green_hash")))
    return ("With a trusted disposable repository whose ## Gate block logged each run, a green tree "
            "ran the gate once and recorded status: passed; an unchanged tree reused that result "
            "without rerunning it; adding an untracked file and then staging an edit each forced "
            "exactly one rerun (counter %s -> %s), both green. With the gate red the Stop decision "
            "blocked %s consecutive times over %s further gate runs and then released with status: "
            "unverified, and a gate that writes a file while running released unverified with no "
            "green hash recorded. The Stop events were delivered to this runtime's own coordinator "
            "rather than by that many client turns; every reading is the hook's own state record."
            % (first, counter, blocks, red_runs))


TASK_OBJECTIVE = "Append one marker line to progress.txt"
CLAUDE_MARKER = "CLAUDE-WAS-HERE"
HANDOFF_PROMPT = ("Read .agent-harness/task.json in this directory. Carry out its first next step "
                  "exactly, then reply with one line: OBJECTIVE=<its objective> "
                  "STATUS=<its verification status>.")
STALE_SAVE = "task revision changed since --revision 1"


def task_repo(home):
    repo = home.project
    (repo / "progress.txt").write_text("start\n")
    probe_repo(repo, home)
    return repo


def task_revision(repo):
    """The revision the task record stands at, or ``None`` when there is no readable record.

    `lib/harness_core/tasks.py` refuses a writer whose `--revision` is not the current one and
    writes the next: a save against a spent revision is the refusal, and against the current one
    it is the next revision. Both readings in this case are that rule.
    """
    try:
        return json.loads((repo / ".agent-harness" / "task.json").read_text()).get("revision")
    except (OSError, ValueError, AttributeError):
        return None


def task_contract():
    # The writing runtime is `--runtime` on the command, not a contract field: `tasks.FIELDS`
    # refuses a payload carrying one.
    return json.dumps({"objective": TASK_OBJECTIVE,
                       "next_steps": ["Append the line %s to progress.txt" % CLAUDE_MARKER],
                       "verification": {"status": "passed"}})


def case_bidirectional_handoff(home):
    """docs/compatibility.md step 11: one task record, written and read across runtimes.

    The caller's own `passed` is retained as evidence and never adopted: what a reader must see is
    `unverified`, because nothing verified it in the reading session.
    """
    home.seed(stances={"autonomy": "execute"}, permissions="bypass", **{ACK_KEY: True})
    home.harness("sync")
    repo = task_repo(home)
    saved = home.harness("task", "save", "--runtime", home.runtime, "--revision", "0",
                         "--input", task_contract(), cwd=repo)
    record = repo / ".agent-harness" / "task.json"
    if not record.exists():
        raise Unverified("harness task save wrote no task record to hand over: "
                         + redact(saved[-300:]))
    data = home.session(HANDOFF_PROMPT, tools=("Bash", "Read", "Edit", "Write"))
    answer = home.answer(data)
    if TASK_OBJECTIVE not in answer:
        raise Unverified("the reading session did not report the record's objective, so the "
                         "handoff was not observed: " + redact(answer[-200:]))
    if "unverified" not in answer.lower():
        raise AssertionError("the reading session reported the caller's own verification status "
                             "rather than unverified: " + redact(answer[-200:]))
    marked = CLAUDE_MARKER in (repo / "progress.txt").read_text(errors="replace")
    notes = ["a %s save at revision 0 wrote revision 1, and a native session read it, reported the "
             "objective and reported the verification status as unverified with the caller's "
             "reported passed retained as evidence only" % home.runtime,
             "its first next step was %s" % ("carried out" if marked else "not carried out")]
    other = "codex" if home.runtime != "codex" else "claude-code"
    home.harness("task", "save", "--runtime", other, "--revision", "1",
                 "--input", task_contract(), cwd=repo)
    if task_revision(repo) != 2:
        raise Unverified(observed(notes, "a --runtime %s save against revision 1 did not produce "
                                  "revision 2, so there was no cross-runtime record to read back"
                                  % other))
    back = home.answer(home.session(HANDOFF_PROMPT, tools=("Bash", "Read")))
    if other not in back:
        raise Unverified(observed(notes, "a %s-written record was saved at revision 2 but the "
                                  "reading session did not name the writing runtime, so the "
                                  "return leg was not observed" % other))
    notes.append("a --runtime %s save against revision 1 then produced revision 2 and a native %s "
                 "session read that record back and named the writing runtime; the %s client's own "
                 "native turn is that target's own round and was not run here"
                 % (other, home.runtime, other))
    # The record now stands at revision 2, so revision 1 is spent: `tasks.save` refuses a writer
    # whose expected revision is not the current one, which is the rule this sequence follows.
    stale = home.harness("task", "save", "--runtime", other, "--revision", "1",
                         "--input", task_contract(), expected=1, cwd=repo)
    if STALE_SAVE not in stale:
        raise AssertionError(observed(notes, "a second save against the spent revision 1 was not "
                                      "refused by name: " + redact(stale[-200:])))
    notes.append("repeating that --revision 1 save against the now-current revision 2 exited 1 "
                 "with \"%s\"" % STALE_SAVE)
    (repo / "progress.txt").write_text("edited after the handoff\n")
    shown = home.harness("task", "show", cwd=repo)
    if "stale" not in shown:
        raise AssertionError(observed(notes, "an edit after the handoff left harness task show "
                                      "reporting a current record: " + redact(shown[-200:])))
    notes.append("and after an unrelated edit harness task show reported the record stale")
    return "; ".join(notes) + "."


LEGACY_RULE = "delegation.md"
OWN_KEY = "MY_OWN_KEY"
ADOPT_HINT = "--adopt"
PRESERVED = "user changes preserved"
RESTORED_PROMPT = ("Reply with two lines: first the single word from your own instructions file, "
                   "then NONE if you have no harness stances and otherwise the word HARNESS.")


def seed_prior_install(home):
    """A home that already has a user's own files where the harness wants to put its own."""
    client = home.client_dir
    (client / "rules").mkdir(parents=True, exist_ok=True)
    (client / "skills" / "own-skill").mkdir(parents=True, exist_ok=True)
    legacy = client / "rules" / LEGACY_RULE
    legacy.write_text("# the user's own delegation rule\n\nPRESERVED\n")
    instructions = client / "CLAUDE.md"
    instructions.write_text("# the user's own instructions\n\nPRESERVED\n")
    skill = client / "skills" / "own-skill" / "SKILL.md"
    skill.write_text("# own skill\n")
    (client / "settings.json").write_text(json.dumps({"env": {OWN_KEY: "kept"}}) + "\n")
    return {"legacy": (legacy, legacy.read_bytes()), "instructions": (instructions,
                                                                      instructions.read_bytes()),
            "skill": (skill, skill.read_bytes())}


def case_migration_uninstall(home):
    """docs/compatibility.md step 7: adoption is refused until it is asked for, and reversed.

    Every file the harness adopted must come back byte for byte, which is the only reading that
    makes an uninstall safe to recommend.
    """
    home.seed()
    before = seed_prior_install(home)
    refused = home.harness("sync", expected=2)
    if ADOPT_HINT not in refused or LEGACY_RULE not in refused:
        raise AssertionError("a sync over a user's own files did not name the collisions and %s: %s"
                             % (ADOPT_HINT, redact(refused[-300:])))
    for name, (path, body) in before.items():
        if path.read_bytes() != body:
            raise AssertionError("the refused sync already overwrote the user's " + name)
    home.harness("sync", "--adopt")
    settings = json.loads((home.client_dir / "settings.json").read_text())
    if OWN_KEY not in json.dumps(settings.get("env") or {}):
        raise AssertionError("the adopting sync dropped the user's own settings key")
    if before["skill"][0].read_bytes() != before["skill"][1]:
        raise AssertionError("the adopting sync rewrote the user's own skill")
    removed = home.harness("uninstall", expected=2)
    if PRESERVED not in removed:
        raise AssertionError("harness uninstall did not report what it preserved: "
                             + redact(removed[-300:]))
    for name, (path, body) in before.items():
        if not path.exists():
            raise AssertionError("harness uninstall did not restore the user's " + name)
        if path.read_bytes() != body:
            raise AssertionError("harness uninstall restored the user's %s with changed bytes"
                                 % name)
    leftovers = sorted(path.name for path in home.client_dir.glob("harness-*"))
    leftovers += ["rules/harness-stances"] if (home.client_dir / "rules"
                                               / "harness-stances").exists() else []
    if leftovers:
        raise AssertionError("harness links remained after uninstall: " + ", ".join(leftovers))
    answer = home.answer(home.session(RESTORED_PROMPT, tools=()))
    if "PRESERVED" not in answer.upper():
        raise Unverified("the restored instructions were byte-identical on disk, but no native turn "
                         "answered from them: " + redact(answer[-200:]))
    return ("harness sync without %s exited 2 and named the pre-existing rules/%s and the non-link "
            "instructions file without overwriting anything; %s then exited 0, kept the user's own "
            "settings key and left the user's own skill byte-identical; harness uninstall exited 2 "
            "reporting \"%s\", restored every adopted file byte-identical, left no harness link "
            "under the client directory, and a native turn afterwards answered from the user's "
            "restored instructions." % (ADOPT_HINT, LEGACY_RULE, ADOPT_HINT, PRESERVED))


CASES = {
    "installation": (case_installation,
                     "sync a disposable home from this checkout, read harness doctor, and ask "
                     "fresh native turns for the rendered identity, a projected skill and the "
                     "subagent types the client offers"),
    "stance-switch": (case_stance_switch,
                      "cycle the delegation stance tiered -> off in one home and read what the "
                      "same unnamed spawn did under each, beside the resolved variant link"),
    "custom-stance": (case_custom_stance,
                      "supply a dimension this repository does not ship from an external "
                      "primitive root, read the client's reply under each variant, and refuse a "
                      "selection naming no variant"),
    "framework-spawn-routing": (case_framework_spawn_routing,
                               "drive the spawn hook with a fixture recipe built from a declared "
                               "integration descriptor, then run the cost-posture turn"),
    "permission-controls": (case_permission_controls,
                            "sync the manual, unacknowledged bypass, acknowledged bypass and auto "
                            "postures, and read each one's synced permission mode and what a "
                            "native turn asking for one file write then did"),
    "hook-composition": (case_hook_composition,
                         "merge a user-owned PostToolUse hook through a sync and read whether a "
                         "grade-bash deny still stops a write under an acknowledged bypass"),
    "role-confinement": (case_role_confinement,
                         "spawn a constrained role natively and read the refusal, then run the "
                         "same work as an isolated worker and refuse an artifact path above the "
                         "workspace"),
    "spawn-confinement": (case_spawn_confinement,
                          "spawn a framework's review work with no subagent_type at all, carrying "
                          "only the descriptor's own sentences, and read the refusal from the "
                          "harness decision log and the client's answer beside an "
                          "ordinary spawn that must still run"),
    "cost-posture": (case_cost_posture,
                     "sync a non-default cost variant, spawn an unnamed subagent in a new native "
                     "session, and read its meta record, brief, the usage feed and the usage rows"),
    "gate-invalidation": (case_gate_invalidation,
                          "trust a disposable repository with a gate that logs each run, and read "
                          "the hook's own state through reuse, invalidation, a bounded red block "
                          "and a gate that writes while it runs"),
    "bidirectional-handoff": (case_bidirectional_handoff,
                              "save one task record, read it back in a native session, refuse a "
                              "stale revision, and continue it from the other runtime"),
    "migration-uninstall": (case_migration_uninstall,
                            "sync over a user's own files without and then with adoption, "
                            "uninstall, and compare every restored file byte for byte"),
}


def confirmed_targets(value):
    """The client surfaces an operator named as hand-compared, as a set of ids.

    Confirmation is per target and never global: one surface compared against a hand run says
    nothing about another, and `True` for every surface at once is exactly the claim this flag
    exists to stop anyone making by accident.
    """
    if not value:
        return frozenset()
    if isinstance(value, bool):
        raise SystemExit("--home-confirmed names one client; there is no confirmation of every "
                         "surface at once")
    if isinstance(value, str):
        value = [value]
    names = frozenset(str(name).strip() for name in value if str(name).strip())
    unknown = sorted(name for name in names if name not in CLIENTS)
    if unknown:
        raise SystemExit("unknown client to confirm: " + ", ".join(unknown))
    return names


def unobserved_note(client, confirmed):
    """Why a verdict from this client surface is not yet trusted, or ``""``."""
    spec = CLIENTS[client]
    if spec.get("observed") or client in confirmed_targets(confirmed):
        return ""
    return UNOBSERVED_HOME % (spec["home_var"], spec["runtime"], spec["runtime"])


def probe(client, name, model, keep, confirmed=()):
    """Run one case and return its result, observation and the home it used.

    A surface whose configuration home this runner has never been run against cannot turn an
    assertion that held into a qualification pass: the reading itself is unconfirmed, so the
    verdict is `unverified` with the observation kept, exactly as an unobserved case is.
    """
    started = time.time()
    spec = CLIENTS[client]
    home = HOMES[spec["runtime"]](spec, name, model, keep=keep)
    caveat = unobserved_note(client, confirmed)
    try:
        observation = CASES[name][0](home)
        return {"case": name, "result": "unverified" if caveat else "passed",
                "observation": redact(observed([observation], caveat) if caveat else observation,
                                      [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    except AssertionError as error:
        # On an unconfirmed surface the reading itself is in question, so an assertion that did
        # not hold is not yet a defect in the harness: it is `unverified` with what was read.
        return {"case": name, "result": "unverified" if caveat else "failed",
                "observation": redact(observed([str(error)], caveat) if caveat else error,
                                      [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    except Exception as error:  # An unobserved case is unverified, never a pass.
        reason = "%s: %s" % (type(error).__name__, error) if not isinstance(error, Unverified) else str(error)
        return {"case": name, "result": "unverified", "observation": redact(reason, [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    finally:
        home.discard()


HEADER_KEYS = ("kind", "client", "harness_version", "runtime_version", "client_version",
               "platform", "source_commit", "tier_routing")


def progress_path(client, out):
    """Where finished cases are appended, outside the checkout a clean run requires."""
    if out:
        return Path(str(out) + ".partial.jsonl")
    return Path(tempfile.gettempdir()) / ("harness-native-%s-%s.partial.jsonl" % (client, VERSION))


def append_case(path, header, item):
    """Record one finished case durably, before the next case is started.

    A killed round then costs the case it was running rather than the whole round: the lines
    already on disk rebuild a partial record, which the evidence schema accepts because it unions
    cases across records and blocks any linked failure regardless.
    """
    if path is None:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "a") as handle:
        handle.write(json.dumps(dict(header, **item), sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def append_routing(path, header):
    """Declare the round's class routing before the first case runs.

    A line with no case is not a result and `progress_lines` ignores it; what it does is put the
    executing and assessing classes on disk before anything they could bias has run, so a round
    killed in its first case still says who ran it.
    """
    if path is None:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "a") as handle:
        handle.write(json.dumps(dict(header, declared="tier_routing"), sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def logged_routing(items):
    """Every distinct routing the surviving lines were logged under."""
    seen = []
    for item in items:
        routing = item.get("tier_routing")
        if routing not in seen:
            seen.append(routing)
    return seen


def under_routing(items, tier_routing):
    """`items` logged under this routing, refusing a log that mixes two of them.

    A record whose cases were produced by two different classes cannot say which class produced
    an observation, and merging them silently is the one thing the routing is recorded to stop.
    """
    keep = [item for item in items if item.get("tier_routing") == tier_routing]
    others = [one for one in logged_routing(items) if one != tier_routing]
    if others:
        raise SystemExit(
            "the durable log holds cases executed under another class routing (%s); rerun them "
            "under %s or build from their own log"
            % ("; ".join(sorted(json.dumps(one, sort_keys=True) for one in others)),
               json.dumps(tier_routing, sort_keys=True)))
    return keep


def progress_lines(path, header=None):
    """Every finished case on disk, ignoring a line torn by the kill or from another round."""
    items = []
    if path is None or not Path(path).exists():
        return items
    for raw in Path(path).read_text(errors="replace").splitlines():
        try:
            item = json.loads(raw)
        except ValueError:
            continue  # A half-written final line is dropped, never guessed at.
        if not isinstance(item, dict) or not item.get("case"):
            continue
        if header and any(item.get(key) != header[key] for key in HEADER_KEYS):
            continue  # Evidence for another commit or client is a different claim.
        items.append(item)
    return items


def build_record(items):
    """Union per-case lines into one evidence record; the latest line for a case wins."""
    if not items:
        raise SystemExit("no finished acceptance case to build a record from")
    data = {key: items[-1].get(key) for key in HEADER_KEYS}
    cases, observations = {}, {}
    for item in items:
        cases[item["case"]] = item.get("result")
        if item.get("observation"):
            observations[item["case"]] = item["observation"]
    data["cases"] = cases
    data["observations"] = [observations[case] for case in cases if case in observations]
    return data


def scoped(client, data):
    """State the path set whose change invalidates this record, so a reviewer need not derive it.

    The catalog grants the scope; a record that claims any other one is rejected. See
    docs/compatibility.md.
    """
    entry = dict(CLIENTS[client], id=client)
    data["invalidation_scope"] = compatibility.evidence_scope(catalog(), entry)
    return data


def selected(names):
    required = catalog()["required_cases"]
    if names in (None, "all"):
        return list(required)
    chosen = [name.strip() for name in names.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in required]
    if unknown:
        raise SystemExit("unknown acceptance case: " + ", ".join(unknown))
    return chosen


def routing(client, execution=None, assessment=None):
    """This target's class routing, refusing a pair that would make the executor its own reader."""
    try:
        return qualification.resolve(ROOT, CLIENTS[client]["runtime"],
                                     execution or qualification.EXECUTION_DEFAULT,
                                     assessment or qualification.ASSESSMENT_DEFAULT)
    except ValueError as error:
        raise SystemExit(str(error))


def plan(client, names, model, confirmed=(), tier_routing=None):
    spec = CLIENTS[client]
    tier_routing = tier_routing or routing(client)
    lines = ["plan: %s, model %s, one disposable %s per case, no client run"
             % (client, model, spec["home_var"]),
             "  tiers: " + qualification.describe(tier_routing)]
    lines += ["  note: " + note for note in tier_routing.get("notes", [])]
    caveat = unobserved_note(client, confirmed)
    if caveat:
        lines.append("  note: " + caveat)
    for name in names:
        how = CASES[name][1] if name in CASES else NOT_AUTOMATED
        lines.append("  %-22s %s" % (name, how))
    return "\n".join(lines)


def record(client, names, model, keep, runner=probe, progress=None, confirmed=(),
           tier_routing=None):
    spec = CLIENTS[client]
    tier_routing = tier_routing or routing(client)
    if git("status", "--porcelain"):
        raise SystemExit("the checkout must be clean: native evidence names a source commit")
    version = client_version(spec["command"])
    header = {
        "kind": "native",
        "client": client,
        "harness_version": VERSION,
        "runtime_version": version,
        "client_version": version,
        "platform": spec["platform"],
        "source_commit": git("rev-parse", "HEAD"),
        # Which class executed these cases and which class must read what they observed. Kept in
        # the per-case header so a resumed round cannot union lines two classes produced.
        "tier_routing": tier_routing,
    }
    append_routing(progress, header)
    results = []
    for name in names:
        item = (runner(client, name, model, keep, confirmed) if name in CASES
                else {"case": name, "result": "unverified", "observation": NOT_AUTOMATED})
        append_case(progress, header, item)
        results.append(item)
    return scoped(client, build_record(progress_lines(progress, header)
                                      or [dict(header, **item) for item in results]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client", required=True, choices=sorted(CLIENTS))
    parser.add_argument("--cases", default="all")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="the cheapest model the client offers; every probe is one turn")
    parser.add_argument("--dry-plan", action="store_true",
                        help="print what would run, without running any client")
    parser.add_argument("--keep-home", action="store_true",
                        help="keep each disposable home for debugging")
    parser.add_argument("--progress", type=Path,
                        help="durable per-case log appended as each case finishes")
    parser.add_argument("--from-progress", action="store_true",
                        help="build the record from the durable log alone, running no client")
    parser.add_argument("--home-confirmed", action="append", default=[], metavar="CLIENT",
                        help="a client whose configuration home was compared against a hand run; "
                             "repeat for each, and never for a surface nobody compared")
    parser.add_argument("--execution-class", default=qualification.EXECUTION_DEFAULT,
                        help="the capability class of the worker running the cases")
    parser.add_argument("--assessment-class", default=qualification.ASSESSMENT_DEFAULT,
                        help="the capability class of the reader assessing the observations")
    args = parser.parse_args(argv)
    names = selected(args.cases)
    tier_routing = routing(args.client, args.execution_class, args.assessment_class)
    if args.dry_plan:
        print(plan(args.client, names, args.model, args.home_confirmed, tier_routing))
        return 0
    progress = args.progress or progress_path(args.client, args.out)
    if args.from_progress:
        data = scoped(args.client, build_record(under_routing(progress_lines(progress),
                                                             tier_routing)))
    else:
        data = record(args.client, names, args.model, args.keep_home, progress=progress,
                      confirmed=args.home_confirmed, tier_routing=tier_routing)
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all(value == "passed" for value in data["cases"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
