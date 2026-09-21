#!/usr/bin/env python3
"""Keep the GitHub About panel equal to the landing copy in `product.json`.

`--check` names every field that differs and exits non-zero; `--apply` writes the
repository's public metadata through `gh repo edit`, so it needs the owner's
approval each run. Topics are compared as a set, because GitHub returns them in
its own order.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH_TIMEOUT_SECONDS = 30
VIEW_ARGS = ("repo", "view", "--json", "description,repositoryTopics,homepageUrl")


class GhError(RuntimeError):
    """`gh` was missing, refused, or returned output that could not be read."""


def gh(args, root=ROOT):
    """Run `gh` and return its stdout, raising `GhError` for every failure mode."""
    try:
        result = subprocess.run(["gh", *args], cwd=str(root), text=True,
                                capture_output=True, timeout=GH_TIMEOUT_SECONDS)
    except OSError as error:
        raise GhError("gh is not available: {}".format(error))
    except subprocess.TimeoutExpired:
        raise GhError("gh timed out after {} seconds".format(GH_TIMEOUT_SECONDS))
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise GhError(message or "gh exited {}".format(result.returncode))
    return result.stdout


def authenticated(runner=gh):
    try:
        runner(["auth", "status"])
    except GhError:
        return False
    return True


def product(root=ROOT):
    """About as `product.json` declares it.

    `homepage` is optional: when the data names none, the live homepage is left
    alone rather than compared against a value the repository does not hold.
    """
    data = json.loads((root / "product.json").read_text())
    about = {"description": data["github_description"], "topics": sorted(data["topics"])}
    homepage = data.get("homepage")
    if homepage:
        about["homepage"] = homepage
    return about


def published(runner=gh):
    data = json.loads(runner(list(VIEW_ARGS)))
    return {
        "description": data.get("description") or "",
        "topics": sorted(topic["name"] for topic in data.get("repositoryTopics") or []),
        "homepage": data.get("homepageUrl") or "",
    }


def differences(wanted, live):
    """Field names whose live value differs from `product.json`, in a stable order."""
    return [field for field in ("description", "topics", "homepage")
            if field in wanted and live[field] != wanted[field]]


def shown(value):
    return ", ".join(value) if isinstance(value, list) else value


def edit_args(wanted, live):
    """The `gh repo edit` arguments that would make GitHub match `product.json`."""
    args = ["repo", "edit"]
    if live["description"] != wanted["description"]:
        args += ["--description", wanted["description"]]
    if "homepage" in wanted and live["homepage"] != wanted["homepage"]:
        args += ["--homepage", wanted["homepage"]]
    for topic in sorted(set(wanted["topics"]) - set(live["topics"])):
        args += ["--add-topic", topic]
    for topic in sorted(set(live["topics"]) - set(wanted["topics"])):
        args += ["--remove-topic", topic]
    return args


def report(fields, wanted, live, out=print):
    for field in fields:
        out("About drift: " + field)
        out("  product.json: " + shown(wanted[field]))
        out("  github:       " + shown(live[field]))


def main(argv=None, root=ROOT, runner=gh):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="report drift and exit non-zero when About differs")
    group.add_argument("--apply", action="store_true",
                       help="write description, topics and homepage to GitHub")
    args = parser.parse_args(argv)
    wanted = product(root)
    try:
        live = published(runner)
        fields = differences(wanted, live)
        if not fields:
            print("About matches product.json: " + ", ".join(sorted(wanted)))
            return 0
        report(fields, wanted, live)
        if args.check:
            return 1
        runner(edit_args(wanted, live))
    except GhError as error:
        print("About check failed: " + str(error))
        return 1
    print("About updated from product.json: " + ", ".join(fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
