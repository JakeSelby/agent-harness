"""Compatibility claims must carry versioned native evidence."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

STATES = {"qualified", "unqualified", "planned", "unsupported"}


def catalog(root):
    data = json.loads((root / "compatibility" / "catalog.json").read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported compatibility schema")
    if data.get("harness_version") != (root / "VERSION").read_text().strip():
        raise ValueError("compatibility catalog does not match VERSION")
    identifiers = [row["id"] for row in data["clients"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate compatibility client")
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
    if not client.get("runtime_version") or not client.get("client_version"):
        errors.append("native runtime and client versions are required")
    for item in client.get("evidence", []):
        path = (root / item.get("path", "")).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append("missing or external evidence artifact")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            errors.append("evidence digest mismatch")
            continue
        record = json.loads(path.read_text())
        if record.get("client") != client["id"] or record.get("harness_version") != data["harness_version"]:
            errors.append("evidence version or client mismatch")
            continue
        if record.get("kind") != "native" or not record.get("observations") or not record.get("source_commit"):
            errors.append("native observations and source commit are required")
            continue
        commit = record["source_commit"]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            errors.append("native evidence requires a full source commit identity")
            continue
        ancestry = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True)
        unchanged = subprocess.run(["git", "-C", str(root), "diff", "--quiet", commit, "HEAD", "--",
                                    "VERSION", "bin", "lib", "adapters", "primitives", "policy", "templates", "config.example.json"], capture_output=True)
        if ancestry.returncode or unchanged.returncode:
            errors.append("runtime source changed or evidence commit is unavailable")
            continue
        passed.update(case for case, result in record.get("cases", {}).items() if result == "passed")
    missing = set(data["required_cases"]) - passed
    if missing:
        errors.append("missing acceptance cases: " + ", ".join(sorted(missing)))
    return errors


def release_errors(root):
    data = catalog(root)
    return [row["id"] + " is " + row["status"] for row in data["clients"]
            if row.get("required_for_release") and row["status"] != "qualified"]


def coverage(root, choices):
    result = {}
    for runtime in ("claude-code", "codex"):
        bindings = json.loads((root / "adapters" / runtime / "capabilities.json").read_text())
        result[runtime] = {name: bindings["stances"].get(name, bindings["custom_stance_default"]) for name in choices}
    return result
