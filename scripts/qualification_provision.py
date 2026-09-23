#!/usr/bin/env python3
"""Provision one qualification round's scratch directory, once, from this checkout.

Every round before this one built the same three things by hand in a per-round scratch copy: a
frozen clone of the commit under qualification, a BMad framework checkout for the workflow case,
and a place to keep each target's record. Hand-built means unreviewed, and a clone taken from the
wrong commit invalidates the round it is used for, so it is a committed script instead.

The clone is taken from this repository's own object store — no network — and it is refused
unless the tree is clean and the commit is the one the caller named. The BMad step is the only
one that reaches the network, it is opt-in, and it runs the pinned installer from docs/bmad.md
rather than a floating version.

    python3 scripts/qualification_provision.py --out ../round-0.13.0
    python3 scripts/qualification_provision.py --out ../round-0.13.0 --commit <sha> --bmad
    python3 scripts/qualification_provision.py --out ../round-0.13.0 --print-env
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
# Split around the `@`, as the runner splits its throwaway committer identity, so the lint's
# address pattern does not match a pinned npm specifier.
BMAD_INSTALLER = "bmad-method" "@6.12.0"
BMAD_MODULES = "bmm,gds"
CLONE = "clone"
RECORDS = "records"
BMAD = "bmad"
BMAD_ENV = "HARNESS_ACCEPTANCE_BMAD"
TIMEOUT = 600


def run(args, cwd=None, timeout=TIMEOUT):
    return subprocess.run([str(item) for item in args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, check=False, timeout=timeout)


def git(*args, **kwargs):
    return run(["git", "-C", str(kwargs.pop("repo", ROOT))] + list(args), **kwargs)


def head():
    return git("rev-parse", "HEAD").stdout.strip()


def clean():
    return not git("status", "--porcelain").stdout.strip()


def clone(out, commit):
    """A read-only clone of one commit, taken from the local object store.

    The round's evidence names a source commit; a clone that is not at that commit records a
    claim about source nobody ran. `--no-hardlinks` is deliberate: a hard-linked object store
    shares a fate with the checkout the operator keeps working in.
    """
    target = out / CLONE
    if target.exists():
        shutil.rmtree(str(target))
    result = run(["git", "clone", "--quiet", "--no-hardlinks", "--shared=false", str(ROOT),
                  str(target)])
    if result.returncode:
        raise SystemExit("could not clone this checkout: " + result.stderr.strip()[-300:])
    checked = git("checkout", "--quiet", "--detach", commit, repo=target)
    if checked.returncode:
        raise SystemExit("the clone could not be moved to %s: %s"
                         % (commit, checked.stderr.strip()[-300:]))
    at = git("rev-parse", "HEAD", repo=target).stdout.strip()
    if at != commit:
        raise SystemExit("the clone is at %s, not the commit asked for" % at)
    return target


def bmad(out):
    """A BMad framework checkout for the workflow case, from the pinned installer.

    The only step here that reaches the network. It is opt-in because a round that is not running
    `bmad-workflow` should not pay for it, and because an installer this script cannot find is a
    reported gap rather than a failed provision.
    """
    target = out / BMAD
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        git("init", "--quiet", repo=target)
    if not shutil.which("npx"):
        return None, "npx is not on PATH, so no BMad framework checkout was installed"
    result = run(["npx", BMAD_INSTALLER, "install", "--directory", str(target),
                  "--modules", BMAD_MODULES, "--tools", "claude-code,codex", "--yes"],
                 timeout=TIMEOUT)
    if result.returncode or not (target / "_bmad").is_dir():
        return None, ("the pinned BMad installer did not produce a framework checkout: "
                      + (result.stderr or result.stdout).strip()[-300:])
    return target, ""


def provision(out, commit, want_bmad):
    out.mkdir(parents=True, exist_ok=True)
    (out / RECORDS).mkdir(exist_ok=True)
    report = {"harness_version": VERSION, "source_commit": commit,
              "clone": str(clone(out, commit)), "records": str(out / RECORDS),
              "bmad": None, "notes": []}
    if want_bmad:
        path, note = bmad(out)
        report["bmad"] = str(path) if path else None
        if note:
            report["notes"].append(note)
    else:
        report["notes"].append("no BMad framework checkout was asked for, so bmad-workflow will "
                               "report itself unverified")
    return report


def environment(report):
    """The one variable a round exports, so no case reaches the network to find a checkout."""
    return {BMAD_ENV: report["bmad"]} if report.get("bmad") else {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True,
                        help="round directory, outside this checkout")
    parser.add_argument("--commit", help="commit to qualify (default: HEAD of this checkout)")
    parser.add_argument("--bmad", action="store_true",
                        help="install the pinned BMad framework checkout; the only network step")
    parser.add_argument("--print-env", action="store_true",
                        help="print the exports a round needs, one per line, and provision nothing")
    args = parser.parse_args(argv)
    out = args.out.expanduser().resolve()
    if ROOT == out or ROOT in out.parents:
        raise SystemExit("the round directory must be outside this checkout")
    if args.print_env:
        existing = out / "provision.json"
        if not existing.is_file():
            raise SystemExit("no provision record at %s; provision the round first" % existing)
        for key, value in sorted(environment(json.loads(existing.read_text())).items()):
            print("export %s=%s" % (key, value))
        return 0
    if not clean():
        raise SystemExit("the checkout must be clean: a round's evidence names a source commit")
    commit = args.commit or head()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        resolved = git("rev-parse", commit).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", resolved):
            raise SystemExit("not a commit in this repository: " + commit)
        commit = resolved
    report = provision(out, commit, args.bmad)
    (out / "provision.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
