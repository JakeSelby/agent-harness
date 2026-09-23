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
    python3 scripts/qualification_round.py --round ../round-0.13.0 --execution-class light

Each target carries an execution class and an assessment class, resolved before anything is
launched and recorded with the round; `harness_core.qualification` holds the rules and the two
refusals.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_core import qualification  # noqa: E402
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


def target_argv(clone, client, model, out, confirmed, routing):
    """The runner's own argv for one target; confirmation is passed through per target only."""
    argv = [sys.executable, str(Path(clone) / "scripts" / RUNNER), "--client", client,
            "--out", str(out), "--execution-class", routing["execution_class"],
            "--assessment-class", routing["assessment_class"]]
    if model:
        argv += ["--model", model]
    if client in confirmed_targets(confirmed):
        argv += ["--home-confirmed", client]
    return argv


def routing(targets, execution, assessment):
    """One class pair per target, resolved before anything is launched.

    A refused pair stops the whole round rather than the target that asked for it: the round's
    record would otherwise say two different things about who read its evidence.
    """
    try:
        executes = qualification.parse_class_map(execution, targets,
                                                 qualification.EXECUTION_DEFAULT,
                                                 "--execution-class", CLIENTS)
        assesses = qualification.parse_class_map(assessment, targets,
                                                 qualification.ASSESSMENT_DEFAULT,
                                                 "--assessment-class", CLIENTS)
        return dict((client, qualification.resolve(ROOT, CLIENTS[client]["runtime"],
                                                   executes[client], assesses[client]))
                    for client in targets)
    except ValueError as error:
        raise SystemExit(str(error))


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


def write_round(round_dir, result):
    """The round record as it stands, rewritten as each target finishes.

    It is written before the smoke tier runs, so a round killed part way through still names the
    classes that were executing and whatever targets had finished.
    """
    (Path(round_dir) / "round.json").write_text(json.dumps(result, indent=2, sort_keys=True)
                                                + "\n")
    return result


def run_round(round_dir, targets, model, confirmed, skip_smoke=False, tier_routing=None):
    tier_routing = tier_routing or routing(targets, None, None)
    report = provision_record(round_dir)
    clone = Path(report["clone"])
    records_dir = Path(report["records"])
    records_dir.mkdir(parents=True, exist_ok=True)
    env = environment(report)
    result = {"source_commit": report.get("source_commit"), "smoke": "skipped", "targets": {},
              "tier_routing": tier_routing}
    write_round(round_dir, result)
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
            subprocess.run(target_argv(clone, client, model, out, confirmed,
                                       tier_routing[client]),
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
        write_round(round_dir, result)
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
    parser.add_argument("--execution-class", action="append", metavar="[TARGET=]CLASS",
                        help="capability class running the cases (default %s, per target with "
                             "TARGET=CLASS)" % qualification.EXECUTION_DEFAULT)
    parser.add_argument("--assessment-class", action="append", metavar="[TARGET=]CLASS",
                        help="capability class assessing the observations (default %s)"
                             % qualification.ASSESSMENT_DEFAULT)
    parser.add_argument("--plan", action="store_true",
                        help="print what the round would run, launching nothing")
    args = parser.parse_args(argv)
    targets = [name.strip() for name in args.targets.split(",") if name.strip()]
    unknown = [name for name in targets if name not in CLIENTS]
    if unknown:
        raise SystemExit("unknown qualification target: " + ", ".join(unknown))
    tier_routing = routing(targets, args.execution_class, args.assessment_class)
    if args.plan:
        print("round: %s, targets %s, smoke tier %s"
              % (args.round, ", ".join(targets), "skipped" if args.skip_smoke else "first"))
        for client in targets:
            print("  %-24s %s" % (client, unobserved_note(client, args.home_confirmed)
                                  or "driven by this runner"))
            print("  %-24s %s" % ("", qualification.describe(tier_routing[client])))
        return 0
    result = write_round(args.round, run_round(args.round, targets, args.model,
                                               args.home_confirmed, args.skip_smoke,
                                               tier_routing))
    print("smoke tier: " + result["smoke"])
    print(summarise(result["targets"]))
    for client in targets:
        print("%-24s %s" % (client, qualification.describe(tier_routing[client])))
    clean = result["smoke"] != "failed" and all(
        value == PASSED
        for data in result["targets"].values()
        for value in (data.get("cases") or {"none": "unverified"}).values())
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
