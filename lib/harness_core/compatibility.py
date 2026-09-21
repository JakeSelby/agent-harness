"""Compatibility claims must carry versioned native evidence."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

STATES = {"qualified", "unqualified", "planned", "unsupported"}
SOURCE_PATHS = ("VERSION", "bin", "lib", "adapters", "primitives", "policy", "templates",
                "config.example.json")
FREEZE_STATES = {"open", "frozen"}


def qualification_source(data):
    """Return the source identity a catalog's evidence qualifies."""
    if data.get("release_state") != "released":
        return "HEAD"
    commit = data.get("qualification_source_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError("released compatibility catalog requires a full qualification source commit")
    return commit


def source_drift(root, data):
    """A released claim stays readable, but changed source needs new qualification."""
    target = qualification_source(data)
    if target == "HEAD":
        return False
    ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", target, "HEAD"],
                              capture_output=True)
    unchanged = subprocess.run(["git", "-C", str(root), "diff", "--quiet", target, "HEAD", "--",
                                *SOURCE_PATHS], capture_output=True)
    return bool(ancestry.returncode or unchanged.returncode)


def git_output(root, *args):
    """Run a read-only git command in `root`, refusing to guess when it fails."""
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if done.returncode:
        detail = (done.stderr.strip().splitlines() or [""])[0]
        raise ValueError("git " + args[0] + " failed: " + detail)
    return done.stdout


def freeze_record(root):
    """Read the release-branch freeze record; a missing file means no branch is frozen.

    A qualification round runs on the `release/vX.Y.Z` branch cut at this commit, so merges
    into `main` cannot invalidate the round's evidence. See docs/releasing.md.
    """
    path = root / "compatibility" / "freeze.json"
    if not path.is_file():
        return {"schema_version": 1, "state": "open"}
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported freeze schema")
    if data.get("state") not in FREEZE_STATES:
        raise ValueError("freeze state must be one of: " + ", ".join(sorted(FREEZE_STATES)))
    if data["state"] == "frozen":
        if not isinstance(data.get("branch"), str) or not data["branch"].strip():
            raise ValueError("a frozen release branch requires its branch name")
        commit = data.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise ValueError("a frozen release branch requires a full commit identity")
    return data


def freeze_drift(root, data, ref="origin/main"):
    """Report runtime source drift between the frozen commit and `ref`.

    This is the check a release handoff otherwise records by hand; an empty `paths` means the
    round's evidence still describes `ref` as well as it describes the frozen commit.
    """
    result = {"state": data.get("state", "open"), "branch": data.get("branch"),
              "commit": data.get("commit"), "ref": ref, "paths": [], "stat": ""}
    if result["state"] != "frozen":
        return result
    numstat = git_output(root, "diff", "--numstat", "--no-renames", result["commit"], ref,
                         "--", *SOURCE_PATHS)
    result["paths"] = sorted({line.split("\t")[-1] for line in numstat.splitlines() if line.strip()})
    result["stat"] = git_output(root, "diff", "--stat", "--no-renames", result["commit"], ref,
                                "--", *SOURCE_PATHS).strip()
    return result


def merge_refusal(root, data, ref):
    """Refuse a merge into a frozen release branch that changes the qualified runtime source."""
    if data.get("state") != "frozen":
        return []
    result = freeze_drift(root, data, ref)
    if not result["paths"]:
        return []
    return [data["branch"] + " is frozen at " + data["commit"][:12] + "; " + ref
            + " changes qualified runtime source: " + ", ".join(result["paths"])]


def catalog(root):
    data = json.loads((root / "compatibility" / "catalog.json").read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported compatibility schema")
    if data.get("harness_version") != (root / "VERSION").read_text().strip():
        raise ValueError("compatibility catalog does not match VERSION")
    identifiers = [row["id"] for row in data["clients"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate compatibility client")
    target = qualification_source(data)
    if target != "HEAD":
        available = subprocess.run(["git", "-C", str(root), "cat-file", "-e", target + "^{commit}"],
                                   capture_output=True)
        if available.returncode:
            raise ValueError("released qualification source commit is unavailable")
    for row in data["clients"]:
        if row.get("status") not in STATES:
            raise ValueError("invalid compatibility status")
        if row["status"] == "qualified":
            errors = evidence_errors(root, data, row)
            if errors:
                raise ValueError(row["id"] + ": " + "; ".join(errors))
    return data


def evidence_errors(root, data, client):
    errors, passed = [], set()
    target = qualification_source(data)
    if not client.get("runtime_version") or not client.get("client_version"):
        errors.append("native runtime and client versions are required")
    for item in client.get("evidence", []):
        path = (root / item.get("path", "")).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append("missing or external evidence artifact")
            continue
        try:
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != item.get("sha256"):
                errors.append("evidence digest mismatch")
                continue
            record = json.loads(content)
        except (ValueError, OSError):
            errors.append("unreadable evidence record")
            continue
        if not isinstance(record, dict):
            errors.append("evidence record must be an object")
            continue
        if record.get("client") != client["id"] or record.get("harness_version") != data["harness_version"]:
            errors.append("evidence version or client mismatch")
            continue
        if any(not client.get(key) or record.get(key) != client[key]
               for key in ("runtime_version", "client_version", "platform")):
            errors.append("evidence runtime, client version or platform mismatch")
            continue
        if record.get("kind") != "native" or not record.get("observations") or not record.get("source_commit"):
            errors.append("native observations and source commit are required")
            continue
        commit = record["source_commit"]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            errors.append("native evidence requires a full source commit identity")
            continue
        ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit, target], capture_output=True)
        unchanged = subprocess.run(["git", "-C", str(root), "diff", "--quiet", commit, target, "--",
                                    *SOURCE_PATHS], capture_output=True)
        if ancestry.returncode or unchanged.returncode:
            errors.append("runtime source changed or evidence commit is unavailable")
            continue
        cases = record.get("cases")
        if not isinstance(cases, dict) or not cases:
            errors.append("native evidence requires acceptance cases")
            continue
        for case, result in cases.items():
            if case not in data["required_cases"] or result not in ("passed", "failed", "unverified"):
                errors.append("unknown acceptance case or result")
            elif result != "passed":
                # Every linked record is part of the claim; another pass cannot hide a failure.
                errors.append(case + " is " + result + " in linked evidence")
            else:
                passed.add(case)
    missing = set(data["required_cases"]) - passed
    if missing:
        errors.append("missing acceptance cases: " + ", ".join(sorted(missing)))
    return errors


def release_errors(root):
    data = catalog(root)
    errors = [row["id"] + " is " + row["status"] for row in data["clients"]
              if row.get("required_for_release") and row["status"] != "qualified"]
    if source_drift(root, data):
        errors.append("current runtime source differs from the released qualification source")
    return errors


def coverage(root, choices):
    result = {}
    for runtime in ("claude-code", "codex"):
        bindings = json.loads((root / "adapters" / runtime / "capabilities.json").read_text())
        result[runtime] = {name: bindings["stances"].get(name, bindings["custom_stance_default"]) for name in choices}
    return result
