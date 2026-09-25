#!/usr/bin/env python3
"""Measure what the harness costs against Claude Code with no harness at all.

`static` counts, without calling a model, what the harness adds to every session. A bare session
loads none of the files counted, so the total is the harness's standing overhead. Tokens are an
estimate from characters (`CHARS_PER_TOKEN`), good for a trend between versions and not for
billing; dollars come from `policy/prices.json`. Codex is not counted: its instructions are
rendered at sync time.

`replay` runs pinned tasks headlessly against a bare profile and against the harness, either the
installed one or a pinned git ref of this repository synced into a config directory of its own, one
history row per `--tag`. It reads cost from the CLI's own JSON result and scores each run with a
held-back check. It calls a model and spends real usage. Reading and limits: docs/benchmarks.md.
"""
import argparse
import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from harness_core import cache_prefix  # noqa: E402  the ledger's miss ratio, one definition
from harness_core import catalog  # noqa: E402  the resolver the hooks load, for the profile fingerprint

CHARS_PER_TOKEN = 4.0
GROWTH_LIMIT = 0.05
# What each counted group covers, carried in the written figure so a reader of the file alone
# knows which set a number is over. The caps `harness lint` prints are a narrower set.
SCOPES = {
    "always_loaded": "claude/CLAUDE.md, claude/rules/, claude/output-styles/ and the stance "
                     "variant config.example.json selects, for the default selection",
    "listings": "one description line per agent, skill and command the session lists",
    "worst_case_est_tokens": "the same files with the longest variant of every stance dimension",
    "note": "`harness lint` counts a narrower set against its caps: instructions, rules and the "
            "longest stance variant, with no output style and no listings",
}
STATIC = Path("benchmarks") / "static.json"
ALLOW = Path("benchmarks") / "allow.json"
TASKS = Path("benchmarks") / "tasks.json"
ORACLES = Path("benchmarks") / "oracles"
HISTORY = Path("benchmarks") / "history.jsonl"
HISTORY_MD = Path("benchmarks") / "history.md"
ARMS = ("bare", "harness")
SNAPSHOT_BRANCH = "main"
# This repository's own gate, as AGENTS.md names it: a snapshot must pass it before any arm runs.
GATE_COMMANDS = (["python3", "bin/harness", "lint"], ["python3", "-m", "unittest", "discover", "-s", "tests"])
RUN_CAP_USD = 2.0
SPEND_CAP_USD = 25.0
THRESHOLD = 0.85
RUN_TIMEOUT = 1800
CHECK_TIMEOUT = 900
SYNC_TIMEOUT = 900
# The harness the user has installed, run as it stands: the one tag that syncs nothing.
CANDIDATE = "candidate"
KEPT_ENV = ("HOME", "USER", "PATH", "TERM")
TOKEN_KINDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens")
# Every arm is fenced the same way: no network, no credential reads. What differs is the profile
# the fence admits, which is the arm's own; see `fence`.
DENY_READ = ["~/.ssh", "~/.aws", "~/.config/gh"]
# The web tools run in the CLI's own process, not under the command sandbox, so the fence's empty
# network allowlist does not reach them; a profile's permission rules do. Both arms are denied them
# whatever their profile allows, since a deny rule outranks any profile's allow.
NO_WEB = ("WebFetch", "WebSearch")
# Where `harness trust` records the roots the stop-gate hook may run a gate in, under HOME.
TRUST_FILE = Path(".config") / "agent-harness" / "trusted.txt"
DEFAULT_CONFIG_DIR = "~/.claude"
# The sandbox matches resolved paths: on macOS `/tmp` is a link to `/private/tmp`, and a rule
# naming the link does not admit the target. Admit both spellings, deduplicated.
SCRATCH_DIRS = tuple(dict.fromkeys(["/tmp", os.path.realpath("/tmp")]))
# The gate this repository's AGENTS.md names, run inside the fence and reported as its own last line.
# The suite's own stdout is block-buffered under a pipe and lands after unittest's stderr summary,
# so the last line of `2>&1` is noise, not the verdict. Filter to the verdict lines and judge the
# tool's output directly rather than whatever the model chose to relay.
# The bar the prompts set, and no more: lint under the arm's own fence. The full suite is
# profile-dependent at every snapshot commit (`claude_dir()` lets CLAUDE_CONFIG_DIR override the
# tests' isolation), so demanding it here measures the profile, not the harness.
PREFLIGHT_PROMPT = "Run exactly this and reply with its output: `python3 bin/harness lint`"
PREFLIGHT_CAP_USD = 0.25
PREFLIGHT_TURNS = 3
PREFLIGHT_RED = re.compile(r"PermissionError|Operation not permitted", re.M)
INHERITED = "inherited"
# What an arm actually loads: the always-on layer, the listed layer, and the personal file.
CONFIG_GLOBS = ("CLAUDE.md", "CLAUDE.personal.md", "rules/**/*.md", "skills/*/SKILL.md",
                "agents/*.md", "output-styles/*.md")
SPAWN_TOOLS = ("Task", "Agent")
# Diagnostic fields `parse_result` reads out of the stream; `backfill` derives the same ones.
STREAM_FIELDS = ("first_call_cache_write", "tool_counts", "spawns", "stop_hooks", "hook_blocks",
                 "cache_miss_ratio")
RESULTS = "results.jsonl"
ENRICHED = "results.enriched.jsonl"


def _description(path):
    """The frontmatter `description`, folded lines included; the part a session lists unasked."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    out, taking = [], False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            out.append(line.split(":", 1)[1].strip())
            taking = True
        elif taking and line[:1] in (" ", "\t"):
            out.append(line.strip())
        else:
            taking = False
    return " ".join(part for part in out if part not in (">", "|", ">-", "|-"))


def _group(root, paths, text=None):
    rows = []
    for path in paths:
        body = text(path) if text else path.read_text(encoding="utf-8")
        rows.append({"path": path.relative_to(root).as_posix(), "lines": body.count("\n") + bool(body),
                     "chars": len(body)})
    return rows


def _sum(rows):
    chars = sum(row["chars"] for row in rows)
    return {"files": len(rows), "lines": sum(row["lines"] for row in rows), "chars": chars,
            "est_tokens": int(round(chars / CHARS_PER_TOKEN))}


def _variants(root, selected):
    """One file per stance dimension: the selected variant, or the longest when none is named."""
    out = []
    stances = root / "claude" / "stances"
    for folder in sorted(p for p in stances.iterdir() if p.is_dir()) if stances.is_dir() else []:
        options = sorted(folder.glob("*.md"))
        if not options:
            continue
        named = folder / (str((selected or {}).get(folder.name)) + ".md")
        out.append(named if selected is not None and named in options
                   else max(options, key=lambda p: (len(p.read_text(encoding="utf-8")), p.name)))
    return out


def measure(root=ROOT):
    """The static figure for one checkout: default selection, worst case, listings and dollars."""
    claude = root / "claude"
    example = root / "config.example.json"
    selected = json.loads(example.read_text(encoding="utf-8")).get("stances", {}) if example.is_file() else {}
    fixed = [p for p in [claude / "CLAUDE.md"] if p.is_file()]
    fixed += sorted((claude / "rules").glob("*.md")) + sorted((claude / "output-styles").glob("*.md"))
    always = _group(root, fixed + _variants(root, selected))
    worst = _group(root, fixed + _variants(root, None))
    listed = sorted((claude / "agents").glob("*.md")) + sorted((claude / "skills").glob("*/SKILL.md"))
    listed += sorted((claude / "commands").glob("*.md"))
    listings = _group(root, listed, _description)
    total = _sum(always + listings)
    version = root / "VERSION"
    return {
        "schema_version": 1,
        "harness_version": version.read_text(encoding="utf-8").strip() if version.is_file() else "",
        "chars_per_token": CHARS_PER_TOKEN,
        "scopes": SCOPES,
        "always_loaded": _sum(always),
        "listings": _sum(listings),
        "total": total,
        "worst_case_est_tokens": _sum(worst + listings)["est_tokens"],
        "largest": sorted(always + listings, key=lambda r: (-r["chars"], r["path"]))[:5],
        "usd": price(root, total["est_tokens"]),
    }


def price(root, tokens):
    """USD the counted layer costs per model: written to the cache once, then read every turn."""
    table = root / "policy" / "prices.json"
    models = json.loads(table.read_text(encoding="utf-8")).get("models", {}) if table.is_file() else {}
    out = {}
    for name, row in sorted(models.items()):
        if name.startswith("claude-") and "cache_write" in row and "cache_read" in row:
            out[name] = {"session_start": round(tokens * row["cache_write"] / 1e6, 6),
                         "later_turn": round(tokens * row["cache_read"] / 1e6, 6)}
    return out


def check(root=ROOT):
    """Errors when the estimate has grown past the limit over the committed figure, unexplained."""
    committed = root / STATIC
    if not committed.is_file():
        return ["%s is missing; run `scripts/cost_bench.py static --write`" % STATIC.as_posix()]
    before = json.loads(committed.read_text(encoding="utf-8"))["total"]["est_tokens"]
    now = measure(root)
    after = now["total"]["est_tokens"]
    if after <= before * (1 + GROWTH_LIMIT):
        return []
    allow = root / ALLOW
    entries = json.loads(allow.read_text(encoding="utf-8")) if allow.is_file() else []
    if any(e.get("harness_version") == now["harness_version"] and e.get("est_tokens") == after
           and str(e.get("reason", "")).strip() for e in entries):
        return []
    return ["static context grew from %d to %d estimated tokens (+%.1f%%, limit %.0f%%); trim it, or "
            "record harness_version, est_tokens and a reason in %s"
            % (before, after, (after / before - 1) * 100 if before else 100.0, GROWTH_LIMIT * 100,
               ALLOW.as_posix())]


# --------------------------------------------------------------------------- replay


def load_tasks(path):
    """The manifest's tasks, or SystemExit naming the first malformed one."""
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))["tasks"]
    for task in tasks:
        missing = [k for k in ("id", "kind", "parent_sha", "good_sha", "prompt", "tests", "max_turns")
                   if k not in task]
        if missing or task["kind"] not in ("issue", "synthetic"):
            raise SystemExit("task %r is malformed: missing %s" % (task.get("id"), missing or "a known kind"))
    return tasks


