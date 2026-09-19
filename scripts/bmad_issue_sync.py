#!/usr/bin/env python3
"""Maintain the public BMad-to-GitHub issue mapping.

GitHub owns delivery state. This tool owns only the idempotent planning block,
native issue type, exact BMad type label, and primary parent relationship.
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "_bmad-output" / "issue-map.json"
ARTIFACT_DIR = ROOT / "_bmad-output" / "implementation-artifacts"
BEGIN = "<!-- bmad-traceability:start -->"
END = "<!-- bmad-traceability:end -->"
GH_TIMEOUT_SECONDS = 30
MISSING = object()
KINDS = ("epic", "story", "task", "bug", "chore", "spike", "decision")
PREFIX = {
    "epic": "E",
    "story": "S",
    "task": "T",
    "bug": "B",
    "chore": "C",
    "spike": "SP",
    "decision": "D",
}
NATIVE_TYPE = {
    "epic": "Feature",
    "story": "Feature",
    "task": "Task",
    "bug": "Bug",
    "chore": "Task",
    "spike": "Task",
    "decision": "Task",
}
EPICS = {93, 116, 135, 189}
DECISIONS = {52}
SPIKES = {141, 146, 159}
BUGS = {37, 67, 80, 84, 85, 181}
AUTHORED = {189, 190, 191, 192, 193}
PARENTS = {
    **{number: 93 for number in range(94, 101)},
    **{number: 116 for number in range(117, 131)},
    134: 98,
    **{number: 135 for number in list(range(136, 148)) + list(range(156, 163))},
    163: 94,
    164: 95,
    165: 96,
    166: 97,
    167: 98,
    168: 94,
    169: 99,
    170: 95,
    171: 94,
    172: 100,
    173: 96,
    174: 97,
    175: 97,
    176: 97,
    177: 96,
    178: 98,
    179: 97,
    180: 97,
    181: 96,
    183: 99,
    185: 98,
    187: 98,
    188: 98,
    **{number: 189 for number in range(190, 194)},
}


def gh_command(args, input_data=None):
    command = ["gh"] + list(args)
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            input=None if input_data is None else json.dumps(input_data),
            text=True,
            capture_output=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "GitHub command timed out after {} seconds".format(GH_TIMEOUT_SECONDS)
        ) from error
    except OSError as error:
        raise RuntimeError("GitHub command failed: {}".format(error)) from error
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def gh_json(args, input_data=None):
    result = gh_command(args, input_data)
    return json.loads(result.stdout) if result.stdout.strip() else None


def fetch_issues(repo):
    pages = gh_json(
        [
            "api",
            "--method",
            "GET",
            "--paginate",
            "--slurp",
            "-H",
            "X-GitHub-Api-Version: 2026-03-10",
            "repos/{}/issues?state=all&per_page=100".format(repo),
        ]
    )
    return sorted(
        [issue for page in pages for issue in page if "pull_request" not in issue],
        key=lambda issue: issue["number"],
    )


def infer_kind(issue):
    number = issue["number"]
    title = issue["title"].lower()
    labels = {label["name"].lower() for label in issue.get("labels", [])}
    if number in EPICS:
        return "epic"
    if number in DECISIONS:
        return "decision"
    if number in SPIKES:
        return "spike"
    if number in BUGS or "bug" in labels or title.startswith("fix"):
        return "bug"
    if "docs" in labels or title.startswith("docs") or title.startswith("refactor"):
        return "chore"
    return "story"


def build_manifest(issues, repo):
    counters = defaultdict(int)
    items = []
    by_number = {}
    for issue in sorted(issues, key=lambda value: value["number"]):
        kind = infer_kind(issue)
        counters[kind] += 1
        bmad_id = "AH-{}{:03d}".format(PREFIX[kind], counters[kind])
        item = {
            "bmad_id": bmad_id,
            "github_number": issue["number"],
            "github_url": issue["html_url"],
            "title": issue["title"],
            "type": kind,
            "native_type": NATIVE_TYPE[kind],
            "artifact_path": "_bmad-output/implementation-artifacts/{}.md".format(bmad_id),
            "parent_bmad_id": None,
            "parent_github_number": PARENTS.get(issue["number"]),
            "lifecycle": "active" if issue["state"] == "open" else "completed",
            "provenance": "authored" if issue["number"] in AUTHORED else "reconstructed",
        }
        items.append(item)
        by_number[issue["number"]] = item
    for item in items:
        parent = by_number.get(item["parent_github_number"])
        if parent:
            item["parent_bmad_id"] = parent["bmad_id"]
    return {
        "schema_version": 1,
        "repository": repo,
        "generated_at": dt.date.today().isoformat(),
        "next_ids": {kind: counters[kind] + 1 for kind in KINDS},
        "items": items,
    }


def yaml_value(value):
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def render_artifact(item):
    history = (
        "This file reconstructs planning metadata from the existing GitHub record. It does not imply "
        "that a BMad artifact existed when the original work was performed."
        if item["provenance"] == "reconstructed"
        else "This work item was authored as part of the repository's committed BMad planning system."
    )
    parent = "None"
    if item["parent_github_number"]:
        repository_url = item["github_url"].rsplit("/issues/", 1)[0]
        parent = "[{}]({}/issues/{})".format(
            item["parent_bmad_id"], repository_url, item["parent_github_number"]
        )
    fields = [
        ("bmad_id", item["bmad_id"]),
        ("type", item["type"]),
        ("title", item["title"]),
        ("lifecycle", item["lifecycle"]),
        ("provenance", item["provenance"]),
        ("github_issue", item["github_number"]),
        ("github_issue_url", item["github_url"]),
        ("parent_bmad_id", item["parent_bmad_id"]),
        ("parent_github_issue", item["parent_github_number"]),
        ("updated", dt.date.today().isoformat()),
    ]
    frontmatter = "\n".join("{}: {}".format(key, yaml_value(value)) for key, value in fields)
    return """---
{}
---

