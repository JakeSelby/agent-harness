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
CHARS_PER_TOKEN = 4.0
GROWTH_LIMIT = 0.05
STATIC = Path("benchmarks") / "static.json"
ALLOW = Path("benchmarks") / "allow.json"
TASKS = Path("benchmarks") / "tasks.json"
ORACLES = Path("benchmarks") / "oracles"
HISTORY = Path("benchmarks") / "history.jsonl"
HISTORY_MD = Path("benchmarks") / "history.md"
ARMS = ("bare", "harness")
RUN_CAP_USD = 2.0
SPEND_CAP_USD = 25.0
THRESHOLD = 0.85
RUN_TIMEOUT = 1800
CHECK_TIMEOUT = 900
KEPT_ENV = ("HOME", "USER", "PATH", "TERM")
TOKEN_KINDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MODEL_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens")
# Both arms get this fence: commands run sandboxed with no network and no credential reads.
FENCE = {"sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
                     "network": {"allowedDomains": [], "strictAllowlist": True},
                     "filesystem": {"denyRead": ["~/.ssh", "~/.aws", "~/.config/gh"]}}}


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


def arm_env(arm, bare_config, stance_cost=None, base=None):
    extra = {"CLAUDE_CONFIG_DIR": str(bare_config)} if arm == "bare" else {}
    if stance_cost and arm != "bare":
        extra["HARNESS_STANCE_COST"] = stance_cost
    return scrubbed_env(extra, base)


def arm_command(claude, model, prompt, run_cap=RUN_CAP_USD):
    """One command line for every arm: the arms differ by environment and by nothing else."""
    return [claude, "-p", prompt, "--model", model, "--output-format", "json", "--verbose",
            "--strict-mcp-config", "--no-session-persistence", "--max-budget-usd", "%g" % run_cap,
            "--permission-mode", "acceptEdits", "--settings", json.dumps(FENCE)]


def snapshot(repo, sha, dest):
    """The tree at `sha` as a one-commit repository, so the commit that solved it is not reachable."""
    dest = Path(dest)
    dest.mkdir(parents=True)
    archive = subprocess.Popen(["git", "-C", str(repo), "archive", sha], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    if archive.wait():
        raise RuntimeError("git archive %s failed" % sha)
    env = scrubbed_env()
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=cost-bench", "-c", "user.email=cost-bench",
                  "commit", "-q", "-m", "chore: baseline"]):
        subprocess.run(["git", "-C", str(dest)] + args, check=True, env=env, stdout=subprocess.DEVNULL)
    return dest


def parse_result(stdout):
    """Cost, tokens and turns from the CLI's JSON. ValueError when there is no result to read.

    With `--verbose` the output is every message, which also gives each thread's first turn; without
    it the output is the result alone and the cache-normalised cost cannot be computed."""
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
    first_turns, seen = [], set()
    for message in messages:
        if not isinstance(message, dict) or message.get("type") != "assistant":
            continue
        thread = message.get("parent_tool_use_id")
        body = message.get("message") or {}
        if thread in seen or not isinstance(body.get("usage"), dict):
            continue
        seen.add(thread)
        first_turns.append({"model": body.get("model") or "",
                            "cache_read": int(body["usage"].get("cache_read_input_tokens") or 0)})
    return {"cost_usd": float(result["total_cost_usd"]), "tokens": tokens,
            "turns": int(result.get("num_turns") or 0), "is_error": bool(result.get("is_error")),
            "subtype": str(result.get("subtype") or ""), "first_turns": first_turns}


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