def prompt_of(task):
    return "\n".join(task["prompt"]) if isinstance(task["prompt"], list) else task["prompt"]


def unsafe_workdir(path, home):
    """Why a run must not start in `path`, or None. A folder under the home directory inherits the
    user's instruction files through the parent-folder walk, which contaminates the bare arm."""
    path, home = Path(path).resolve(), Path(home).resolve()
    if path == home or home in path.parents:
        return "%s is under the home directory" % path
    for parent in path.parents:
        if (parent / ".git").exists():
            return "%s is inside the checkout %s" % (path, parent)
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude"):
            if (parent / name).exists():
                return "%s would inherit %s" % (path, parent / name)
    return None


def scrubbed_env(extra=None, base=None):
    """A shell inside an agent session carries that session's variables; an arm gets none of them."""
    base = os.environ if base is None else base
    env = {name: base[name] for name in KEPT_ENV if name in base}
    env.setdefault("TERM", "dumb")
    env.update(extra or {})
    return env


def arm_env(arm, bare_config, stance_cost=None, base=None, harness_config=None):
    """Each arm points at its own profile directory.

    A profile is authenticated by its absolute path: the CLI stores the credential in the keychain
    under `Claude Code-credentials-<sha256(config dir)[:8]>`, so a copied directory is not signed in
    and cannot be made so by copying files. The harness profile is therefore one the owner signed
    into once, never a copy of the bare one. With none named the harness arm inherits the live
    `~/.claude` through HOME, which carries the owner's personal layer into the comparison."""
    config = bare_config if arm == "bare" else harness_config
    extra = {"CLAUDE_CONFIG_DIR": str(config)} if config else {}
    if stance_cost and arm != "bare":
        extra["HARNESS_STANCE_COST"] = stance_cost
    return scrubbed_env(extra, base)


def arm_profile(arm, env, opts):
    """The profile fingerprint a row of this arm carries: `bare`, or the harness arm's profile.

    The bare arm loads no harness, so it has no profile to digest and says so by name rather than
    by a null a reader would take for a row from before the field. The harness arm's is resolved
    by this checkout's resolver over the checkout the arm's profile was synced from, in the
    arm's own environment, so a pinned tag is fingerprinted as the tag. None when it cannot be.
    HOME is the run's `home`, which is the arm's own outside a test."""
    try:
        module = catalog.posture_module(ROOT)
        if arm == "bare":
            return module.BARE_FINGERPRINT
        home = opts.get("home")
        return module.fingerprint(dict(env, HOME=str(home)) if home else env,
                                  root=Path(opts.get("profile_root") or opts.get("harness_source") or ROOT))
    except Exception:
        return None


def arm_admits(arm, opts):
    """What one arm's fence admits beyond its own profile: for the harness arm on a pinned tag, the
    checkout its profile's links lead to. The bare arm is admitted to no harness content ever."""
    source = opts.get("harness_source")
    return [str(source)] if source and arm != "bare" else []


def config_label(config_dir, home=None):
    """The config directory as a row records it: `inherited`, or the path with `$HOME` as `~`.

    A profile normally sits under the home directory, and a literal home path in a row would be a
    personal string in a file the repository's lint reads. The `~` form names the same directory."""
    if not config_dir:
        return INHERITED
    text, prefix = str(config_dir), str(Path(home) if home else Path.home())
    if text == prefix or text.startswith(prefix + os.sep):
        return "~" + text[len(prefix):]
    return text


def config_fingerprint(config_dir, home=None):
    """What an arm's instruction layer was, as sizes: `{sha, rules, skills, agents, personal_bytes}`.

    The sha is over the sorted `(relative path, byte size)` pairs of CONFIG_GLOBS under the
    directory, so two runs with the same sha loaded the same files at the same lengths. Sizes and
    relative paths only: no content and no home-directory path reaches a row. `INHERITED` means the
    arm launched with no CLAUDE_CONFIG_DIR and therefore read `$HOME/.claude`."""
    root = Path(home or Path.home()) / ".claude" if config_dir in (None, "", INHERITED) \
        else Path(config_dir).expanduser()
    entries = set()
    for pattern in CONFIG_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                entries.add((path.relative_to(root).as_posix(), path.stat().st_size))
    listed = sorted(entries)
    sha = hashlib.sha256("\n".join("%s %d" % pair for pair in listed).encode("utf-8")).hexdigest()[:8]
    under = lambda folder: sum(1 for name, _ in listed if name.startswith(folder + "/"))
    return {"sha": sha, "rules": under("rules"), "skills": under("skills"), "agents": under("agents"),
            "personal_bytes": dict(listed).get("CLAUDE.personal.md", 0)}


def fence(config_dir=None, admit=()):
    """The settings one arm runs under: no network, no web tools, no credential reads, its own
    profile writable.

    A fence that admits only the CLI's default `~/.claude` handicaps whichever arm was moved to a
    bench profile, because this repository's own suite writes under the config directory and under
    `/tmp`; the arm then fails its gate and spends turns on a block the runner imposed. Each arm
    therefore gets its own directory, and the shared scratch directory, readable and writable.
    `denyRead` is the same for every arm.

    `admit` names anything else the profile leads to, admitted for reading only. A profile
    `harness sync` filled is symlinks into the checkout it was synced from, so an arm on a pinned
    tag reads nothing at all unless that checkout is admitted; and an arm that could write it could
    rewrite its own rules, skills and hooks in the middle of the run being measured.

    The web tools are denied here rather than left to each profile: see `NO_WEB`."""
    admitted = [str(config_dir) if config_dir else DEFAULT_CONFIG_DIR] + list(SCRATCH_DIRS)
    readable = admitted + [str(path) for path in admit if path]
    return {"permissions": {"deny": list(NO_WEB)},
            "sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
                        "network": {"allowedDomains": [], "strictAllowlist": True},
                        "filesystem": {"denyRead": list(DENY_READ), "allowWrite": list(admitted),
                                       "allowRead": readable}}}


def arm_command(claude, model, prompt, run_cap=RUN_CAP_USD, config_dir=None, admit=(), max_turns=None):
    """One command line for every arm: the arms differ by environment and by their fence's
    profile, which follows that environment, and by nothing else.

    The output is `stream-json` with hook events, because hook lifecycle events are the only place
    a Stop hook's decision appears and the CLI emits them in no other format. `max_turns` is the
    task's own cap; without it a run is bounded only by the soft budget and the timeout."""
    turns = ["--max-turns", str(int(max_turns))] if max_turns else []
    return [claude, "-p", prompt, "--model", model, "--output-format", "stream-json",
            "--include-hook-events", "--verbose", "--strict-mcp-config", "--no-session-persistence",
            "--max-budget-usd", "%g" % run_cap, "--permission-mode", "acceptEdits"] + turns + [
            "--settings", json.dumps(fence(config_dir, admit))]


def trust_path(home):
    return Path(home) / TRUST_FILE


@contextlib.contextmanager
def _trust_lock(folder):
    """An exclusive lock on the trust file's folder, so two replays never interleave their
    updates. The folder is locked rather than the file, because the cleanup replaces the file."""
    import fcntl
    fd = os.open(str(folder), os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


@contextlib.contextmanager
def trusted_run(workdir, home):
    """The snapshot listed where `harness trust` lists roots, for this run only.

    The stop-gate hook runs a repository's gate only in a folder the user trusted, and a fresh
    snapshot is trusted by nobody, so without this the gate never fires in a replay and the
    harness arm is measured without one of its own behaviours. Every arm's snapshot is listed,
    the bare one included, which has no hook to read it, so the arms still differ by profile
    alone. Afterwards exactly the line added is removed, through an atomic write, and every
    other root the file holds is kept as it was. Both updates hold `_trust_lock`, so replays
    running at once cannot restore a root another removed; `harness trust` takes no lock."""
    path, root = trust_path(home), str(Path(workdir).resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    with _trust_lock(path.parent):
        existed = path.exists()
        unterminated = existed and path.stat().st_size and not path.read_bytes().endswith(b"\n")
        with open(str(path), "a", encoding="utf-8") as handle:
            handle.write(("\n" if unterminated else "") + root + "\n")
    try:
        yield root
    finally:
        with _trust_lock(path.parent):
            try:
                lines = path.read_text(encoding="utf-8").splitlines(True)
            except OSError:
                lines = []
            kept = [line for line in lines if line.strip() != root]
            if not existed and not "".join(kept).strip():
                with contextlib.suppress(OSError):
                    path.unlink()
            elif len(kept) != len(lines):
                atomic_write(path, "".join(kept).encode("utf-8"))


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args), env=scrubbed_env(),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)


