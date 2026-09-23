# SPDX-License-Identifier: MIT
"""Tests for typed BMad story files: templates, the managed block, upgrade and the depth check."""

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bmad_issue_sync", REPO / "scripts" / "bmad_issue_sync.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
sys.path.insert(0, str(REPO / ".github" / "scripts"))
OWNERSHIP_SPEC = importlib.util.spec_from_file_location(
    "issue_ownership_depth", REPO / ".github" / "scripts" / "check_issue_ownership.py"
)
checker = importlib.util.module_from_spec(OWNERSHIP_SPEC)
OWNERSHIP_SPEC.loader.exec_module(checker)

REPOSITORY = "JakeSelby/agent-harness"
AMENDMENT = (
    "\n## Amendment — personal-repository capability boundary\n\n"
    "Live application showed that GitHub accepts but silently discards native issue-type updates.\n"
    "Labels are the authoritative type projection here.\n"
)


def item_for(kind, number=1, provenance="authored", parent=None):
    bmad_id = "AH-{}{:03d}".format(sync.PREFIX[kind], number)
    return {
        "bmad_id": bmad_id,
        "github_number": number,
        "github_url": "https://github.com/{}/issues/{}".format(REPOSITORY, number),
        "title": "A {} titled — with a dash".format(kind),
        "type": kind,
        "native_type": sync.NATIVE_TYPE[kind],
        "artifact_path": "_bmad-output/implementation-artifacts/{}.md".format(bmad_id),
        "parent_bmad_id": parent[0] if parent else None,
        "parent_github_number": parent[1] if parent else None,
        "lifecycle": "active",
        "provenance": provenance,
    }


def manifest_for(items):
    next_ids = {kind: 1 for kind in sync.KINDS}
    for item in items:
        next_ids[item["type"]] = max(next_ids[item["type"]], int(item["bmad_id"][-3:]) + 1)
    return {
        "schema_version": 2,
        "repository": REPOSITORY,
        "native_type_projection": "labels-only",
        "generated_at": "2026-09-23",
        "next_ids": next_ids,
        "items": items,
    }


def fill(text):
    """Replace every placeholder with prose, as an author would."""
    return re.sub(r"<!-- fill: .*?-->", "Written content.", text, flags=re.DOTALL)


class TempRoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
        patcher = mock.patch.object(sync, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def write(self, item, text):
        path = self.root / item["artifact_path"]
        path.write_bytes(text.encode("utf-8"))
        return path


class RenderingTests(unittest.TestCase):
    def test_each_kind_renders_its_own_skeleton_under_the_managed_block(self):
        for kind in sync.KINDS:
            with self.subTest(kind=kind):
                item = item_for(kind, parent=("AH-E001", 93))
                text = sync.render_artifact(item)
                head_end = sync.sync_layout(text)
                self.assertIsNotNone(head_end)
                head, body = text[:head_end], text[head_end:]
                self.assertIn("# {} — {}".format(item["bmad_id"], item["title"]), head)
                self.assertLess(head.index("\n# "), head.index(sync.SYNC_BEGIN))
                self.assertIn("- **GitHub issue:** [#1]({})".format(item["github_url"]), head)
                self.assertIn("- **Primary parent:** [AH-E001](https://github.com/{}/issues/93)".format(REPOSITORY), head)
                self.assertIn("- **State:** active", head)
                self.assertIn(sync.AUTHORITY, head)
                self.assertEqual(body, "\n\n" + sync.story_template(kind))
                sections = sync.markdown_sections(body)
                for name in sync.REQUIRED[kind]:
                    self.assertIn(name.casefold(), sections)
                    self.assertIn("<!-- fill: ", sections[name.casefold()])

    def test_frontmatter_keeps_the_nine_audited_fields_and_updated(self):
        text = sync.render_artifact(item_for("story"))
        frontmatter = text.split("---\n")[1]
        self.assertEqual(
            [line.split(":")[0] for line in frontmatter.splitlines()],
            ["bmad_id", "type", "title", "lifecycle", "provenance", "github_issue",
             "github_issue_url", "parent_bmad_id", "parent_github_issue", "updated"],
        )

    def test_kind_specific_sections(self):
        expected = {
            "story": ["Story", "Context and value", "Acceptance criteria", "Design", "Tasks", "Dev notes",
                      "Dev agent record", "Review findings", "Change log"],
            "bug": ["Reproduction", "Root cause", "Acceptance criteria", "Design", "Regression test", "Tasks",
                    "Dev notes", "Dev agent record", "Review findings", "Change log"],
            "spike": ["Question", "Experiment", "Exit criterion", "Result", "Decision", "Dev notes", "Change log"],
            "decision": ["Context", "Options", "Decision", "Consequences", "References"],
            "epic": ["Goal", "Scope and requirement coverage", "Children", "Architecture slice", "Sequencing",
                     "Exit criteria"],
            "task": ["Goal", "Acceptance criteria", "Tasks", "Dev notes", "Dev agent record", "Change log"],
        }
        expected["chore"] = expected["task"]
        for kind, names in expected.items():
            with self.subTest(kind=kind):
                headings = re.findall(r"(?m)^## (.+)$", sync.story_template(kind))
                self.assertEqual(headings, names)

    def test_reconstructed_provenance_keeps_its_disclaimer(self):
        text = sync.render_artifact(item_for("story", provenance="reconstructed"))
        head = text[:sync.sync_layout(text)]
        self.assertIn("does not imply that a BMad artifact existed", head)

    def test_write_manifest_renders_new_artifacts_typed(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sync, "ROOT", Path(temp)):
            item = item_for("spike")
            sync.write_manifest(manifest_for([item]))
            text = (Path(temp) / item["artifact_path"]).read_text(encoding="utf-8")
            self.assertEqual(sync.audit_manifest(manifest_for([item])), [])
        self.assertIn("## Exit criterion", text)
        self.assertEqual(text.count(sync.SYNC_BEGIN), 1)


class MarkerTests(TempRoot):
    def test_missing_or_duplicated_markers_are_refused_everywhere(self):
        item = item_for("story")
        good = sync.render_artifact(item)
        broken = {
            "missing end": good.replace(sync.SYNC_END, ""),
            "missing begin": good.replace(sync.SYNC_BEGIN, ""),
            "duplicated begin": good.replace(sync.SYNC_END, sync.SYNC_BEGIN + "\n" + sync.SYNC_END),
            "duplicated block": good + "\n" + sync.SYNC_BEGIN + "\n" + sync.SYNC_END + "\n",
            "reversed": good.replace(sync.SYNC_BEGIN, "@@").replace(sync.SYNC_END, sync.SYNC_BEGIN).replace(
                "@@", sync.SYNC_END
            ),
        }
        manifest = manifest_for([item])
        live = [{"number": 1, "title": "renamed", "state": "open", "parent_issue_url": None}]
        for label, text in broken.items():
            with self.subTest(label):
                path = self.write(item, text)
                with self.assertRaisesRegex(RuntimeError, "missing or duplicated"):
                    sync.sync_layout(text)
                with self.assertRaisesRegex(RuntimeError, "markers are missing or duplicated.*AH-S001"):
                    sync.refresh(manifest, live)
                self.assertEqual(path.read_bytes().decode("utf-8"), text)
                self.assertIn("AH-S001: bmad-sync markers are missing or duplicated", sync.audit_manifest(manifest))
                self.assertEqual(sync.depth_findings(manifest, 1)[0], ["AH-S001 #1: bmad-sync markers are missing or duplicated"])
                self.assertEqual(sync.upgrade(manifest, check=True)[0][1], "refuse")

    def test_a_file_with_no_markers_is_a_legacy_stub(self):
        self.assertIsNone(sync.sync_layout(sync.render_legacy_stub(item_for("story"))))


class UpgradeTests(TempRoot):
    def setUp(self):
        super().setUp()
        self.bug = item_for("bug", 8, parent=("AH-E004", 189))
        self.chore = item_for("chore", 7)
        self.parent = item_for("epic", 189)
        self.parent["bmad_id"] = "AH-E004"
        self.parent["artifact_path"] = "_bmad-output/implementation-artifacts/AH-E004.md"
        self.manifest = manifest_for([self.bug, self.chore, self.parent])
        stub = sync.render_legacy_stub(self.bug).replace(
            re.search(r'updated: ".*"', sync.render_legacy_stub(self.bug)).group(0), 'updated: "2026-09-19"'
        )
        self.bug_path = self.write(self.bug, stub + AMENDMENT)
        self.chore_path = self.write(self.chore, sync.render_legacy_stub(self.chore))
        self.write(self.parent, sync.render_legacy_stub(self.parent))
        self.assertEqual(sync.audit_manifest(self.manifest), [])

    def test_upgrade_carries_amendments_verbatim_and_keeps_the_linkage(self):
        before = self.bug_path.read_bytes().decode("utf-8")
        report = dict((bmad_id, status) for bmad_id, status, _ in sync.upgrade(self.manifest))
        self.assertEqual(report, {"AH-B008": "convert", "AH-C007": "convert", "AH-E004": "convert"})
        after = self.bug_path.read_bytes().decode("utf-8")
        self.assertTrue(after.endswith(AMENDMENT))
        self.assertTrue(after.startswith("---\n"))
        body = after[sync.sync_layout(after):]
        self.assertEqual(body, "\n\n" + sync.story_template("bug") + AMENDMENT)
        for key in ("bmad_id", "type", "title", "lifecycle", "provenance", "github_issue",
                    "github_issue_url", "parent_bmad_id", "parent_github_issue"):
            self.assertEqual(sync.frontmatter_value(after, key), sync.frontmatter_value(before, key))
        self.assertIn("- **Primary parent:** [AH-E004]", after)
        self.assertIn("committed BMad planning system", after)
        self.assertEqual(sync.audit_manifest(self.manifest), [])
        self.assertIn("## Goal", self.chore_path.read_text(encoding="utf-8"))

    def test_upgrade_is_idempotent(self):
        sync.upgrade(self.manifest)
        first = {path: path.read_bytes() for path in (self.bug_path, self.chore_path)}
        report = sync.upgrade(self.manifest)
        self.assertEqual({status for _, status, _ in report}, {"current"})
        self.assertEqual({path: path.read_bytes() for path in first}, first)

    def test_check_reports_and_writes_nothing(self):
        before = self.bug_path.read_bytes()
        report = sync.upgrade(self.manifest, check=True)
        self.assertIn(("AH-B008", "convert", "converts without loss, carrying 4 line(s) verbatim"), report)
        self.assertEqual(self.bug_path.read_bytes(), before)

    def test_a_hand_edited_stub_is_refused_and_nothing_is_written(self):
        chore_before = self.chore_path.read_bytes()
        edited = self.bug_path.read_text(encoding="utf-8").replace("owns scope", "owns the scope")
        self.write(self.bug, edited)
        report = sync.upgrade(self.manifest)
        self.assertEqual(dict((bmad_id, status) for bmad_id, status, _ in report)["AH-B008"], "refuse")
        self.assertEqual(self.chore_path.read_bytes(), chore_before)

    def test_ids_select_a_batch_and_an_unknown_id_is_refused(self):
        report = sync.upgrade(self.manifest, ["AH-C007"])
        self.assertEqual([bmad_id for bmad_id, _, _ in report], ["AH-C007"])
        self.assertNotIn(sync.SYNC_BEGIN, self.bug_path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(RuntimeError, "not in the issue map: AH-S999"):
            sync.upgrade(self.manifest, ["AH-S999"])

    def test_refresh_after_upgrade_preserves_the_carried_amendment(self):
        sync.upgrade(self.manifest)
        live = [
            {"number": 8, "title": "renamed", "state": "closed", "parent_issue_url": None},
        ]
        with mock.patch.object(sync, "write_manifest"):
            self.assertEqual(sync.refresh(self.manifest, live), ["AH-B008"])
        after = self.bug_path.read_text(encoding="utf-8")
        self.assertTrue(after.endswith(AMENDMENT))
        self.assertIn("# AH-B008 — renamed", after)

    def test_cli_check_exits_zero_and_names_each_conversion(self):
        with mock.patch.object(sync, "load_manifest", return_value=self.manifest), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(sync.main(["upgrade", "--check"]), 0)
        self.assertIn("AH-B008: converts without loss", out.getvalue())
        self.assertIn("upgrade --check: 3 convertible, 0 already current, 0 refused", out.getvalue())
        self.assertNotIn(sync.SYNC_BEGIN, self.bug_path.read_text(encoding="utf-8"))


class RealCorpusTests(unittest.TestCase):
    def test_every_existing_artifact_converts_without_loss(self):
        manifest = sync.load_manifest()
        with mock.patch.object(sync, "write_text_atomic") as write:
            report = sync.upgrade(manifest, check=True)
        write.assert_not_called()
        refused = [(bmad_id, reason) for bmad_id, status, reason in report if status == "refuse"]
        self.assertEqual(refused, [])
        self.assertEqual(len(report), len(manifest["items"]))


class DepthTests(TempRoot):
    def check(self, item, text):
        self.write(item, text)
        return sync.depth_findings(manifest_for([item]), item["github_number"])

    def test_a_skeleton_fails_for_every_required_section_of_each_kind(self):
        for kind in sync.KINDS:
            with self.subTest(kind=kind):
                item = item_for(kind)
                findings, notices = self.check(item, sync.render_artifact(item))
                self.assertEqual(notices, [])
                self.assertEqual(
                    findings,
                    ["{} #1: required {} section '{}' is unfilled".format(item["bmad_id"], kind, name)
                     for name in sync.REQUIRED[kind]],
                )

    def test_a_filled_story_passes_for_each_kind(self):
        for kind in sync.KINDS:
            with self.subTest(kind=kind):
                item = item_for(kind)
                text = sync.render_artifact(item)
                head_end = sync.sync_layout(text)
                self.assertEqual(self.check(item, text[:head_end] + fill(text[head_end:])), ([], []))

    def test_only_required_sections_decide(self):
        item = item_for("story")
        text = sync.render_artifact(item)
        head_end = sync.sync_layout(text)
        body = text[head_end:]
        for name in sync.REQUIRED["story"]:
            body = re.sub(r"(## {}\n\n)<!-- fill: .*?-->".format(re.escape(name)), r"\1Content.", body,
                          count=1, flags=re.DOTALL)
        body = re.sub(r"(### [^\n]+\n\n)<!-- fill: .*?-->", r"\1Content.", body, flags=re.DOTALL)
        self.assertEqual(self.check(item, text[:head_end] + body), ([], []))

    def test_subheadings_and_a_deleted_section_do_not_count_as_content(self):
        item = item_for("story")
        text = sync.render_artifact(item)
        head_end = sync.sync_layout(text)
        body = fill(text[head_end:])
        body = re.sub(r"## Design\n.*?(?=\n## Tasks)", "## Design\n\n### Approach\n\n#### Detail\n", body, flags=re.DOTALL)
        body = re.sub(r"## Story\n.*?(?=\n## Context)", "", body, flags=re.DOTALL)
        findings, _ = self.check(item, text[:head_end] + body)
        self.assertEqual(findings, [
            "AH-S001 #1: required story section 'Story' is missing",
            "AH-S001 #1: required story section 'Design' is unfilled",
        ])

    def test_a_heading_inside_fenced_code_is_not_a_section(self):
        item = item_for("task")
        text = sync.render_artifact(item)
        head_end = sync.sync_layout(text)
        body = "\n\n## Goal\n\n```text\n## Acceptance criteria\n## Tasks\n```\n"
        findings, _ = self.check(item, text[:head_end] + body)
        self.assertEqual(findings, [
            "AH-T001 #1: required task section 'Acceptance criteria' is missing",
            "AH-T001 #1: required task section 'Tasks' is missing",
        ])

    def test_a_legacy_stub_passes_with_a_notice(self):
        item = item_for("story", 206)
        findings, notices = self.check(item, sync.render_legacy_stub(item) + AMENDMENT)
        self.assertEqual(findings, [])
        self.assertEqual(notices, [
            "AH-S206 #206: legacy stub, not depth-checked until upgraded "
            "(python3 scripts/bmad_issue_sync.py upgrade --id AH-S206)"
        ])

    def test_an_unmapped_or_missing_story_fails(self):
        item = item_for("story")
        self.assertEqual(sync.depth_findings(manifest_for([item]), 2), (["#2: no BMad ID; run reserve"], []))
        self.assertEqual(
            sync.depth_findings(manifest_for([item]), 1),
            (["AH-S001 #1: missing artifact _bmad-output/implementation-artifacts/AH-S001.md"], []),
        )

    def test_cli_exit_codes(self):
        item = item_for("bug")
        manifest = manifest_for([item])
        self.write(item, sync.render_artifact(item))
        with mock.patch.object(sync, "load_manifest", return_value=manifest), mock.patch.object(
            sync, "fetch_issues"
        ) as fetch:
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sync.main(["audit", "--delivery", "1"]), 1)
            self.assertIn("depth: issue #1, 5 finding(s)", out.getvalue())
            self.write(item, fill(sync.render_artifact(item)))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sync.main(["audit", "--delivery", "1"]), 0)
            with self.assertRaisesRegex(RuntimeError, "--delivery is a local check"):
                sync.main(["audit", "--delivery", "1", "--live"])
        fetch.assert_not_called()


