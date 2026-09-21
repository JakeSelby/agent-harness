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
"""
import argparse
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
VERSION = (ROOT / "VERSION").read_text().strip()
DEFAULT_MODEL = "haiku"
TURN_TIMEOUT = 300
# Authentication this machine already holds, passed through by name. A value is never read,
# logged or written by this runner. Profile and file pointers travel; raw AWS key material does
# not, because a profile is enough. `AWS_*` file pointers are re-anchored at the real home
# because the probe's HOME is disposable and an unset pointer hangs the provider lookup.
AUTH_PASSTHROUGH = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
    "AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE", "CLOUD_ML_REGION", "ANTHROPIC_VERTEX_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS",
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

CLIENTS = {
    "claude-code-cli-macos": {"runtime": "claude-code", "platform": "macos", "command": "claude"},
    "claude-code-cli-linux": {"runtime": "claude-code", "platform": "linux", "command": "claude"},
}


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
    """A disposable configuration home: its own HOME, client config directory and state."""

    def __init__(self, command, label, model, keep=False):
        self.command = command
        self.model = model
        self.keep = keep
        self.root = Path(tempfile.mkdtemp(prefix="harness-native-" + label + "-"))
        self.project = self.root / "project"
        self.project.mkdir()
        self.client_dir = self.root / ".claude"
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
        env.update({"HOME": str(self.root), "CLAUDE_CONFIG_DIR": str(self.client_dir),
                    "HARNESS_MANAGE_VSCODE": "false", "PYTHONDONTWRITEBYTECODE": "1",
                    "CI": "1"})
        env.update(extra or {})
        return env

    def harness(self, *args, **kwargs):
        expected = kwargs.pop("expected", 0)
        result = run([sys.executable, str(ROOT / "bin" / "harness")] + list(args),
                     cwd=str(ROOT), env=self.env(kwargs.pop("extra", None)))
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
        directory = self.transcript_dir(session_id)
        if directory is None:
            return ""
        chunks = []
        for path in sorted(directory.glob("*.jsonl")) + sorted(
                (self.client_dir / "projects").glob("*/" + session_id + ".jsonl")):
            chunks.append(path.read_text(errors="replace"))
        return "\n".join(chunks)


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
    if "usage-feed: " in home.orchestrator_text(null_result["session_id"]):
        raise AssertionError("the null variant still fed usage back to the orchestrator")
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


CASES = {
    "cost-posture": (case_cost_posture,
                     "sync a non-default cost variant, spawn an unnamed subagent in a new native "
                     "session, and read its meta record, brief, the usage feed and the usage rows"),
}


def probe(client, name, model, keep):
    """Run one case and return its result, observation and the home it used."""
    started = time.time()
    home = Home(CLIENTS[client]["command"], name, model, keep=keep)
    try:
        observation = CASES[name][0](home)
        return {"case": name, "result": "passed", "observation": redact(observation, [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    except AssertionError as error:
        return {"case": name, "result": "failed", "observation": redact(error, [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    except Exception as error:  # An unobserved case is unverified, never a pass.
        reason = "%s: %s" % (type(error).__name__, error) if not isinstance(error, Unverified) else str(error)
        return {"case": name, "result": "unverified", "observation": redact(reason, [home.root]),
                "seconds": round(time.time() - started, 1), "sessions": home.launched}
    finally:
        home.discard()


def selected(names):
    required = catalog()["required_cases"]
    if names in (None, "all"):
        return list(required)
    chosen = [name.strip() for name in names.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in required]
    if unknown:
        raise SystemExit("unknown acceptance case: " + ", ".join(unknown))
    return chosen


def plan(client, names, model):
    lines = ["plan: %s, model %s, one disposable configuration home per case, no client run"
             % (client, model)]
    for name in names:
        how = CASES[name][1] if name in CASES else NOT_AUTOMATED
        lines.append("  %-22s %s" % (name, how))
    return "\n".join(lines)


def record(client, names, model, keep, runner=probe):
    spec = CLIENTS[client]
    if git("status", "--porcelain"):
        raise SystemExit("the checkout must be clean: native evidence names a source commit")
    results = [runner(client, name, model, keep) if name in CASES
               else {"case": name, "result": "unverified", "observation": NOT_AUTOMATED}
               for name in names]
    version = client_version(spec["command"])
    return {
        "kind": "native",
        "client": client,
        "harness_version": VERSION,
        "runtime_version": version,
        "client_version": version,
        "platform": spec["platform"],
        "source_commit": git("rev-parse", "HEAD"),
        "observations": [item["observation"] for item in results if item["observation"]],
        "cases": {item["case"]: item["result"] for item in results},
    }


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
    args = parser.parse_args(argv)
    names = selected(args.cases)
    if args.dry_plan:
        print(plan(args.client, names, args.model))
        return 0
    data = record(args.client, names, args.model, args.keep_home)
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all(value == "passed" for value in data["cases"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