def snapshot(repo, sha, dest):
    """The repository rewound to `sha`, with real history and no way forward to the fix.

    A tree with no history is not the repository an agent is asked to work in: this project's own
    gate reads its git history, so an archive of the files alone fails the gate before the agent has
    touched anything, and both arms then spend turns proving the failure was already there. The
    clone keeps every ancestor and the tags among them, and drops every ref ahead of `sha` before
    pruning, so the commit that solved the task is not reachable and not present."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wanted = _git(repo, "rev-parse", "--verify", "%s^{commit}" % sha).stdout.strip()
    env = scrubbed_env()
    subprocess.run(["git", "clone", "--quiet", "--local", "--no-hardlinks", "--no-checkout",
                    str(repo), str(dest)], check=True, env=env)
    _git(dest, "checkout", "--quiet", "-B", SNAPSHOT_BRANCH, sha)
    for ref in _git(dest, "for-each-ref", "--format=%(refname)").stdout.split():
        ancestor = ref.startswith("refs/tags/") and not _git(dest, "merge-base", "--is-ancestor",
                                                             ref, "HEAD").returncode
        if ref != "refs/heads/" + SNAPSHOT_BRANCH and not ancestor:
            _git(dest, "update-ref", "-d", ref)
    _git(dest, "remote", "remove", "origin")
    _git(dest, "reflog", "expire", "--expire=now", "--all")
    _git(dest, "gc", "--quiet", "--prune=now")
    if _git(dest, "rev-parse", "--verify", "--quiet", "HEAD").stdout.strip() != wanted:
        raise RuntimeError("snapshot of %s did not land on that commit" % sha)
    return dest


def reaches(repo, sha):
    """Whether `sha` is present in the snapshot at all: the guard that the fix stayed hidden."""
    return _git(repo, "cat-file", "-e", sha).returncode == 0


def resolve_tag(repo, ref):
    """The commit a `--tag` names in this repository, as a full sha.

    A ref that does not resolve is a named error rather than a skipped tag: a run asked for two
    tags and given one row, with nothing in the file saying which one is missing, reads as a
    result. Every ref is resolved before the first launch, so a typo costs nothing."""
    done = _git(repo, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref)
    sha = done.stdout.strip()
    if done.returncode or len(sha) != 40:
        raise SystemExit("cost-bench: --tag %s does not name a commit in %s" % (ref, repo))
    return sha


def refuse_live_config(config_dir, base=None, bare=None):
    """SystemExit when a sync target is, holds or sits inside a profile a tag must not write.

    The tagged arm's whole point is a profile nobody else wrote, and `harness sync` rewrites
    whatever `CLAUDE_CONFIG_DIR` names. Refused: the live profile in both spellings (the default
    under HOME, and an ambient `CLAUDE_CONFIG_DIR` if this process carries one), any directory
    inside one, any directory holding one (HOME itself, and every ancestor), and the bare arm's
    profile, which a sync would turn into a second harness arm."""
    base = os.environ if base is None else base
    target = Path(config_dir).expanduser().resolve()
    live = [Path(base.get("HOME") or Path.home()).expanduser() / ".claude"]
    if base.get("CLAUDE_CONFIG_DIR"):
        live.append(Path(base["CLAUDE_CONFIG_DIR"]).expanduser())
    for path in (p.resolve() for p in live):
        if target == path or path in target.parents:
            raise SystemExit("cost-bench: refusing to sync a tag into %s: that is the live profile"
                             % config_dir)
        if target in path.parents:
            raise SystemExit("cost-bench: refusing to sync a tag into %s: it holds the live profile %s"
                             % (config_dir, path))
    if bare and Path(bare).expanduser().resolve() == target:
        raise SystemExit("cost-bench: refusing to sync a tag into %s: that is the bare profile"
                         % config_dir)


# Paths a harness sync leaves in a profile as regular files, beside the links it makes.
HARNESS_FILES = ("CLAUDE.md", "CLAUDE.personal.md", "rules/harness-stances", "skills/harness-*")
# Every top-level name `bin/harness sync` writes under the config directory: the files it
# generates or merges, and the directories it fills with links. A link at one of these is the
# harness's whatever it leads to; one that leads outside the profile would have the sync write
# through it, outside anything the undo can see.
HARNESS_NAMES = ("CLAUDE.md", "CLAUDE.personal.md", "agents", "commands", "hooks", "output-styles",
                 "plans", "rules", "settings.json", "skills")
# The one file a sync rewrites in place when the profile already holds it. Everything else it
# writes is new, or is at a path `harness_residue` refuses beforehand.
SYNC_MERGES = ("settings.json",)
# What the CLI keeps a sign-in in. Never copied, written, or deleted here, whatever wrote it and
# whenever it appeared: a profile that loses one is signed out.
CREDENTIAL_NAMES = (".credentials.json", ".claude.json")
# Where a sync records what it wrote, under the HOME it ran with. This is where the harness at
# HEAD writes; an older tag's sync may record elsewhere, and `undo_sync` checks the profile
# afterwards rather than trusting the record.
SYNC_STATE = Path(".local") / "state" / "agent-harness"
# What the CLI and the owner's other sessions write into a profile during a run, left alone by
# the undo and not counted as the sync's when the profile is checked afterwards. `skills/synced`
# is the CLI's own skill packs, which it writes under a harness-managed name.
RUN_WRITES = ("projects", "todos", "plans", "history.jsonl", "skills/synced")


def is_credential(rel):
    name = Path(rel).name
    return name in CREDENTIAL_NAMES or name.startswith(CREDENTIAL_NAMES) or "credential" in name.lower()


def leads_into_harness(link):
    """Whether a symlink resolves to somewhere under a checkout holding `bin/harness`."""
    try:
        target = Path(link).resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return any((parent / "bin" / "harness").is_file() for parent in [target] + list(target.parents))


def harness_residue(config_dir):
    """What in `config_dir` a harness sync put there, as relative paths; empty for a clean profile.

    A pinned tag is synced into a profile holding none of it, for two reasons. The sync runs with a
    HOME of its own and so with an empty manifest, and a sync that finds links it did not record
    calls them unmanaged and stops with the profile half rewritten. And a profile already carrying
    another version's layer would mix it into the arm and label the result with the tag.

    A link counts only when it leads into a harness checkout or sits at a name the harness
    manifest manages; the CLI writes links of its own (`debug/latest`) into a profile it merely
    signed into, and those are not residue."""
    root = Path(config_dir).expanduser()
    found = []
    for rel, kind in profile_entries(root).items():
        if kind != "link":
            continue
        top = rel.split("/", 1)[0]
        if top in HARNESS_NAMES or Path(rel).name in HARNESS_NAMES or leads_into_harness(root / rel):
            found.append(rel)
    for pattern in HARNESS_FILES:
        found += sorted(p.relative_to(root).as_posix() for p in root.glob(pattern))
    settings = root / "settings.json"
    if settings.is_file() and "hooks/harness" in settings.read_text(encoding="utf-8", errors="replace"):
        found.append("settings.json")
    return sorted(set(found))


def escapes_profile(config_dir):
    """Names in HARNESS_NAMES the sync would write through to somewhere outside the profile: any
    that is a symlink, or whose resolved path is not under the profile's."""
    root = Path(config_dir).expanduser()
    try:
        inside = root.resolve()
    except OSError:
        inside = root
    out = []
    for name in HARNESS_NAMES:
        path = root / name
        if path.is_symlink():
            out.append(name)
            continue
        if not path.exists():
            continue
        try:
            real = path.resolve()
        except (OSError, RuntimeError):
            out.append(name)
            continue
        if real != inside / name and inside not in real.parents:
            out.append(name)
    return out


def check_sync_target(config_dir, bare=None, base=None):
    """Every refusal a named sync target can meet, run before anything is launched or spent."""
    refuse_live_config(config_dir, base, bare)
    escaping = escapes_profile(config_dir)
    if escaping:
        raise SystemExit("cost-bench: refusing to sync a tag into %s: %s would take the sync's writes "
                         "outside the profile, where nothing could undo them"
                         % (config_dir, ", ".join(escaping)))
    residue = harness_residue(config_dir)
    if residue:
        raise SystemExit("cost-bench: refusing to sync a tag into %s: it already holds harness files "
                         "(%s); a pinned tag needs a signed-in profile with none"
                         % (config_dir, ", ".join(residue[:5])))


def profile_entries(root):
    """`{relative path: "dir" | "file" | "link" | "other"}` for everything under `root`, no link
    followed and nothing opened; a socket or a FIFO is `other`."""
    root, out = Path(root), {}
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            try:
                mode = os.lstat(str(path)).st_mode
            except OSError:
                continue
            out[path.relative_to(root).as_posix()] = ("link" if stat.S_ISLNK(mode) else "dir"
                                                      if stat.S_ISDIR(mode) else "file"
                                                      if stat.S_ISREG(mode) else "other")
    return out


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile_listing(root):
    """`{relative path: (kind, detail)}`: a link's target, a regular file's size and mtime, the
    sha256 as well for the files a sync merges in place, nothing for a directory or anything
    else. Only a SYNC_MERGES file is ever opened, so a FIFO cannot hang this, nothing else in the
    profile is read, and an unreadable entry is listed as `(kind, None)` rather than stopping
    the walk."""
    root, out = Path(root), {}
    for rel, kind in profile_entries(root).items():
        path = root / rel
        try:
            if kind == "link":
                out[rel] = (kind, os.readlink(str(path)))
            elif kind == "file" and rel in SYNC_MERGES:
                out[rel] = (kind, (path.stat().st_size, _digest(path)))
            elif kind == "file":
                info = path.stat()
                out[rel] = (kind, (info.st_size, info.st_mtime_ns))
            else:
                out[rel] = (kind, None)
        except OSError:
            out[rel] = (kind, None)
    return out


def _run_write(rel):
    """A credential, one of RUN_WRITES, anything under one, or a directory that only exists to
    hold one (`skills` above `skills/synced`): the run's, never the sync's."""
    roots = tuple(n + "/" for n in RUN_WRITES)
    return (is_credential(rel) or rel in RUN_WRITES or rel.startswith(roots)
            or any(root.startswith(rel + "/") for root in roots))