def copy_tool(root):
    """A self-contained repository holding the sync tool, so it can run as CI runs it."""
    shutil.copytree(str(REPO / "scripts" / "bmad_story_templates"), str(root / "scripts" / "bmad_story_templates"))
    shutil.copy(str(REPO / "scripts" / "bmad_issue_sync.py"), str(root / "scripts" / "bmad_issue_sync.py"))
    (root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
    return root / "scripts" / "bmad_issue_sync.py"


class CliBoundaryTests(unittest.TestCase):
    def test_a_malformed_manifest_is_reported_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            tool = copy_tool(Path(temp))
            (Path(temp) / "_bmad-output" / "issue-map.json").write_text(
                json.dumps({"items": [{"bmad_id": "AH-S001"}]}), encoding="utf-8"
            )
            result = subprocess.run([sys.executable, str(tool), "audit"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("bmad issue sync: KeyError", result.stderr)


class OwnershipWiringTests(unittest.TestCase):
    def repository(self, temp, text_for):
        root = Path(temp)
        tool = copy_tool(root)
        item = item_for("story", 10)
        (root / "_bmad-output" / "issue-map.json").write_text(json.dumps(manifest_for([item])), encoding="utf-8")
        (root / item["artifact_path"]).write_text(text_for(item), encoding="utf-8")
        return tool

    def test_a_placeholder_story_fails_and_a_filled_one_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            tool = self.repository(temp, sync.render_artifact)
            with self.assertRaisesRegex(ValueError, "(?s)#10 is not ready.*section 'Story' is unfilled"):
                checker.require_story_depth(10, tool)
        with tempfile.TemporaryDirectory() as temp:
            tool = self.repository(temp, lambda item: fill(sync.render_artifact(item)))
            self.assertIn("depth: issue #10, 0 finding(s)", checker.require_story_depth(10, tool))

    def test_a_legacy_stub_passes_with_its_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            tool = self.repository(temp, sync.render_legacy_stub)
            self.assertIn("notice: AH-S010 #10: legacy stub", checker.require_story_depth(10, tool))

    def test_the_real_tool_is_what_the_check_runs(self):
        self.assertEqual(checker.SYNC_TOOL, REPO / "scripts" / "bmad_issue_sync.py")
        self.assertTrue(checker.SYNC_TOOL.is_file())

    def run_main(self, env, depth):
        page = {"data": {"repository": {"pullRequests": {"nodes": [
            {"number": 7, "state": "OPEN", "merged": False, "closingIssuesReferences": {
                "totalCount": 1, "nodes": [{"number": 10, "repository": {"nameWithOwner": "owner/repo"}}]}},
        ]}}}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "issue-map.json"
            path.write_text(json.dumps({"items": [{"github_number": 10, "bmad_id": "AH-S010"}]}))
            with mock.patch.object(checker, "ISSUE_MAP", path), mock.patch.object(
                checker.subprocess, "run", return_value=mock.Mock(stdout=json.dumps([page]))
            ), mock.patch.object(checker, "require_story_depth", side_effect=depth) as called, mock.patch.dict(
                os.environ, dict(env, GITHUB_REPOSITORY="owner/repo"), clear=False
            ), redirect_stdout(io.StringIO()) as out:
                checker.main()
        return called, out.getvalue()

    def test_main_checks_the_delivery_story_on_a_pull_request_and_in_the_merge_queue(self):
        envs = (
            {"PR_NUMBER": "7", "MERGE_GROUP_HEAD_REF": ""},
            {"PR_NUMBER": "", "MERGE_GROUP_HEAD_REF": "refs/heads/gh-readonly-queue/main/pr-7-0123abcd"},
        )
        for env in envs:
            with self.subTest(env=env):
                called, out = self.run_main(env, lambda issue: "depth: issue #{}, 0 finding(s)".format(issue))
                called.assert_called_once_with(10)
                self.assertIn("depth: issue #10, 0 finding(s)", out)
                self.assertIn("Issue ownership verified: #10 (AH-S010)", out)

    def test_main_fails_when_the_story_is_not_ready(self):
        with self.assertRaisesRegex(ValueError, "not ready"):
            self.run_main({"PR_NUMBER": "7"}, ValueError("The story for delivery issue #10 is not ready"))


if __name__ == "__main__":
    unittest.main()
