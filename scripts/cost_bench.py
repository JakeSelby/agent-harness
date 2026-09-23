#!/usr/bin/env python3
"""Measure what the harness costs against Claude Code with no harness at all.

`static` counts, without calling a model, what the harness adds to every session. A bare session
loads none of the files counted, so the total is the harness's standing overhead. Tokens are an
estimate from characters (`CHARS_PER_TOKEN`), good for a trend between versions and not for
billing; dollars come from `policy/prices.json`. Codex is not counted: its instructions are
rendered at sync time.

`replay` runs pinned tasks headlessly against a bare profile and against the installed harness,
reads cost from the CLI's own JSON result and scores each run with a held-back check. It calls a
model and spends real usage. Reading and limits for both: docs/benchmarks.md.
"""
import argparse
import datetime
import hashlib
import importlib.util
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
from harness_core import cache_prefix  # noqa: E402  the ledger's miss ratio, one definition

CHARS_PER_TOKEN = 4.0
GROWTH_LIMIT = 0.05
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
KEPT_ENV = ("HOME", "USER", "PATH", "TERM")
TOKEN_KINDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens")
# Every arm is fenced the same way: no network, no credential reads. What differs is the profile
# the fence admits, which is the arm's own; see `fence`.
DENY_READ = ["~/.ssh", "~/.aws", "~/.config/gh"]
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
STREAM_FIELDS = ("first_call_cache_write", "tool_counts", "spawns", "hook_blocks",
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


def fence(config_dir=None):
    """The sandbox one arm runs under: no network, no credential reads, its own profile writable.

    A fence that admits only the CLI's default `~/.claude` handicaps whichever arm was moved to a
    bench profile, because this repository's own suite writes under the config directory and under
    `/tmp`; the arm then fails its gate and spends turns on a block the runner imposed. Each arm
    therefore gets its own directory, and the shared scratch directory, readable and writable.
    `denyRead` is the same for every arm."""
    admitted = [str(config_dir) if config_dir else DEFAULT_CONFIG_DIR] + list(SCRATCH_DIRS)
    return {"sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
                        "network": {"allowedDomains": [], "strictAllowlist": True},
                        "filesystem": {"denyRead": list(DENY_READ), "allowWrite": list(admitted),
                                       "allowRead": list(admitted)}}}


def arm_command(claude, model, prompt, run_cap=RUN_CAP_USD, config_dir=None):
    """One command line for every arm: the arms differ by environment and by their fence's
    profile, which follows that environment, and by nothing else."""
    return [claude, "-p", prompt, "--model", model, "--output-format", "json", "--verbose",
            "--strict-mcp-config", "--no-session-persistence", "--max-budget-usd", "%g" % run_cap,
            "--permission-mode", "acceptEdits", "--settings", json.dumps(fence(config_dir))]


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


def parse_result(stdout):
    """Cost, tokens, turns and the diagnostic fields, from the CLI's JSON. ValueError when there is
    no result to read.

    With `--verbose` the output is every message, which also gives each thread's first turn; without
    it the output is the result alone and the cache-normalised cost cannot be computed.

    `first_call_cache_write` is the standing prefix: the cache write of the first assistant message
    carrying a usage block, which is what the session paid to put its instruction layer in the
    cache, as against the run's total writes. `tool_counts` counts every `tool_use` content block
    by name, and `spawns` is the subagent share of it.

    `hook_blocks` is always None. Hook lifecycle events are the only place a Stop hook's `block`
    decision appears in the stream, and this CLI emits them only under `--include-hook-events`,
    which its own help says "only works with --output-format=stream-json"; the runner reads
    `--output-format json`, so no run of it can carry a hook decision. Text in the transcript is
    not a substitute: the block reason also appears in the prompt and in files the agent reads."""
    try:
        data = json.loads(stdout)
    except (TypeError, ValueError):
        raise ValueError("the CLI did not return JSON")
    messages = data if isinstance(data, list) else [data]
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
    cache = {"cache_read": 0, "cache_write": 0, "turns": 0}
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
        cache["cache_read"] += int(body["usage"].get("cache_read_input_tokens") or 0)
        cache["cache_write"] += int(body["usage"].get("cache_creation_input_tokens") or 0)
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
            "spawns": sum(tools.get(name, 0) for name in SPAWN_TOOLS), "hook_blocks": None,
            "cache_miss_ratio": run_miss_ratio(cache)}