def sync_leftovers(config, before):
    """Relative paths in `config` the sync could have written that are not as they were before
    it: an entry under a HARNESS_NAMES name that is new or changed, or a new link anywhere.
    Credentials and what a run writes for itself (RUN_WRITES) are never counted."""
    after = profile_listing(config)
    out = []
    for rel, entry in after.items():
        if _run_write(rel) or before.get(rel) == entry:
            continue
        if rel.split("/", 1)[0] in HARNESS_NAMES or entry[0] == "link":
            out.append(rel)
    return sorted(out)


def atomic_write(path, data):
    """Write `data` to `path` through a temp file in the same directory, fsync and rename, so a
    full disk or an interrupt leaves either the old bytes or the new ones and never a stump."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def copy_aside(config, dest, listing):
    """Copy the files a sync rewrites in place into `dest`; the relative paths copied.

    Only those files: a credential file is never copied, so nothing here can ever write one back.
    The copy is built under a temporary name and re-read afterwards, and it counts as a copy only
    when every byte matches; a copy that failed halfway is not one the restore may use."""
    config, dest = Path(config), Path(dest)
    partial = dest.with_name(dest.name + ".partial")
    partial.mkdir(parents=True)
    copied = [rel for rel in SYNC_MERGES if listing.get(rel, ("",))[0] == "file"
              and listing[rel][1] is not None and not is_credential(rel)]
    for rel in copied:
        (partial / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(config / rel), str(partial / rel))
    for rel in copied:
        if _digest(partial / rel) != listing[rel][1][1]:
            raise RuntimeError("the copy of %s does not match the original" % rel)
    partial.rename(dest)
    return copied


def sync_wrote(config, state):
    """Relative paths a sync recorded as its own, read from the state it left under its HOME:
    every link in its manifest, every file its ownership store generated or created, and the
    files at HARNESS_FILES paths it renders without recording. Only paths inside `config`."""
    config = Path(config)
    try:
        inside = config.resolve()
    except OSError:
        inside = config
    out = set()

    def add(path):
        path = Path(path)
        try:  # the parent resolved, the entry itself never followed: a link is the entry
            rel = (path.parent.resolve() / path.name).relative_to(inside)
        except (OSError, ValueError):
            return
        if not is_credential(rel):
            out.add(rel.as_posix())

    def read(name):
        try:
            return json.loads((Path(state) / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    for link in read("manifest.json").get("links", []) or []:
        if isinstance(link, dict) and link.get("path"):
            add(link["path"])
    for path, record in (read("ownership.json").get("files", {}) or {}).items():
        # A merged file is the sync's too: it is never deleted (it was there before), but it
        # counts as recorded, so a merge-only sync does not read as one that recorded nothing.
        if isinstance(record, dict) and (record.get("kind") in ("generated", "json") or record.get("created")):
            add(path)
    for pattern in HARNESS_FILES:
        for path in config.glob(pattern):
            add(path)
            if path.is_dir() and not path.is_symlink():
                for child in path.rglob("*"):
                    add(child)
    return out


def undo_sync(config, before, saved, copied, state):
    """Take back exactly what a sync wrote into `config`, and nothing else.

    `before` is `profile_listing` of `config` from before the sync, `saved` the directory
    `copy_aside` built, `copied` what it holds, and `state` the sync's own state directory,
    from which `sync_wrote` reads what it made. Only those paths are removed: what the run's own
    sessions or anyone else's wrote into the profile meanwhile, a transcript or a credential
    created for the first time, is not the sync's and stays. A directory the sync created goes
    only when it is empty. `settings.json`, which the sync merged into, is put back from its copy
    through an atomic write, and only when its bytes differ; a credential file is never written,
    so a token the CLI refreshed during the run stays refreshed."""
    config, saved = Path(config), Path(saved)
    wrote = sync_wrote(config, state)
    for rel in sorted(wrote, key=lambda r: -r.count("/")):
        path = config / rel
        if is_credential(rel) or rel in before and before[rel][0] != "dir":
            continue  # a pre-existing file is restored below or left alone, never deleted
        try:
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                path.unlink()
        except OSError:
            continue
    # Only a directory the sync's records lead through, or one of its own top-level write sites
    # (`plans` it makes and records nowhere), and only when it was not there before and holds
    # nothing now: a directory that merely appeared during the run is not the sync's.
    made = {name for name in HARNESS_NAMES if (config / name).is_dir() and not (config / name).is_symlink()}
    for rel in wrote:
        made.update(p.as_posix() for p in [Path(rel)] + list(Path(rel).parents) if p.as_posix() != ".")
    for rel in sorted(made - set(before), key=lambda r: -r.count("/")):
        try:
            (config / rel).rmdir()  # refuses anything still holding a file: never rmtree
        except OSError:
            pass
    for rel in copied:
        if rel not in before or before[rel][0] != "file" or is_credential(rel):
            continue
        data = (saved / rel).read_bytes()
        target = config / rel
        if target.is_symlink() or target.is_dir():
            raise RuntimeError("%s is no longer a file; its copy is kept" % rel)
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, data)
    # The records are read from where the harness at HEAD writes them; an older tag's sync may
    # record elsewhere, and then nothing above removed anything. The profile itself is the check:
    # what the sync could have written must be as it was, or the run stops here, before another
    # tag launches into a profile that would refuse it or, worse, run links into a deleted checkout.
    leftovers = sync_leftovers(config, before)
    if leftovers or not wrote:
        raise SystemExit("cost-bench: the sync could not be taken back out of %s: %s; the sync's "
                         "records %s"
                         % (config, ", ".join(leftovers[:8]) or "nothing left, but nothing recorded",
                            "were empty" if not wrote else "did not cover it"))


def sync_tag(repo, ref, parent, config_dir=None, python=sys.executable):
    """The harness as it stood at `ref`, projected into a profile of its own under `parent`.

    Returns `{parent, checkout, config, home, version, sha}`. The checkout keeps real history,
    because `harness sync` reads git state; the profile starts empty, so everything in it came
    from that checkout and nothing from the owner's.

    The sync subprocess is given a HOME of its own as well as an explicit `CLAUDE_CONFIG_DIR`.
    HOME alone decides `~/.config/agent-harness/config.json`, and a sync that inherited it would
    render the owner's identity and stance selection into the arm: the run would then measure a
    personal layer that is not the tag's, and two tags measured on different days would not be
    comparable. With no configuration to read the projection is the tag's defaults, which is the
    same question asked of every tag."""
    parent = Path(parent)
    sha = resolve_tag(repo, ref)
    config = Path(config_dir).expanduser() if config_dir else parent / "config"
    refuse_live_config(config)
    checkout = snapshot(repo, sha, parent / "checkout")
    home = parent / "home"
    home.mkdir(parents=True, exist_ok=True)
    config.mkdir(parents=True, exist_ok=True)
    env = scrubbed_env({"HOME": str(home), "CLAUDE_CONFIG_DIR": str(config)})
    done = subprocess.run([python, "bin/harness", "sync"], cwd=str(checkout), env=env,
                          timeout=SYNC_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    if done.returncode:
        tail = "\n".join((done.stdout or "").strip().splitlines()[-5:])
        raise SystemExit("cost-bench: `harness sync` failed for %s (exit %d)\n%s"
                         % (ref, done.returncode, tail))
    version = checkout / "VERSION"
    return {"parent": parent, "checkout": checkout, "config": config, "home": home, "sha": sha,
            "version": version.read_text(encoding="utf-8").strip() if version.is_file() else ref}


@contextlib.contextmanager
def synced_tag(repo, ref, tmp=None, config_dir=None, python=sys.executable, bare=None):
    """`sync_tag`, undone afterwards, exception or not.

    The temporary directories go. A named `config_dir` is a profile the owner keeps, so what the
    sync wrote into it is taken back once the tag's schedule is over (`undo_sync`), and the next
    tag, or the next invocation, finds it as this one did. If taking it back fails for any reason,
    an interrupt included, the copy of what was rewritten is kept and its path named."""
    parent = Path(tempfile.mkdtemp(prefix="cost-tag-", dir=tmp))
    config = saved = before = copied = None
    keep = False
    try:
        if config_dir:
            config = Path(config_dir).expanduser()
            check_sync_target(config, bare)
            before = profile_listing(config)
            copied = copy_aside(config, parent / "saved-profile", before)
            saved = parent / "saved-profile"  # only once the copy is whole
        yield sync_tag(repo, ref, parent, config_dir, python)
    finally:
        if saved is not None:
            try:
                undo_sync(config, before, saved, copied, parent / "home" / SYNC_STATE)
            except BaseException:
                keep = True
                print("cost-bench: could not take the sync back out of %s; the copy of what it "
                      "rewrote is kept at %s" % (config, saved), file=sys.stderr)
                raise
            finally:
                if not keep:
                    shutil.rmtree(str(parent), ignore_errors=True)
        else:
            shutil.rmtree(str(parent), ignore_errors=True)


def cli_messages(stdout):
    """(messages, streamed): the CLI's output as a list of messages. ValueError when none parse.

    The runner reads `stream-json`, one message per line. A raw file kept before that is one JSON
    document, the `json --verbose` array or a lone result, and still reads here, with `streamed`
    False so a field only the stream can carry stays unknown for it. A line that does not parse,
    such as the last one of a run cut off mid-write, is skipped rather than failing the run."""
    try:
        data = json.loads(stdout)
    except (TypeError, ValueError):
        data = None
    else:
        if isinstance(data, (list, dict)):
            return (data if isinstance(data, list) else [data]), False
    messages = []
    for line in (stdout or "").splitlines() if isinstance(stdout, str) else ():
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message, dict):
            messages.append(message)
    if not messages:
        raise ValueError("the CLI did not return JSON")
    return messages, True


def _hook_blocked(event):
    """Whether one `hook_response` event refused the stop: a `block` decision on stdout, or the
    exit code 2 that feeds stderr back to the model."""
    if event.get("exit_code") == 2:
        return True
    for key in ("stdout", "output"):
        try:
            decision = json.loads(str(event.get(key) or "").strip() or "null")
        except ValueError:
            continue
        if isinstance(decision, dict) and decision.get("decision") == "block":
            return True
    return False


def stop_hook_counts(messages, streamed):
    """(stop hook runs, of which blocked), or (None, None) for output that cannot carry them.

    Counted from the `hook_response` lifecycle events of the `Stop` hook only. Text in the
    transcript is not a substitute: the block reason also appears in the prompt and in files the
    agent reads."""
    if not streamed:
        return None, None
    stops = [m for m in messages if m.get("type") == "system" and m.get("subtype") == "hook_response"
             and m.get("hook_event") == "Stop"]
    return len(stops), sum(1 for m in stops if _hook_blocked(m))


def parse_result(stdout):
    """Cost, tokens, turns and the diagnostic fields, from the CLI's output. ValueError when there
    is no result to read.

    With `--verbose` the output is every message, which also gives each thread's first turn; without
    it the output is the result alone and the cache-normalised cost cannot be computed.

    `first_call_cache_write` is the standing prefix: the cache write of the first assistant message
    carrying a usage block, which is what the session paid to put its instruction layer in the
    cache, as against the run's total writes. `tool_counts` counts every `tool_use` content block
    by name, and `spawns` is the subagent share of it.

    `stop_hooks` and `hook_blocks` are how often the Stop hook ran and how often it refused the
    stop. Hook lifecycle events carry them, and the CLI emits those only under
    `--include-hook-events`, which works only with `--output-format=stream-json`; for output kept
    in the older single-document form both are None, never zero. See `stop_hook_counts`."""
    messages, streamed = cli_messages(stdout)
    stops, blocks = stop_hook_counts(messages, streamed)
    results = [m for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    if not results or not isinstance(results[-1].get("total_cost_usd"), (int, float)):
        raise ValueError("the CLI returned no result with total_cost_usd")
    result = results[-1]
    per_model = [u for u in (result.get("modelUsage") or {}).values() if isinstance(u, dict)]
    if per_model:  # includes subagents, which the top-level usage block may not
        tokens = {kind: sum(int(u.get(key) or 0) for u in per_model)
                  for kind, key in zip(TOKEN_KINDS, MODEL_USAGE_KEYS)}
    else:
        tokens = {kind: int((result.get("usage") or {}).get(kind) or 0) for kind in TOKEN_KINDS}
    first_turns, seen, first_write, tools = [], set(), None, {}
    cache = {"cache_read": 0, "cache_write": 0, "turns": 0, "known": True}
    for message in messages:
        if not isinstance(message, dict) or message.get("type") != "assistant":
            continue
        thread = message.get("parent_tool_use_id")
        body = message.get("message") or {}
        for block in body.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = str(block.get("name") or "")
                tools[name] = tools.get(name, 0) + 1
        if not isinstance(body.get("usage"), dict):
            continue
        if first_write is None:
            first_write = int(body["usage"].get("cache_creation_input_tokens") or 0)
        for field, key in (("cache_read", "cache_read_input_tokens"),
                           ("cache_write", "cache_creation_input_tokens")):
            if key not in body["usage"]:
                cache["known"] = False  # one silent turn and the run's total is not its spend
            cache[field] += int(body["usage"].get(key) or 0)
        cache["turns"] += 1
        if thread in seen:
            continue
        seen.add(thread)
        first_turns.append({"model": body.get("model") or "",
                            "cache_read": int(body["usage"].get("cache_read_input_tokens") or 0)})
    return {"cost_usd": float(result["total_cost_usd"]), "tokens": tokens,
            "turns": int(result.get("num_turns") or 0), "is_error": bool(result.get("is_error")),
            "subtype": str(result.get("subtype") or ""), "first_turns": first_turns,
            "first_call_cache_write": first_write, "tool_counts": tools,
            "spawns": sum(tools.get(name, 0) for name in SPAWN_TOOLS), "stop_hooks": stops,
            "hook_blocks": blocks,
            "cache_miss_ratio": run_miss_ratio(cache)}


def run_miss_ratio(cache):
    """The share of a run's prefix the provider re-wrote: `write / (read + write)`, or None.

    The ledger's figure, taken from `harness_core.cache_prefix` so the replay and
    `harness usage --by prefix` cannot drift apart. Unlike the ledger's, this one counts every
    thread the run opened, subagents included: a fan-out writes a fresh prefix, and here that is
    part of what the run cost rather than something to subtract.

    None when the CLI output carried no per-turn usage at all, when a turn's usage block omits
    either cache field, and when the turns it did carry report neither reads nor writes. Zero is
    a run that served its whole prefix from cache, and a run that cannot say must never be read
    as that one: a silent turn counted as two zeroes would be averaged in as a held prefix."""
    if not cache["turns"] or not cache["known"]:
        return None
    ratio = cache_prefix.miss_ratio(cache, "")
    return None if ratio is None else round(ratio, 4)


def _rates(prices, model):
    names = [name for name in prices if model == name or model.startswith(name + "-")]
    return prices[max(names, key=len)] if names else None


def normalised_cost(cost, first_turns, prices):
    """Reported cost with each thread's first-turn cache reads repriced as cache writes.

    Whether a run finds its prefix already cached depends on what ran before it, so run order moves
    the reported dollars. None when the first turns or a model's rates are unknown: never a guess."""
    if not first_turns:
        return None
    extra = 0.0
    for turn in first_turns:
        rates = _rates(prices, turn["model"])
        if not rates or "cache_write" not in rates or "cache_read" not in rates:
            return None
        extra += turn["cache_read"] * (rates["cache_write"] - rates["cache_read"]) / 1e6
    return round(cost + extra, 6)