def verify_tasks(tasks, repo, parent):
    """Errors for every task whose check does not fail before the work and pass after it."""
    errors = []
    for task in tasks:
        before = snapshot(repo, task["parent_sha"], Path(parent) / (task["id"] + "-parent"))
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
    row = dict(opts["stamp"], task=task["id"], arm=arm, tag=opts["tag"], rep=rep, passed=None, error=False,
               error_kind="", cost_usd=None, cost_normalised_usd=None, turns=None, wall_seconds=None,
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
            done = launch(arm_command(opts["claude"], opts["model"], prompt_of(task), opts["run_cap"]),
                          cwd=str(workdir), env=arm_env(arm, opts["bare_config"], opts.get("stance_cost")),
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
                   cost_normalised_usd=normalised_cost(parsed["cost_usd"], parsed["first_turns"], opts["prices"]))
        if parsed["is_error"] or done.returncode:
            return dict(row, error=True, error_kind=parsed["subtype"] or "exit %s" % done.returncode)
        try:
            row["passed"] = bool(opts.get("scorer", score)(task, workdir, opts["repo"])[0])
        except Exception as exc:  # a check that cannot run says nothing about the agent's work
            return dict(row, error=True, error_kind="check: %s" % type(exc).__name__)
        return row
    finally:
        shutil.rmtree(str(workdir.parent), ignore_errors=True)  # removed, never reset


def replay(tasks, opts, launch=subprocess.run, out=None):
    """(rows, stopped). Stops before a launch that could take reported spend past the cap; the
    per-run cap is soft, so a run with no readable cost is counted at the full run cap."""
    rows, spent = [], 0.0
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
    """One line for `history.jsonl`: a harness version against bare on the same day and model."""
    first = rows[0]
    reported, normalised = summarise(rows), summarise(rows, "cost_normalised_usd")
    ratio, status = verdict(reported)
    return {"date": first["date"], "series": series, "harness_version": first["harness_version"],
            "harness_sha": first["harness_sha"], "tag": first["tag"], "model": first["model"],
            "cli_version": first["cli_version"], "reps": max(r["rep"] for r in rows), "runs": len(rows),
            "bare": reported["bare"], "harness": reported["harness"], "ratio": ratio,
            "ratio_cache_normalised": verdict(normalised)[0], "threshold": THRESHOLD, "status": status}


def upsert_history(path, row):
    """Append, replacing an earlier line for the same version, commit, day and series."""
    path = Path(path)
    key = lambda r: (r["date"], r["series"], r["harness_version"], r["harness_sha"])
    old = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if path.is_file() else []
    kept = [r for r in old if key(r) != key(row)] + [row]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in kept), encoding="utf-8")
    return kept


def render_history(rows):
    usd = lambda v: "n/a" if v is None else "%.3f" % v
    lines = ["# Cost per passed task, harness against bare Claude Code", "",
             "Dollars are list-price equivalents reported by the CLI, not money charged. Compare ratios"
             " across days, never dollars. A new series means the task set or the model changed.", "",
             "| Date | Series | Harness | Model | Bare USD per pass | Harness USD per pass | Ratio |"
             " Cache-normalised ratio | Passed, bare | Passed, harness | Errors | Threshold %.2f |" % THRESHOLD,
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| %s | %s | %s @ %s | %s | %s | %s | %s | %s | %s | %s | %d | %s |" % (
            r["date"], r["series"], r["harness_version"], r["harness_sha"][:7], r["model"],
            usd(r["bare"]["cost_per_passed"]), usd(r["harness"]["cost_per_passed"]), usd(r["ratio"]),
            usd(r["ratio_cache_normalised"]), usd(r["bare"]["passed"]), usd(r["harness"]["passed"]),
            r["bare"]["errors"] + r["harness"]["errors"], r["status"]))
    return "\n".join(lines) + "\n"


def installed_harness(home):
    """The checkout the user-level install links to: the harness the harness arm actually loads.
    None when the link does not lead to one, since a guessed commit would mislabel every row."""
    link = Path(home) / ".claude" / "CLAUDE.md"
    for parent in link.resolve().parents if link.exists() else ():
        if (parent / "bin" / "harness").is_file():
            return parent
    return None


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
            errors = verify_tasks(tasks, ROOT, parent)
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
    series = hashlib.sha256(Path(args.tasks).read_bytes() + args.model.encode()).hexdigest()[:8]
    out = Path(args.out) if args.out else ROOT / "benchmarks" / version
    opts = {"repo": ROOT, "home": home, "claude": args.claude, "model": args.model, "tag": tags[0],
            "reps": args.reps, "run_cap": args.run_cap, "spend_cap": args.spend_cap, "prices": table,
            "bare_config": bare, "stance_cost": args.stance_cost, "raw": args.raw, "tmp": args.tmp,
            "stamp": {"date": datetime.date.today().isoformat(), "model": args.model,
                      "cli_version": _text([args.claude, "--version"], env=scrubbed_env()),
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
        kept = upsert_history(ROOT / HISTORY, history_row(rows, series))
        (ROOT / HISTORY_MD).write_text(render_history(kept), encoding="utf-8")
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
    run.add_argument("--claude", default="claude", help="the CLI to launch")
    run.add_argument("--harness-repo", help="the installed harness checkout; default: follow ~/.claude")
    run.add_argument("--out", help="results directory; default benchmarks/<harness version>")
    run.add_argument("--raw", help="keep each run's raw CLI output here; never commit it")
    run.add_argument("--tmp", help="parent for the throwaway clones; must be outside the home directory")
    run.add_argument("--verify-tasks", action="store_true", help="prove every check; calls no model")
    run.add_argument("--dry-run", action="store_true", help="print the schedule and stop")
    args = parser.parse_args(argv)
    if args.command == "replay":
        return cmd_replay(args)
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