# {} — {}

{}

## Delivery authority

- **GitHub issue:** [#{}]({})
- **Primary parent:** {}
- **State:** {}

The GitHub issue owns scope, discussion, delivery state and acceptance evidence. This immutable-ID
file owns the planning identity and reverse link; amendments belong here only when they add durable
planning context rather than duplicate the issue.
""".format(
        frontmatter,
        item["bmad_id"],
        item["title"],
        history,
        item["github_number"],
        item["github_url"],
        parent,
        item["lifecycle"],
    )


def write_manifest(manifest):
    map_path = ROOT / "_bmad-output" / "issue-map.json"
    artifact_dir = ROOT / "_bmad-output" / "implementation-artifacts"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    expected = set()
    for item in manifest["items"]:
        path = ROOT / item["artifact_path"]
        expected.add(path)
    for path in artifact_dir.glob("AH-*.md"):
        if path not in expected:
            raise RuntimeError("refusing to remove unreferenced artifact: {}".format(path))
    for item in manifest["items"]:
        path = ROOT / item["artifact_path"]
        if not path.exists():
            path.write_text(render_artifact(item), encoding="utf-8")
    map_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_manifest():
    return json.loads((ROOT / "_bmad-output" / "issue-map.json").read_text(encoding="utf-8"))


def frontmatter_value(text, key):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return MISSING
    try:
        end = lines.index("---", 1)
    except ValueError:
        return MISSING
    frontmatter = "\n".join(lines[1:end])
    matches = re.findall(r"^{}:\s*(.+)$".format(re.escape(key)), frontmatter, re.MULTILINE)
    if len(matches) != 1:
        return MISSING
    raw = matches[0]
    if raw == "null":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return MISSING


def audit_manifest(manifest=None):
    manifest = manifest or load_manifest()
    errors = []
    seen_ids = set()
    seen_issues = set()
    seen_artifacts = set()
    by_id = {item["bmad_id"]: item for item in manifest.get("items", [])}
    for item in manifest.get("items", []):
        bmad_id = item["bmad_id"]
        issue_number = item["github_number"]
        expected_id = r"^AH-{}\d{{3}}$".format(PREFIX.get(item["type"], "INVALID"))
        if not re.match(expected_id, bmad_id):
            errors.append("{}: ID does not match type {}".format(bmad_id, item["type"]))
        if bmad_id in seen_ids:
            errors.append("duplicate BMad ID {}".format(bmad_id))
        if issue_number in seen_issues:
            errors.append("duplicate GitHub issue #{}".format(issue_number))
        if item["artifact_path"] in seen_artifacts:
            errors.append("duplicate artifact path {}".format(item["artifact_path"]))
        seen_ids.add(bmad_id)
        seen_issues.add(issue_number)
        seen_artifacts.add(item["artifact_path"])
        expected_path = "_bmad-output/implementation-artifacts/{}.md".format(bmad_id)
        if item["artifact_path"] != expected_path:
            errors.append("{}: artifact path does not match ID".format(bmad_id))
        if item["native_type"] != NATIVE_TYPE.get(item["type"]):
            errors.append("{}: invalid native type".format(bmad_id))
        if bool(item["parent_bmad_id"]) != bool(item["parent_github_number"]):
            errors.append("{}: parent mapping is incomplete".format(bmad_id))
        elif item["parent_bmad_id"]:
            parent = by_id.get(item["parent_bmad_id"])
            if not parent or parent["github_number"] != item["parent_github_number"]:
                errors.append("{}: parent mapping is inconsistent".format(bmad_id))
        path = ROOT / item["artifact_path"]
        if not path.is_file():
            errors.append("{}: missing artifact {}".format(bmad_id, item["artifact_path"]))
            continue
        text = path.read_text(encoding="utf-8")
        expected = {
            "bmad_id": bmad_id,
            "type": item["type"],
            "title": item["title"],
            "lifecycle": item["lifecycle"],
            "provenance": item["provenance"],
            "github_issue": issue_number,
            "github_issue_url": item["github_url"],
            "parent_bmad_id": item["parent_bmad_id"],
            "parent_github_issue": item["parent_github_number"],
        }
        for key, value in expected.items():
            if frontmatter_value(text, key) != value:
                errors.append("{}: artifact {} does not match manifest".format(bmad_id, key))
    for kind in KINDS:
        next_id = manifest.get("next_ids", {}).get(kind)
        used = []
        pattern = re.compile(r"^AH-{}(\d{{3}})$".format(PREFIX[kind]))
        for item in manifest.get("items", []):
            match = pattern.match(item["bmad_id"])
            if item.get("type") == kind and match:
                used.append(int(match.group(1)))
        if type(next_id) is not int or next_id < 1 or (used and next_id <= max(used)):
            errors.append("{}: next ID is not monotonic".format(kind))
    expected_paths = {ROOT / path for path in seen_artifacts}
    artifact_dir = ROOT / "_bmad-output" / "implementation-artifacts"
    for path in artifact_dir.glob("AH-*.md"):
        if path not in expected_paths:
            errors.append("unreferenced artifact {}".format(path.relative_to(ROOT)))
    return errors


def planning_block(item, repo):
    artifact_url = "https://github.com/{}/blob/main/{}".format(repo, item["artifact_path"])
    lines = [
        BEGIN,
        "## Planning",
        "",
        "- **BMad ID:** `{}`".format(item["bmad_id"]),
        "- **Artifact:** [{}]({})".format(item["bmad_id"], artifact_url),
    ]
    if item["parent_github_number"]:
        lines.append(
            "- **Primary parent:** [{}](https://github.com/{}/issues/{})".format(
                item["parent_bmad_id"], repo, item["parent_github_number"]
            )
        )
    lines += ["", END]
    return "\n".join(lines)


def upsert_planning_block(body, block):
    body = body or ""
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    matches = list(pattern.finditer(body))
    if body.count(BEGIN) != body.count(END) or len(matches) != body.count(BEGIN):
        raise RuntimeError("issue body has malformed BMad Planning fences")
    if matches:
        parts = []
        cursor = 0
        for index, match in enumerate(matches):
            parts.append(body[cursor:match.start()])
            if index == 0:
                parts.append(block)
            cursor = match.end()
        parts.append(body[cursor:])
        return "".join(parts)
    return body.rstrip() + ("\n\n" if body.strip() else "") + block


def type_name(value):
    if isinstance(value, dict):
        return value.get("name")
    return value


def desired_labels(issue, kind):
    unrelated = {
        label["name"] for label in issue.get("labels", [])
        if not label["name"].startswith("type::")
    }
    return unrelated | {"type::{}".format(kind)}


def planned_actions(manifest, live_issues):
    live = {issue["number"]: issue for issue in live_issues}
    actions = []
    for item in manifest["items"]:
        issue = live.get(item["github_number"])
        if not issue:
            actions.append({"issue": item["github_number"], "action": "missing"})
            continue
        desired_body = upsert_planning_block(issue.get("body"), planning_block(item, manifest["repository"]))
        labels = {label["name"] for label in issue.get("labels", [])}
        changes = []
        if desired_body != (issue.get("body") or ""):
            changes.append("planning-block")
        if type_name(issue.get("type")) != item["native_type"]:
            changes.append("native-type")
        if labels != desired_labels(issue, item["type"]):
            changes.append("type-label")
        parent_url = issue.get("parent_issue_url")
        current_parent = int(parent_url.rstrip("/").split("/")[-1]) if parent_url else None
        if current_parent != item["parent_github_number"]:
            changes.append("parent")
        if changes:
            actions.append({"issue": item["github_number"], "changes": changes})
    return actions


def verify_remote_artifacts(manifest):
    repo = manifest["repository"]
    tree = gh_json(["api", "repos/{}/git/trees/main?recursive=1".format(repo)])
    if tree.get("truncated"):
        raise RuntimeError("GitHub returned a truncated main tree; artifact presence is unknown")
    paths = {entry["path"] for entry in tree.get("tree", [])}
    return [item["artifact_path"] for item in manifest["items"] if item["artifact_path"] not in paths]


def apply_manifest(manifest):
    errors = audit_manifest(manifest)
    if errors:
        raise RuntimeError("\n".join(errors))
    missing = verify_remote_artifacts(manifest)
    if missing:
        raise RuntimeError("artifacts are not on main: {}".format(", ".join(missing[:5])))
    repo = manifest["repository"]
    live_issues = fetch_issues(repo)
    live = {issue["number"]: issue for issue in live_issues}
    missing_issues = [item["github_number"] for item in manifest["items"] if item["github_number"] not in live]
    if missing_issues:
        raise RuntimeError(
            "mapped issues were not found: {}".format(
                ", ".join("#{}".format(number) for number in missing_issues)
            )
        )
    planned_actions(manifest, live_issues)
    for kind in sorted({item["type"] for item in manifest["items"]}):
        gh_command(
            [
                "label", "create", "type::{}".format(kind), "-R", repo,
                "--description", "BMad work item type: {}".format(kind), "--color", "6f42c1", "--force",
            ]
        )
    by_number = {item["github_number"]: item for item in manifest["items"]}
    for item in manifest["items"]:
        issue = live[item["github_number"]]
        current_labels = {label["name"] for label in issue.get("labels", [])}
        projected_labels = desired_labels(issue, item["type"])
        desired_body = upsert_planning_block(issue.get("body"), planning_block(item, repo))
        payload = {}
        if desired_body != (issue.get("body") or ""):
            payload["body"] = desired_body
        if type_name(issue.get("type")) != item["native_type"]:
            payload["type"] = item["native_type"]
        if projected_labels != current_labels:
            payload["labels"] = sorted(projected_labels)
        if payload:
            gh_json(
                ["api", "--method", "PATCH", "-H", "X-GitHub-Api-Version: 2026-03-10", "repos/{}/issues/{}".format(repo, item["github_number"]), "--input", "-"],
                payload,
            )
    live_issues = fetch_issues(repo)
    live = {issue["number"]: issue for issue in live_issues}
    for item in manifest["items"]:
        issue = live[item["github_number"]]
        parent_url = issue.get("parent_issue_url")
        current_parent = int(parent_url.rstrip("/").split("/")[-1]) if parent_url else None
        desired_parent = item["parent_github_number"]
        if current_parent == desired_parent:
            continue
        child_id = issue["id"]
        if current_parent:
            gh_json(
                ["api", "--method", "DELETE", "-H", "X-GitHub-Api-Version: 2026-03-10", "repos/{}/issues/{}/sub_issue".format(repo, current_parent), "--input", "-"],
                {"sub_issue_id": child_id},
            )
        if desired_parent and desired_parent in by_number:
            try:
                gh_json(
                    ["api", "--method", "POST", "-H", "X-GitHub-Api-Version: 2026-03-10", "repos/{}/issues/{}/sub_issues".format(repo, desired_parent), "--input", "-"],
                    {"sub_issue_id": child_id},
                )
            except RuntimeError as error:
                if current_parent:
                    try:
                        gh_json(
                            ["api", "--method", "POST", "-H", "X-GitHub-Api-Version: 2026-03-10", "repos/{}/issues/{}/sub_issues".format(repo, current_parent), "--input", "-"],
                            {"sub_issue_id": child_id},
                        )
                    except RuntimeError as rollback_error:
                        raise RuntimeError(
                            "failed to set parent #{}: {}; failed to restore parent #{}: {}".format(
                                desired_parent, error, current_parent, rollback_error
                            )
                        ) from error
                raise


def reserve(manifest, repo, issue_number, kind, parent_number):
    if any(item["github_number"] == issue_number for item in manifest["items"]):
        raise RuntimeError("issue #{} already has a BMad ID".format(issue_number))
    errors = audit_manifest(manifest)
    if errors:
        raise RuntimeError("\n".join(errors))
    issues = {issue["number"]: issue for issue in fetch_issues(repo)}
    issue = issues.get(issue_number)
    if not issue:
        raise RuntimeError("issue #{} was not found".format(issue_number))
    parent = next((item for item in manifest["items"] if item["github_number"] == parent_number), None)
    if parent_number is not None and parent is None:
        raise RuntimeError("parent issue #{} does not have a BMad ID".format(parent_number))
    sequence = manifest["next_ids"][kind]
    if type(sequence) is not int or sequence < 1 or sequence > 999:
        raise RuntimeError("next {} ID sequence is invalid: {}".format(kind, sequence))
    bmad_id = "AH-{}{:03d}".format(PREFIX[kind], sequence)
    if any(item["bmad_id"] == bmad_id for item in manifest["items"]):
        raise RuntimeError("next {} ID {} is already in use".format(kind, bmad_id))
    artifact_path = "_bmad-output/implementation-artifacts/{}.md".format(bmad_id)
    if (ROOT / artifact_path).exists():
        raise RuntimeError("target artifact already exists: {}".format(artifact_path))
    manifest["next_ids"][kind] = sequence + 1
    item = {
        "bmad_id": bmad_id,
        "github_number": issue_number,
        "github_url": issue["html_url"],
        "title": issue["title"],
        "type": kind,
        "native_type": NATIVE_TYPE[kind],
        "artifact_path": artifact_path,
        "parent_bmad_id": parent["bmad_id"] if parent else None,
        "parent_github_number": parent_number,
        "lifecycle": "active" if issue["state"] == "open" else "completed",
        "provenance": "authored",
    }
    manifest["items"].append(item)
    manifest["items"].sort(key=lambda value: value["github_number"])
    write_manifest(manifest)
    return item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument("--repo", default="JakeSelby/agent-harness")
    subparsers.add_parser("audit")
    subparsers.add_parser("plan")
    subparsers.add_parser("apply")
    reserve_parser = subparsers.add_parser("reserve")
    reserve_parser.add_argument("--issue", type=int, required=True)
    reserve_parser.add_argument("--kind", choices=KINDS, required=True)
    reserve_parser.add_argument("--parent", type=int)
    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        if MAP_PATH.exists():
            raise RuntimeError("issue map already exists")
        manifest = build_manifest(fetch_issues(args.repo), args.repo)
        write_manifest(manifest)
        print("bootstrapped {} issues".format(len(manifest["items"])))
        return 0
    manifest = load_manifest()
    if args.command == "audit":
        errors = audit_manifest(manifest)
        for error in errors:
            print(error)
        print("audit: {} issue(s), {} finding(s)".format(len(manifest["items"]), len(errors)))
        return 1 if errors else 0
    if args.command == "plan":
        print(json.dumps(planned_actions(manifest, fetch_issues(manifest["repository"])), indent=2))
        return 0
    if args.command == "apply":
        apply_manifest(manifest)
        remaining = planned_actions(manifest, fetch_issues(manifest["repository"]))
        print("apply: {} remaining action(s)".format(len(remaining)))
        return 1 if remaining else 0
    item = reserve(manifest, manifest["repository"], args.issue, args.kind, args.parent)
    print("reserved {} for issue #{}".format(item["bmad_id"], item["github_number"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print("bmad issue sync: {}".format(error), file=sys.stderr)
        sys.exit(1)