def run_miss_ratio(cache):
    """The share of a run's prefix the provider re-wrote: `write / (read + write)`, or None.

    The ledger's figure, taken from `harness_core.cache_prefix` so the replay and
    `harness usage --by prefix` cannot drift apart. Unlike the ledger's, this one counts every
    thread the run opened, subagents included: a fan-out writes a fresh prefix, and here that is
    part of what the run cost rather than something to subtract.

    None when the CLI output carried no per-turn usage at all, and when the turns it did carry
    report neither reads nor writes. Zero is a run that served its whole prefix from cache, and a
    run that cannot say must never be read as that one."""
    if not cache["turns"]:
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
    config = env.get("CLAUDE_CONFIG_DIR")
    row = dict(opts["stamp"], task=task["id"], arm=arm, tag=opts["tag"], rep=rep, passed=None, error=False,
               error_kind="", cost_usd=None, cost_normalised_usd=None, turns=None, wall_seconds=None,
               first_call_cache_write=None, tool_counts={}, spawns=None, hook_blocks=None,
               cache_miss_ratio=None,
               change_note=opts.get("change_note", ""), preflight=opts.get("preflight", "skipped"),
               arm_config_dir=config_label(config, opts.get("home")),
               arm_fingerprint=config_fingerprint(config, opts.get("home")),
               fingerprint_source="launch", **{kind: None for kind in TOKEN_KINDS})
    workdir = Path(tempfile.mkdtemp(prefix="cost-replay-", dir=opts.get("tmp"))) / "repo"
    reason = unsafe_workdir(workdir, opts["home"])
    if reason:
        shutil.rmtree(str(workdir.parent), ignore_errors=True)
        raise SystemExit("cost-bench: refusing to run: " + reason)
    started = time.time()
    try:
        snapshot(opts["repo"], task["parent_sha"], workdir)
        try:
            done = launch(arm_command(opts["claude"], opts["model"], prompt_of(task), opts["run_cap"], config),
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
            return dict(row, error=True, error_kind=parsed["subtype"] or "exit %s" % done.returncode)
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
        data = json.loads(stdout)
    except (TypeError, ValueError):
        return ""
    parts = []
    for ev in data if isinstance(data, list) else [data]:
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
        data = json.loads(stdout)
    except (TypeError, ValueError):
        return ""
    messages = data if isinstance(data, list) else [data]
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
                                  config) + ["--max-turns", str(PREFLIGHT_TURNS)]
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
                new.setdefault(field, {} if field == "tool_counts" else None)
            out.append(new)
            continue
        new.update({field: parsed[field] for field in STREAM_FIELDS})
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
    tags = args.tag or ["candidate"]
    if tags != ["candidate"]:
        raise SystemExit("cost-bench: only --tag candidate runs today; syncing an older tag into a "
                         "temporary config directory is unverified")
    if not args.model:
        raise SystemExit("cost-bench: --model is required, and every arm gets the same one")
    home = Path.home()
    bare = Path(args.bare_config).expanduser()
    if not bare.is_dir():
        raise SystemExit("cost-bench: the bare profile %s does not exist; sign in to it once" % bare)
    harness = Path(args.harness_repo).expanduser() if args.harness_repo else installed_harness(home)
    if harness is None:
        raise SystemExit("cost-bench: ~/.claude/CLAUDE.md does not lead to a harness checkout; name the "
                         "installed one with --harness-repo")
    version = (harness / "VERSION").read_text(encoding="utf-8").strip()
    table = json.loads((ROOT / "policy" / "prices.json").read_text(encoding="utf-8")).get("models", {})
    harness_config = Path(args.harness_config).expanduser() if args.harness_config else None
    if harness_config and not harness_config.is_dir():
        raise SystemExit("cost-bench: the harness profile %s does not exist; sign in to it once, then "
                         "sync the harness into it" % harness_config)
    # The arm profile is part of what is being compared, so it rotates the series: a run whose
    # harness arm carries the owner's personal layer is not comparable to one whose arm does not.
    profile = b"|isolated" if harness_config else b"|inherited"
    series = hashlib.sha256(Path(args.tasks).read_bytes() + args.model.encode()
                            + profile).hexdigest()[:8]
    out = Path(args.out) if args.out else ROOT / "benchmarks" / version
    opts = {"repo": ROOT, "home": home, "claude": args.claude, "model": args.model, "tag": tags[0],
            "reps": args.reps, "run_cap": args.run_cap, "spend_cap": args.spend_cap, "prices": table,
            "bare_config": bare, "harness_config": harness_config, "stance_cost": args.stance_cost,
            "raw": args.raw, "tmp": args.tmp, "change_note": args.change_note or "",
            "skip_preflight": args.skip_preflight,
            "stamp": {"date": datetime.date.today().isoformat(), "model": args.model,
                      "cli_version": _text([args.claude, "--version"], env=scrubbed_env()),
                      "bucket": args.bucket, "predicted_ratio": args.predicted_ratio,
                      "harness_version": version, "harness_sha": _text(["git", "-C", str(harness), "rev-parse", "HEAD"]),
                      "os": "%s %s" % (platform.system(), platform.release())}}
    plan = schedule(tasks, args.reps)
    print("%d run(s): %d task(s) x %s x %d rep(s), model %s, %g USD per run, stop at %g USD reported"
          % (len(plan), len(tasks), " + ".join(ARMS), args.reps, args.model, args.run_cap, args.spend_cap))
    if args.dry_run:
        for task, rep, arm in plan:
            print("  %s rep %d %s" % (task["id"], rep, arm))
        return 0
    out.mkdir(parents=True, exist_ok=True)
    rows, stopped = replay(tasks, opts, out=out / "results.jsonl")
    if stopped:
        print("cost-bench: stopped at the spend cap after %d of %d run(s)" % (len(rows), len(plan)), file=sys.stderr)
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
    run.add_argument("--tag", action="append", help="harness version to run; repeatable; default candidate")
    run.add_argument("--model", help="the one model id every arm runs")
    run.add_argument("--reps", type=int, default=2)
    run.add_argument("--run-cap", type=float, default=RUN_CAP_USD, help="--max-budget-usd per run; soft")
    run.add_argument("--spend-cap", type=float, default=SPEND_CAP_USD, help="stop before passing this")
    run.add_argument("--stance-cost", help="HARNESS_STANCE_COST for the harness arm")
    run.add_argument("--bare-config", default="~/.claude-bench-bare", help="the signed-in empty profile")
    run.add_argument("--harness-config", help="the signed-in profile the harness is synced into; "
                     "without it the harness arm inherits ~/.claude and the owner's personal layer")
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
