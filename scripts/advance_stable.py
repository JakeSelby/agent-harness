#!/usr/bin/env python3
"""Fast-forward the `stable` branch to a release tag, or check that it already points there."""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "stable"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def remote_head(root, remote):
    line = git(root, "ls-remote", "--heads", remote, "refs/heads/" + BRANCH)
    return line.split()[0] if line else None


def plan(root, tag, remote="origin"):
    """Return (action, release commit); `stable` never moves backward or sideways."""
    commit = git(root, "rev-parse", tag + "^{commit}")
    current = remote_head(root, remote)
    if current is None:
        return "create", commit
    if current == commit:
        return "current", commit
    git(root, "fetch", "--quiet", remote, "refs/heads/" + BRANCH)
    code = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", current, commit]).returncode
    if code not in (0, 1):
        raise RuntimeError("cannot compare {} with {}".format(BRANCH, tag))
    return ("advance" if code == 0 else "refuse"), commit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", nargs="?", help="defaults to v<VERSION>")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--check", action="store_true", help="never push; fail unless stable is at the tag")
    args = parser.parse_args(argv)
    args.tag = args.tag or "v" + (ROOT / "VERSION").read_text().strip()
    action, commit = plan(ROOT, args.tag, args.remote)
    if action == "current":
        print("{} is at {} ({})".format(BRANCH, args.tag, commit))
        return 0
    if action == "refuse":
        print("{} is not an ancestor of {}; refusing to move it".format(BRANCH, args.tag))
        return 1
    if args.check:
        print("{} is stale: {} is {} and the branch needs to {}".format(BRANCH, args.tag, commit, action))
        return 1
    try:
        git(ROOT, "push", args.remote, commit + ":refs/heads/" + BRANCH)
    except subprocess.CalledProcessError:
        # The annotation is the only trace when the workflow job is allowed to fail.
        print("::warning::{} was not moved to {}; run scripts/advance_stable.py from a checkout".format(BRANCH, args.tag))
        return 1
    print("{} now at {} ({})".format(BRANCH, args.tag, commit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
