#!/usr/bin/env python3
"""Drive one qualification round across its targets, from a provisioned round directory.

The driver that ran each round lived only in a per-round scratch copy, so every round rewrote it
and no two rounds were driven quite the same way. This is that driver, committed: it runs the
deterministic smoke tier once, then `scripts/native_acceptance.py` per target from the frozen
clone, and writes one record per target beside a summary an operator reads.

It decides nothing. A target's verdict is the runner's, a failed target does not stop the
others — a round collects every target's defects before any of them is fixed, which is the rule
in docs/releasing.md — and the exit status is 0 only when every case of every target passed.

    python3 scripts/qualification_round.py --round ../round-0.13.0 --targets claude-code-cli-macos
    python3 scripts/qualification_round.py --round ../round-0.13.0 --plan
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_acceptance import (CLIENTS, catalog, confirmed_targets,  # noqa: E402
                               unobserved_note)

SMOKE = "smoke_tier.py"
RUNNER = "native_acceptance.py"
PASSED = "passed"
ROUND_TIMEOUT = 5400


def provision_record(round_dir):
    path = Path(round_dir) / "provision.json"
    if not path.is_file():
        raise SystemExit("no provision record at %s; run scripts/qualification_provision.py first"
                         % path)
    return json.loads(path.read_text())


def environment(report):
    """The round's own exports on top of the operator's, never instead of them.

    The credentials a client uses are the operator's and are passed through by name by the runner
    itself; the round adds only the checkouts it provisioned.
    """
    import os
    env = dict(os.environ)
    if report.get("bmad"):
        env["HARNESS_ACCEPTANCE_BMAD"] = report["bmad"]
    return env


def smoke(clone, env):
    """The deterministic tier, or `None` when it ran past the round's own deadline."""
    try:
        return subprocess.run([sys.executable, str(Path(clone) / "scripts" / SMOKE)],
                              cwd=str(clone), env=env, check=False, timeout=ROUND_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None


def nothing_observed(reason):
    """A target's record when the runner wrote none: every required case, unobserved.

    An absent `--out` is the one shape that must never be read as the previous run's: a runner
    that died before writing left no reading at all, and reporting the stale file would publish
    an old pass as this round's.
    """
    cases = dict((name, "unverified") for name in catalog()["required_cases"])
    return {"cases": cases, "observations": [reason]}


def target_argv(clone, client, model, out, confirmed):
    """The runner's own argv for one target; confirmation is passed through per target only."""
    argv = [sys.executable, str(Path(clone) / "scripts" / RUNNER), "--client", client,
            "--out", str(out)]
    if model:
        argv += ["--model", model]
    if client in confirmed_targets(confirmed):
        argv += ["--home-confirmed", client]
    return argv


def summarise(records):
    """One line per target and case, in the order a reviewer reads them: worst first."""
    lines = []
    for client in sorted(records):
        data = records[client]
        cases = data.get("cases") or {}
        if not cases:
            lines.append("%-24s no record" % client)
            continue
        bad = sorted(name for name, value in cases.items() if value != PASSED)
        lines.append("%-24s %s of %s passed%s"
                     % (client, len(cases) - len(bad), len(cases),
                        (", not " + ", ".join(bad)) if bad else ""))
    return "\n".join(lines)


def run_round(round_dir, targets, model, confirmed, skip_smoke=False):
    report = provision_record(round_dir)
    clone = Path(report["clone"])
    records_dir = Path(report["records"])
    records_dir.mkdir(parents=True, exist_ok=True)
    env = environment(report)
    result = {"source_commit": report.get("source_commit"), "smoke": "skipped", "targets": {}}
    if not skip_smoke:
        finished = smoke(clone, env)
        result["smoke"] = ("timed out" if finished is None
                           else PASSED if finished.returncode == 0 else "failed")
    for client in targets:
        out = records_dir / (client + ".json")
        note = unobserved_note(client, confirmed)
        # Move any earlier record aside before the runner is launched. A runner that exits
        # before writing `--out` would otherwise leave the previous round's file in place and
        # this round would report its passes as its own.
        if out.exists():
            out.replace(out.with_suffix(".json.previous"))
        failure = ""
        try:
            subprocess.run(target_argv(clone, client, model, out, confirmed),
                           cwd=str(clone), env=env, check=False, timeout=ROUND_TIMEOUT)
        except subprocess.TimeoutExpired:
            # Reported and carried, not raised: a round collects every target's defects, and a
            # target that ran past the deadline must not cost the targets after it.
            failure = "the target ran past the round deadline of %ss" % ROUND_TIMEOUT
        try:
            data = json.loads(out.read_text())
        except (OSError, ValueError):
            data = nothing_observed(failure or "the runner wrote no record for this target")
        if failure and failure not in data.get("observations", []):
            data.setdefault("observations", []).append(failure)
        if note:
            data.setdefault("observations", []).append(note)
        result["targets"][client] = data
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=Path, required=True, help="the provisioned round directory")
    parser.add_argument("--targets", default=",".join(sorted(CLIENTS)))
    parser.add_argument("--model", help="the cheapest model each client offers")
    parser.add_argument("--home-confirmed", action="append", default=[], metavar="CLIENT",
                        help="a client whose configuration home was compared against a hand run; "
                             "repeat for each, and never for a surface nobody compared")
    parser.add_argument("--skip-smoke", action="store_true",
                        help="the smoke tier was already run at this commit")
    parser.add_argument("--plan", action="store_true",
                        help="print what the round would run, launching nothing")
    args = parser.parse_args(argv)
    targets = [name.strip() for name in args.targets.split(",") if name.strip()]
    unknown = [name for name in targets if name not in CLIENTS]
    if unknown:
        raise SystemExit("unknown qualification target: " + ", ".join(unknown))
    if args.plan:
        print("round: %s, targets %s, smoke tier %s"
              % (args.round, ", ".join(targets), "skipped" if args.skip_smoke else "first"))
        for client in targets:
            print("  %-24s %s" % (client, unobserved_note(client, args.home_confirmed)
                                  or "driven by this runner"))
        return 0
    result = run_round(args.round, targets, args.model, args.home_confirmed, args.skip_smoke)
    (Path(args.round) / "round.json").write_text(json.dumps(result, indent=2, sort_keys=True)
                                                 + "\n")
    print("smoke tier: " + result["smoke"])
    print(summarise(result["targets"]))
    clean = result["smoke"] != "failed" and all(
        value == PASSED
        for data in result["targets"].values()
        for value in (data.get("cases") or {"none": "unverified"}).values())
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
