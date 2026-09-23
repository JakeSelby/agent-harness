#!/usr/bin/env python3
"""Run the deterministic pre-qualification checks as one tier: no model turn, no client, no cost.

Every check here already exists in this repository; the tier is the single command that runs
them before a qualification round is paid for — the acceptance runner's self-tests against
recorded transcripts, the documentation-link check, the credential-reachability probe, and the
disposable-home sync, projection-drift and lifecycle checks.

A green tier is never native client qualification. It observes no client behaviour, writes
nothing under `compatibility/evidence/` and appears in no catalog record; the run fails if
either of those is touched. What a client must be observed doing, and what evidence must
contain, is in docs/compatibility.md.

    python3 scripts/smoke_tier.py --list
    python3 scripts/smoke_tier.py
    python3 scripts/smoke_tier.py --only credentials,documentation-links
"""
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_acceptance import redact

NOT_QUALIFICATION = ("smoke tier: deterministic pre-qualification checks, no model turn; "
                     "a green run is not native client qualification")
# What no check may touch: an evidence record is a claim about an observed client, and this tier
# observes none.
GUARDED = (Path("compatibility") / "evidence", Path("compatibility") / "catalog.json")
TAIL = 600


def unittest_argv(pattern):
    return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern]


def steps(work):
    """Each check, in the order a failing one is cheapest to read: fastest and narrowest first."""
    return [
        {"name": "credentials",
         "how": "name the credential a client launched under this environment would use",
         "argv": [sys.executable, "-m", "harness_core.credentials"],
         "env": {"PYTHONPATH": str(ROOT / "lib")}, "timeout": 15},
        {"name": "projection-drift",
         "how": "regenerate every native projection and compare it with the committed one",
         "argv": [sys.executable, str(ROOT / "bin" / "harness"), "generate", "--check"],
         "timeout": 120},
        {"name": "documentation-links",
         "how": "resolve every relative documentation link and heading anchor",
         "argv": unittest_argv("test_doc_links.py"), "timeout": 120},
        {"name": "runner-self-tests",
         "how": "read recorded transcripts with the acceptance runner's own readers",
         "argv": unittest_argv("test_native_acceptance*.py"), "timeout": 600},
        {"name": "disposable-home-lifecycle",
         "how": "install, sync, upgrade, roll back and uninstall in disposable homes",
         "argv": [sys.executable, str(ROOT / "scripts" / "lifecycle_acceptance.py"),
                  "--output", str(work / "lifecycle.json")],
         "timeout": 1800, "clean_tree": True},
    ]


def dirty(root=ROOT):
    result = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                            capture_output=True, text=True, check=False)
    return result.stdout.strip()


def digest(root=ROOT):
    """One digest over everything this tier must not write, so a write is caught rather than trusted."""
    sha = hashlib.sha256()
    for relative in GUARDED:
        path = root / relative
        for item in ([path] if path.is_file() else sorted(path.rglob("*")) if path.exists() else []):
            sha.update(str(item.relative_to(root)).encode())
            if item.is_file():
                sha.update(item.read_bytes())
    return sha.hexdigest()


def run_step(step, root=ROOT):
    """Run one check under a bounded timeout and classify it, never inferring a pass."""
    started = time.time()
    if step.get("clean_tree") and dirty(root):
        return {"name": step["name"], "result": "unverified", "seconds": 0.0,
                "detail": "the checkout is dirty and this check requires a clean one"}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.update(step.get("env") or {})
    try:
        completed = subprocess.run([str(item) for item in step["argv"]], cwd=str(root), env=env,
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                   timeout=step["timeout"], check=False)
    except subprocess.TimeoutExpired:
        # The failure this tier exists to replace: a check that hangs reports nothing at all.
        return {"name": step["name"], "result": "failed", "seconds": step["timeout"],
                "detail": "no answer within %ss" % step["timeout"]}
    seconds = round(time.time() - started, 1)
    if completed.returncode == 0:
        return {"name": step["name"], "result": "passed", "seconds": seconds, "detail": ""}
    output = (completed.stderr or "") + (completed.stdout or "")
    return {"name": step["name"], "result": "failed", "seconds": seconds,
            "detail": redact(output[-TAIL:]) or "exit %s with no output" % completed.returncode}


def names_in(names, plan):
    chosen = [name.strip() for name in (names or "").split(",") if name.strip()]
    unknown = [name for name in chosen if name not in {step["name"] for step in plan}]
    if unknown:
        raise SystemExit("unknown smoke check: " + ", ".join(unknown))
    return chosen


def selected(only, skip, plan):
    keep = names_in(only, plan) or [step["name"] for step in plan]
    dropped = names_in(skip, plan)
    return [step for step in plan if step["name"] in keep and step["name"] not in dropped]


def report(results, wrote):
    lines = [NOT_QUALIFICATION]
    for item in results:
        lines.append("  %-26s %-11s %ss" % (item["name"], item["result"], item["seconds"]))
        if item["detail"]:
            lines.append("      " + item["detail"])
    counted = [result for result in ("passed", "failed", "unverified")
               if any(item["result"] == result for item in results)]
    lines.append("smoke tier: " + ", ".join(
        "%s %s" % (sum(item["result"] == result for item in results), result)
        for result in counted or ["passed"]))
    if wrote:
        lines.append("smoke tier: a check wrote under %s; the tier writes no evidence"
                     % " or ".join(str(path) for path in GUARDED))
    return "\n".join(lines)


def tier(plan, root=ROOT, runner=run_step):
    before = digest(root)
    results = [runner(step, root) for step in plan]
    return results, digest(root) != before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated subset of the checks to run")
    parser.add_argument("--skip", help="comma-separated checks to leave out of this run")
    parser.add_argument("--list", action="store_true", dest="listing",
                        help="print what would run, running nothing")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="harness-smoke-") as work:
        plan = selected(args.only, args.skip, steps(Path(work)))
        if args.listing:
            print("\n".join([NOT_QUALIFICATION]
                            + ["  %-26s %s" % (step["name"], step["how"]) for step in plan]))
            return 0
        results, wrote = tier(plan)
    print(report(results, wrote))
    return 0 if not wrote and all(item["result"] == "passed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