def _oracle(repo, name):
    spec = importlib.util.spec_from_file_location("oracle_" + name, str(Path(repo) / ORACLES / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score(task, workdir, repo, python=sys.executable):
    """(passed, detail). The held-back check arrives only now, after the agent has finished."""
    workdir = Path(workdir)
    tests = task["tests"]
    if task["kind"] == "synthetic":
        errors = _oracle(repo, tests["oracle"]).check(workdir)
        return (not errors, "; ".join(errors[:3]))
    for name in tests["copy"]:
        blob = subprocess.run(["git", "-C", str(repo), "show", "%s:%s" % (task["good_sha"], name)],
                              check=True, stdout=subprocess.PIPE).stdout
        (workdir / name).parent.mkdir(parents=True, exist_ok=True)
        (workdir / name).write_bytes(blob)
    command = [python, "-m", "unittest", "discover", "-s", "tests", "-p", tests["pattern"]]
    for select in tests.get("select", []):
        command += ["-k", select]
    env = scrubbed_env({"PYTHONPATH": os.pathsep.join(str(workdir / p) for p in tests.get("pythonpath", []))})
    done = subprocess.run(command, cwd=str(workdir), env=env, timeout=CHECK_TIMEOUT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    ran = re.search(r"^Ran (\d+) tests? in", done.stdout, re.M)
    count = int(ran.group(1)) if ran else 0
    # Python 3.9 exits 0 when a filter matches nothing, so no tests run is a failure here.
    return (done.returncode == 0 and count > 0, "ran %d, exit %d" % (count, done.returncode))


def repo_gate(workdir, commands, python=sys.executable):
    """Exit codes for the repository's own gate, run in `workdir`. A benchmark fixture whose gate is
    already red charges both arms for failures the agent did not cause."""
    out = []
    for command in commands:
        done = subprocess.run([python if part == "python3" else part for part in command],
                              cwd=str(workdir), env=scrubbed_env({"PYTHONPATH": str(Path(workdir) / "lib")}),
                              timeout=CHECK_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)
        out.append((" ".join(command), done.returncode))
    return out


def verify_tasks(tasks, repo, parent, gate=None):
    """Errors for every task whose fixture or check does not hold before the agent runs."""
    errors = []
    for task in tasks:
        before = snapshot(repo, task["parent_sha"], Path(parent) / (task["id"] + "-parent"))
        if task["kind"] == "issue" and reaches(before, task["good_sha"]):
            errors.append("%s: the commit that solved it is present in the snapshot" % task["id"])
        for command, code in repo_gate(before, gate or []):
            if code:
                errors.append("%s: `%s` already fails in a clean snapshot (exit %d)"
                              % (task["id"], command, code))
        if score(task, before, repo)[0]:
            errors.append("%s: the check already passes at the parent sha" % task["id"])
        if task["kind"] == "issue":
            after = snapshot(repo, task["good_sha"], Path(parent) / (task["id"] + "-good"))
        else:
            after = before
            _oracle(repo, task["tests"]["oracle"]).solve(after)
        passed, detail = score(task, after, repo)
        if not passed:
            errors.append("%s: the check fails on the known-good tree (%s)" % (task["id"], detail))
    return errors


def schedule(tasks, reps):
    """Arms interleaved inside each task and rep, the leading arm alternating so neither always
    runs on the other's warm cache."""
    out = []
    for task in tasks:
        for rep in range(1, reps + 1):
            order = ARMS if rep % 2 else ARMS[::-1]
            out += [(task, rep, arm) for arm in order]
    return out


def run_one(task, rep, arm, opts, launch=subprocess.run):
    """One row. An errored run is `error: true` with `passed: null`; it is never a failure."""
    env = arm_env(arm, opts["bare_config"], opts.get("stance_cost"), harness_config=opts.get("harness_config"))
    config, admit = env.get("CLAUDE_CONFIG_DIR"), arm_admits(arm, opts)
    row = dict(opts["stamp"], task=task["id"], arm=arm, tag=opts["tag"], rep=rep, passed=None, error=False,
               error_kind="", cost_usd=None, cost_normalised_usd=None, turns=None, wall_seconds=None,
               first_call_cache_write=None, tool_counts={}, spawns=None, stop_hooks=None, hook_blocks=None,
               cache_miss_ratio=None,
               change_note=opts.get("change_note", ""), preflight=opts.get("preflight", "skipped"),
               arm_config_dir=config_label(config, opts.get("home")),
               arm_fingerprint=config_fingerprint(config, opts.get("home")),
               fingerprint_source="launch", profile_fingerprint=arm_profile(arm, env, opts),
               **{kind: None for kind in TOKEN_KINDS})
    workdir = Path(tempfile.mkdtemp(prefix="cost-replay-", dir=opts.get("tmp"))) / "repo"
    reason = unsafe_workdir(workdir, opts["home"])
    if reason:
        shutil.rmtree(str(workdir.parent), ignore_errors=True)
        raise SystemExit("cost-bench: refusing to run: " + reason)
    started = time.time()
    try:
        snapshot(opts["repo"], task["parent_sha"], workdir)
        try:
            with trusted_run(workdir, opts["home"]):
                done = launch(arm_command(opts["claude"], opts["model"], prompt_of(task), opts["run_cap"],
                                          config, admit, task["max_turns"]),
                              cwd=str(workdir), env=env,
                              timeout=RUN_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        except subprocess.TimeoutExpired:
            return dict(row, error=True, error_kind="timeout", wall_seconds=round(time.time() - started, 1))
        row["wall_seconds"] = round(time.time() - started, 1)
        if opts.get("raw"):
            Path(opts["raw"]).mkdir(parents=True, exist_ok=True)
            (Path(opts["raw"]) / ("%s-%s-%d.json" % (task["id"], arm, rep))).write_text(done.stdout or "",
                                                                                     encoding="utf-8")
        try:
            parsed = parse_result(done.stdout)
        except ValueError as exc:
            return dict(row, error=True, error_kind="exit %s: %s" % (done.returncode, exc))
        row.update(parsed["tokens"], cost_usd=parsed["cost_usd"], turns=parsed["turns"],
                   cost_normalised_usd=normalised_cost(parsed["cost_usd"], parsed["first_turns"], opts["prices"]),
                   **{field: parsed[field] for field in STREAM_FIELDS})
        if parsed["is_error"] or done.returncode:
            # The other stream fields diagnose an errored run; a miss ratio only describes one
            # that finished, and an aborted run's turns are not the spend it would have had.
            return dict(row, error=True, cache_miss_ratio=None,
                        error_kind=parsed["subtype"] or "exit %s" % done.returncode)
        try:
            row["passed"] = bool(opts.get("scorer", score)(task, workdir, opts["repo"])[0])
        except Exception as exc:  # a check that cannot run says nothing about the agent's work
            return dict(row, error=True, error_kind="check: %s" % type(exc).__name__)
        return row
    finally:
        shutil.rmtree(str(workdir.parent), ignore_errors=True)  # removed, never reset


def gate_output(stdout):
    """Every tool result in a `-p` stream, joined: the gate's own output, not the model's relay."""
    try:
        messages = cli_messages(stdout)[0]
    except ValueError:
        return ""
    parts = []
    for ev in messages:
        content = ((ev.get("message") or {}).get("content") if isinstance(ev, dict) else None) or []
        for blk in content if isinstance(content, list) else []:
            if isinstance(blk, dict) and blk.get("type") == "tool_result":
                text = blk.get("content")
                parts.append(text if isinstance(text, str) else json.dumps(text))
    return "\n".join(parts)


def gate_passed(stdout):
    """Green means lint reported no findings and nothing was refused. A suite verdict in the
    output is ignored either way: it is not the bar, and on a bench profile it is red for reasons
    that are not the arm's."""
    out = gate_output(stdout)
    return "lint: 0 finding(s)" in out and PREFLIGHT_RED.search(out) is None


def reply_text(stdout):
    """The final text of a `-p` run: the `result` field of the CLI's last result message, or ""."""
    try:
        messages = cli_messages(stdout)[0]
    except ValueError:
        return ""
    texts = [m.get("result") for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    return str(texts[-1] or "").strip() if texts else ""


def preflight(tasks, opts, launch=subprocess.run):
    """([{arm, passed, reply, cost_usd}], spent). One gate run per arm before anything is scored.

    The fence and the profile are the arm's own, so this asks the question the scored runs depend
    on: can an agent in this arm make the repository's own gate pass at all? An arm that cannot
    spends its turns on that instead of on the task, and the comparison measures the runner rather
    than the harness. The reply is the gate's last line, so an arm passes when it ends in `OK`."""
    checks, spent = [], 0.0
    for arm in ARMS:
        env = arm_env(arm, opts["bare_config"], opts.get("stance_cost"),
                      harness_config=opts.get("harness_config"))
        config = env.get("CLAUDE_CONFIG_DIR")
        workdir = Path(tempfile.mkdtemp(prefix="cost-preflight-", dir=opts.get("tmp"))) / "repo"
        reason = unsafe_workdir(workdir, opts["home"])
        if reason:
            shutil.rmtree(str(workdir.parent), ignore_errors=True)
            raise SystemExit("cost-bench: refusing to run: " + reason)
        try:
            snapshot(opts["repo"], tasks[0]["parent_sha"], workdir)
            command = arm_command(opts["claude"], opts["model"], PREFLIGHT_PROMPT, PREFLIGHT_CAP_USD,
                                  config, arm_admits(arm, opts), PREFLIGHT_TURNS)
            try:
                done = launch(command, cwd=str(workdir), env=env, timeout=RUN_TIMEOUT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            except subprocess.TimeoutExpired:
                spent += PREFLIGHT_CAP_USD
                checks.append({"arm": arm, "passed": False, "reply": "timeout", "cost_usd": None})
                continue
            if opts.get("raw"):
                raw = Path(opts["raw"]); raw.mkdir(parents=True, exist_ok=True)
                (raw / ("preflight-%s.json" % arm)).write_text(done.stdout or "", encoding="utf-8")
            reply = reply_text(done.stdout)
            try:
                cost = parse_result(done.stdout)["cost_usd"]
            except ValueError:
                cost = None
            spent += PREFLIGHT_CAP_USD if cost is None else cost
            checks.append({"arm": arm, "passed": gate_passed(done.stdout), "reply": reply,
                           "cost_usd": cost})
        finally:
            shutil.rmtree(str(workdir.parent), ignore_errors=True)
    return checks, spent


def replay(tasks, opts, launch=subprocess.run, out=None):
    """(rows, stopped). Stops before a launch that could take reported spend past the cap; the
    per-run cap is soft, so a run with no readable cost is counted at the full run cap.

    A red pre-flight refuses the whole replay with exit 2 before any scored run launches, since
    spending on arms that cannot pass the gate buys a number nobody can read. Its own cost counts
    against the same cumulative cap."""
    rows, spent = [], 0.0
    if not opts.get("skip_preflight"):
        checks, spent = preflight(tasks, opts, launch)
        red = [c for c in checks if not c["passed"]]
        for check in red:
            print("cost-bench: the %s arm's gate is red under its own fence: %s"
                  % (check["arm"], check["reply"] or "no reply"), file=sys.stderr)
        if red:
            print("cost-bench: refusing the replay; no scored run launched", file=sys.stderr)
            raise SystemExit(2)
        opts = dict(opts, preflight="passed")
    for task, rep, arm in schedule(tasks, opts["reps"]):
        if spent + opts["run_cap"] > opts["spend_cap"]:
            return rows, True
        row = run_one(task, rep, arm, opts, launch)
        spent += opts["run_cap"] if row["cost_usd"] is None else row["cost_usd"]
        rows.append(row)
        if out:
            with open(str(out), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return rows, False


def _mean(values):
    return sum(values) / len(values) if values else None


def summarise(rows, field="cost_usd"):
    """Per arm: cost per passed task and passes, each the mean of reps. Errors are counted apart
    and sit in neither figure. A rep in which an arm passed nothing has no cost per passed task."""
    out = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        scored = [r for r in mine if not r["error"]]
        per_rep, passes = [], []
        for rep in sorted({r["rep"] for r in mine}):
            runs = [r for r in scored if r["rep"] == rep]
            won = sum(1 for r in runs if r["passed"])
            passes.append(won)
            costs = [r[field] for r in runs]
            per_rep.append(sum(costs) / won if won and None not in costs else None)
        out[arm] = {"runs": len(mine), "errors": len(mine) - len(scored), "passed": _mean(passes),
                    "cost_per_passed": None if None in per_rep or not per_rep else round(_mean(per_rep), 6)}
    return out


def per_task(rows, field="cost_usd"):
    """One cell per task: each arm's mean cost, the ratio between them, and each arm's spread.

    Spread is max over min priced cost in the cell, so a cell whose two reps differ by half is
    visible as 1.5 and the aggregate ratio above it is read with that in mind. None when the cell
    holds fewer than two priced runs, because one run has no spread to report."""
    out = {}
    for task in sorted({r.get("task") or "" for r in rows}):
        cell, reps = {}, set()
        for arm in ARMS:
            mine = [r for r in rows if (r.get("task") or "") == task and r["arm"] == arm]
            reps.update(r["rep"] for r in mine)
            costs = [r[field] for r in mine if not r["error"] and r.get(field) is not None]
            cell[arm] = round(_mean(costs), 6) if costs else None
            cell[arm + "_spread"] = round(max(costs) / min(costs), 4) if len(costs) > 1 and min(costs) else None
        ratio = round(cell["harness"] / cell["bare"], 4) if cell["bare"] and cell["harness"] is not None else None
        out[task] = dict(cell, ratio=ratio, n=len(reps))
    return out


def cache_miss(rows):
    """Per arm: the mean of the per-run miss ratios, over the runs that reported one.

    None rather than zero when no scored run in the arm reported a figure, matching the per-run
    rule. It sits beside the cache-normalised ratio because the two answer different halves of
    one question: the normalised cost says what the run would have cost with a cold prefix, and
    this says how much of its prefix it actually re-bought."""
    out = {}
    for arm in ARMS:
        known = [r["cache_miss_ratio"] for r in rows if r["arm"] == arm and not r["error"]
                 and r.get("cache_miss_ratio") is not None]
        out[arm] = round(_mean(known), 4) if known else None
    return out


def verdict(summary):
    """The publishable threshold, fixed before the run: at most 85% of bare per passed task, passing
    no fewer than bare minus one."""
    bare, harness = summary["bare"], summary["harness"]
    known = bare["cost_per_passed"] and harness["cost_per_passed"] is not None
    ratio = round(harness["cost_per_passed"] / bare["cost_per_passed"], 4) if known else None
    if None not in (bare["passed"], harness["passed"]) and harness["passed"] < bare["passed"] - 1:
        return ratio, "failed"  # passing too few fails whatever the dollars say
    if ratio is None:
        return None, "inconclusive"
    return ratio, "passed" if ratio <= THRESHOLD else "failed"


def history_row(rows, series):
    """One line for `history.jsonl`: a harness version against bare on the same day and model.

    It carries the per-task breakdown as well as the aggregate, because one task moving is the
    usual shape of a regression and the aggregate alone cannot tell that from a broad one."""
    first = rows[0]
    reported, normalised = summarise(rows), summarise(rows, "cost_normalised_usd")
    ratio, status = verdict(reported)
    return {"date": first["date"], "series": series, "bucket": first.get("bucket", ""),
            "predicted_ratio": first.get("predicted_ratio"),
            "harness_version": first["harness_version"],
            "harness_sha": first["harness_sha"], "tag": first["tag"], "model": first["model"],
            "cli_version": first["cli_version"], "reps": max(r["rep"] for r in rows), "runs": len(rows),
            "change_note": first.get("change_note", ""), "per_task": per_task(rows),
            "bare": reported["bare"], "harness": reported["harness"], "ratio": ratio,
            "ratio_cache_normalised": verdict(normalised)[0], "cache_miss": cache_miss(rows),
            "threshold": THRESHOLD, "status": status}


def upsert_history(path, row):
    """Append, replacing an earlier line for the same version, commit, day, series and bucket.

    The bucket is part of the key: a programme that changes one thing at a time measures several
    buckets at one sha on one day, and without it each row would overwrite the last."""
    path = Path(path)
    key = lambda r: (r["date"], r["series"], r["harness_version"], r["harness_sha"], r.get("bucket", ""))
    old = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if path.is_file() else []
    kept = [r for r in old if key(r) != key(row)] + [row]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in kept), encoding="utf-8")
    return kept


def render_history(rows):
    """The ledger as text: the aggregate table, and under each of its lines the per-task detail.

    The detail is indented plain text rather than more table rows, since a task line answers a
    different question from the columns above it and would need none of them."""
    usd = lambda v: "n/a" if v is None else "%.3f" % v
    lines = ["# Cost per passed task, harness against bare Claude Code", "",
             "Dollars are list-price equivalents reported by the CLI, not money charged. Compare ratios"
             " across days, never dollars. A new series means the task set or the model changed.", "",
             "| Date | Series | Bucket | Harness | Model | Bare USD per pass | Harness USD per pass |"
             " Ratio | Predicted | Cache-normalised ratio | Cache miss, bare | Cache miss, harness |"
             " Passed, bare | Passed, harness | Errors | Threshold %.2f |" % THRESHOLD,
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
             " --- | --- |"]
    for r in rows:
        miss = r.get("cache_miss") or {}
        lines.append("| %s | %s | %s | %s @ %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                     " %d | %s |" % (
            r["date"], r["series"], r.get("bucket") or "n/a", r["harness_version"], r["harness_sha"][:7],
            r["model"], usd(r["bare"]["cost_per_passed"]), usd(r["harness"]["cost_per_passed"]),
            usd(r["ratio"]), usd(r.get("predicted_ratio")), usd(r["ratio_cache_normalised"]),
            usd(miss.get("bare")), usd(miss.get("harness")),
            usd(r["bare"]["passed"]), usd(r["harness"]["passed"]),
            r["bare"]["errors"] + r["harness"]["errors"], r["status"]))
        if r.get("change_note"):
            lines.append("    note: %s" % r["change_note"])
        for task, cell in sorted((r.get("per_task") or {}).items()):
            lines.append("    %s: bare %s, harness %s, ratio %s, spread bare %s / harness %s, n %d"
                         % (task or "n/a", usd(cell.get("bare")), usd(cell.get("harness")),
                            usd(cell.get("ratio")), usd(cell.get("bare_spread")),
                            usd(cell.get("harness_spread")), cell.get("n") or 0))
    return "\n".join(lines) + "\n"


def installed_harness(home):
    """The checkout the user-level install links to: the harness the harness arm actually loads.
    None when the link does not lead to one, since a guessed commit would mislabel every row."""
    link = Path(home) / ".claude" / "CLAUDE.md"
    for parent in link.resolve().parents if link.exists() else ():
        if (parent / "bin" / "harness").is_file():
            return parent
    return None


def raw_path(raw_dir, row):
    """Where `--raw` kept the CLI output for one row: the runner's `<task>-<arm>-<rep>.json`."""
    return Path(raw_dir) / ("%s-%s-%s.json" % (row.get("task"), row.get("arm"), row.get("rep")))


def backfill_rows(rows, raw_dir, config_dir=None, home=None):
    """(enriched rows, missing raw files). The diagnostic fields, derived after the fact.

    The launch environment is gone by now, so the fingerprint is of the directory named on the
    command line and the row says `fingerprint_source: backfill`: it is the caller's claim about
    which profile ran, not something the run recorded. A row whose raw output is missing or
    unreadable keeps its stream fields empty rather than borrowing another row's."""
    fingerprint = config_fingerprint(config_dir, home)
    label = config_label(None if config_dir in (None, "", INHERITED) else config_dir, home)
    out, missing = [], []
    for row in rows:
        new = dict(row, arm_config_dir=label, arm_fingerprint=fingerprint, fingerprint_source="backfill")
        new.setdefault("change_note", "")
        path = raw_path(raw_dir, row)
        try:
            parsed = parse_result(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            missing.append(path.name)
            for field in STREAM_FIELDS:
                new[field] = {} if field == "tool_counts" else None
            out.append(new)
            continue
        new.update({field: parsed[field] for field in STREAM_FIELDS})
        if new.get("error"):
            new["cache_miss_ratio"] = None  # the same rule `run_one` applies to an errored run
        out.append(new)
    return out, missing


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def cmd_backfill(args):
    results = Path(args.results).expanduser() / RESULTS
    if not results.is_file():
        raise SystemExit("cost-bench: %s does not exist" % results)
    config = Path(args.config_dir).expanduser() if args.config_dir else None
    rows, missing = backfill_rows(read_jsonl(results), Path(args.raw).expanduser(), config)
    write_jsonl(results.parent / ENRICHED, rows)
    if args.in_place:
        write_jsonl(results, rows)
    for name in missing:
        print("cost-bench: no raw output for %s" % name, file=sys.stderr)
    print("enriched %d row(s), %d without raw output, into %s"
          % (len(rows), len(missing), results.parent / ENRICHED))
    return 1 if missing else 0


def _text(command, **kwargs):
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, universal_newlines=True,
                          **kwargs).stdout.strip()


def cmd_replay(args):
    tasks = load_tasks(args.tasks)
    if args.task:
        tasks = [t for t in tasks if t["id"] in args.task]
    if args.verify_tasks:
        parent = Path(tempfile.mkdtemp(prefix="cost-replay-verify-"))
        try:
            errors = verify_tasks(tasks, ROOT, parent, GATE_COMMANDS)
        finally:
            shutil.rmtree(str(parent), ignore_errors=True)
        for error in errors:
            print("cost-bench: " + error, file=sys.stderr)
        print("verified %d task(s), %d error(s)" % (len(tasks), len(errors)))
        return 1 if errors else 0
    tags = args.tag or [CANDIDATE]
    if not args.model:
        raise SystemExit("cost-bench: --model is required, and every arm gets the same one")
    home = Path.home()
    bare = Path(args.bare_config).expanduser()
    if not bare.is_dir():
        raise SystemExit("cost-bench: the bare profile %s does not exist; sign in to it once" % bare)
    for tag in tags:  # every ref resolves before the first launch: a typo costs nothing
        if tag != CANDIDATE:
            resolve_tag(ROOT, tag)
    harness_config = Path(args.harness_config).expanduser() if args.harness_config else None
    if harness_config and not harness_config.is_dir():
        raise SystemExit("cost-bench: the harness profile %s does not exist; sign in to it once, then "
                         "sync the harness into it" % harness_config)
    # Every refusal about the target itself, the refs and the install runs here, before the first
    # launch of any tag, so no tag's schedule is spent and then stranded by one the next tag
    # meets. The per-tag work (copy-aside, snapshot, sync) necessarily runs as each tag's turn
    # comes, and a failure there is that tag's.
    harness = None
    if CANDIDATE in tags:
        harness = Path(args.harness_repo).expanduser() if args.harness_repo else installed_harness(home)
        if harness is None:
            raise SystemExit("cost-bench: ~/.claude/CLAUDE.md does not lead to a harness checkout; name the "
                             "installed one with --harness-repo")
    if harness_config and any(tag != CANDIDATE for tag in tags):
        check_sync_target(harness_config, bare)
        if CANDIDATE in tags:
            raise SystemExit("cost-bench: --harness-config %s cannot serve candidate and a pinned tag "
                             "in one run: candidate needs the installed harness synced into it and a "
                             "pinned tag needs it clean; run candidate on its own" % harness_config)
    plan = schedule(tasks, args.reps)
    print("%d run(s) per tag, %d tag(s) (%s): %d task(s) x %s x %d rep(s), model %s, %g USD per run, "
          "stop at %g USD reported per tag"
          % (len(plan), len(tags), ", ".join(tags), len(tasks), " + ".join(ARMS), args.reps,
             args.model, args.run_cap, args.spend_cap))
    if args.dry_run:  # nothing is synced and nothing is spent
        for tag in tags:
            print("  tag %s" % tag)
            for task, rep, arm in plan:
                print("    %s rep %d %s" % (task["id"], rep, arm))
        return 0
    common = {"tasks": tasks, "plan": plan, "home": home, "bare": bare,
              "prices": json.loads((ROOT / "policy" / "prices.json").read_text(encoding="utf-8")).get("models", {}),
              "cli_version": _text([args.claude, "--version"], env=scrubbed_env()),
              "harness_config": harness_config, "harness": harness, "per_tag_out": len(tags) > 1}
    status = 0
    for tag in tags:
        if tag == CANDIDATE:
            status = max(status, replay_tag(tag, args, common))
            continue
        with synced_tag(ROOT, tag, args.tmp, args.harness_config, bare=bare) as synced:
            status = max(status, replay_tag(tag, args, common, synced))
    return status


def replay_tag(tag, args, common, synced=None):
    """One tag's whole schedule, its results file and its history row. 1 when it stopped early.

    `synced` is `sync_tag`'s record when the tag was pinned, and None for the candidate. A pinned
    tag is stamped from its own checkout rather than from the install, because `installed_harness`
    describes the harness that happens to be live and would label every pinned row with it."""
    tasks, home = common["tasks"], common["home"]
    if synced:
        version, sha = synced["version"], synced["sha"]
        harness_config, source = synced["config"], synced["checkout"]
        if not args.harness_config:
            # A credential is keyed on the profile's absolute path, so a directory made for this
            # run is not signed in. Said once, before the spend, rather than read off every row.
            print("cost-bench: tag %s is synced into a temporary profile, which is not signed in; "
                  "name a signed-in --harness-config to sync into instead" % tag, file=sys.stderr)
    else:
        harness = common["harness"]
        version = (harness / "VERSION").read_text(encoding="utf-8").strip()
        sha = _text(["git", "-C", str(harness), "rev-parse", "HEAD"])
        harness_config, source = common["harness_config"], None
    # The arm profile is part of what is being compared, so it rotates the series: a run whose
    # harness arm carries the owner's personal layer is not comparable to one whose arm does not.
    profile = b"|isolated" if harness_config else b"|inherited"
    series = hashlib.sha256(Path(args.tasks).read_bytes() + args.model.encode()
                            + profile).hexdigest()[:8]
    out = Path(args.out) if args.out else ROOT / "benchmarks" / version
    # A pinned tag always gets a directory of its own: it may share a VERSION with the install, and
    # its rows would then append to the candidate's. So does every tag of a multi-tag run.
    if synced or common["per_tag_out"]:
        out = out / tag
    opts = {"repo": ROOT, "home": home, "claude": args.claude, "model": args.model, "tag": tag,
            "reps": args.reps, "run_cap": args.run_cap, "spend_cap": args.spend_cap,
            "prices": common["prices"], "bare_config": common["bare"],
            "harness_config": harness_config, "harness_source": source,
            "profile_root": source or common["harness"], "stance_cost": args.stance_cost,
            "raw": args.raw, "tmp": args.tmp, "change_note": args.change_note or "",
            "skip_preflight": args.skip_preflight,
            "stamp": {"date": datetime.date.today().isoformat(), "model": args.model,
                      "cli_version": common["cli_version"],
                      "bucket": args.bucket, "predicted_ratio": args.predicted_ratio,
                      "harness_version": version, "harness_sha": sha,
                      "os": "%s %s" % (platform.system(), platform.release())}}
    out.mkdir(parents=True, exist_ok=True)
    rows, stopped = replay(tasks, opts, out=out / RESULTS)
    if stopped:
        print("cost-bench: tag %s stopped at the spend cap after %d of %d run(s)"
              % (tag, len(rows), len(common["plan"])), file=sys.stderr)
    if rows and len(tasks) == len(load_tasks(args.tasks)) and not stopped:
        home_dir = Path(args.history_dir) if args.history_dir else ROOT / "benchmarks"
        home_dir.mkdir(parents=True, exist_ok=True)
        kept = upsert_history(home_dir / HISTORY.name, history_row(rows, series))
        (home_dir / HISTORY_MD.name).write_text(render_history(kept), encoding="utf-8")
        print(json.dumps(kept[-1], indent=2))
    else:
        print("cost-bench: a partial set is not a history row; results are in %s" % out, file=sys.stderr)
    return 1 if stopped else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    static = sub.add_parser("static", help="count the always-loaded layer and the session listings")
    mode = static.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="refresh %s" % STATIC.as_posix())
    mode.add_argument("--check", action="store_true", help="fail on unexplained growth")
    run = sub.add_parser("replay", help="run the pinned tasks against bare and harness; spends usage")
    run.add_argument("--tasks", default=str(ROOT / TASKS))
    run.add_argument("--task", action="append", help="run only this task id; repeatable")
    run.add_argument("--tag", action="append", help="harness version to run; repeatable; default "
                     "candidate, the installed harness as it stands. Any other value is a git ref "
                     "of this repository, synced into a config directory of its own and torn down "
                     "after that tag's schedule; each tag writes its own history row")
    run.add_argument("--model", help="the one model id every arm runs")
    run.add_argument("--reps", type=int, default=2)
    run.add_argument("--run-cap", type=float, default=RUN_CAP_USD, help="--max-budget-usd per run; soft")
    run.add_argument("--spend-cap", type=float, default=SPEND_CAP_USD, help="stop before passing "
                     "this; it applies to each tag's schedule on its own")
    run.add_argument("--stance-cost", help="HARNESS_STANCE_COST for the harness arm")
    run.add_argument("--bare-config", default="~/.claude-bench-bare", help="the signed-in empty profile")
    run.add_argument("--harness-config", help="the signed-in profile the harness is synced into; "
                     "without it the harness arm inherits ~/.claude and the owner's personal layer. "
                     "With --tag it is the directory each tag is synced into, which is what makes a "
                     "pinned run authenticated: a credential is keyed on a profile's absolute path")
    run.add_argument("--bucket", default="", help="the one change this run measures, e.g. A; names the "
                     "history row so several buckets can share a day and a commit")
    run.add_argument("--predicted-ratio", type=float, help="the ratio the plan predicts for this bucket; "
                     "stored beside the measured one so a miss is visible in the file")
    run.add_argument("--history-dir", help="directory for history.jsonl and history.md; "
                     "default benchmarks/")
    run.add_argument("--change-note", default="", help="what changed since the last run of this "
                     "bucket; stored on every row and on the history row")
    run.add_argument("--claude", default="claude", help="the CLI to launch")
    run.add_argument("--harness-repo", help="the installed harness checkout; default: follow ~/.claude")
    run.add_argument("--out", help="results directory; default benchmarks/<harness version>")
    run.add_argument("--raw", help="keep each run's raw CLI output here; never commit it")
    run.add_argument("--tmp", help="parent for the throwaway clones; must be outside the home directory")
    run.add_argument("--verify-tasks", action="store_true", help="prove every check; calls no model")
    run.add_argument("--skip-preflight", action="store_true", help="do not run each arm's gate under "
                     "its own fence first; rows then say preflight: skipped")
    run.add_argument("--dry-run", action="store_true", help="print the schedule and stop")
    back = sub.add_parser("backfill", help="derive the diagnostic fields for rows already written")
    back.add_argument("--results", required=True, help="directory holding %s" % RESULTS)
    back.add_argument("--raw", required=True, help="directory of the runs' raw CLI output")
    where = back.add_mutually_exclusive_group()
    where.add_argument("--config-dir", help="the profile those runs used; its files are measured now")
    where.add_argument("--inherited", action="store_true", help="those runs inherited ~/.claude (default)")
    back.add_argument("--in-place", action="store_true", help="also rewrite %s" % RESULTS)
    args = parser.parse_args(argv)
    if args.command == "replay":
        return cmd_replay(args)
    if args.command == "backfill":
        return cmd_backfill(args)
    if args.check:
        errors = check(ROOT)
        for error in errors:
            print("cost-bench: " + error, file=sys.stderr)
        return 1 if errors else 0
    text = json.dumps(measure(ROOT), indent=2) + "\n"
    if args.write:
        (ROOT / STATIC).parent.mkdir(exist_ok=True)
        (ROOT / STATIC).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
