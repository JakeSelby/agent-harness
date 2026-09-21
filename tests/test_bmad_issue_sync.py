# SPDX-License-Identifier: MIT
"""Tests for BMad/GitHub traceability."""

import importlib.util
import io
import json
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bmad_issue_sync", REPO / "scripts" / "bmad_issue_sync.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def issue(number, title, state="open", labels=None):
    return {
        "id": number * 10,
        "number": number,
        "title": title,
        "state": state,
        "body": "Original body",
        "html_url": "https://github.com/JakeSelby/agent-harness/issues/{}".format(number),
        "labels": [{"name": label} for label in (labels or [])],
        "type": None,
        "parent_issue_url": None,
    }


class ClassificationTests(unittest.TestCase):
    def test_types_are_stable_and_hierarchy_is_separate(self):
        manifest = sync.build_manifest(
            [
                issue(52, "docs(bmad): decide the builder-routing follow-up", state="closed", labels=["docs"]),
                issue(80, "fix(installer): install crashes", state="closed", labels=["bug"]),
                issue(93, "Deliver a provider-agnostic harness"),
                issue(94, "Unify primitive contracts"),
                issue(141, "Preserve a deferred experiment"),
            ],
            "JakeSelby/agent-harness",
        )
        items = {item["github_number"]: item for item in manifest["items"]}
        self.assertEqual(items[52]["bmad_id"], "AH-D001")
        self.assertEqual(items[80]["bmad_id"], "AH-B001")
        self.assertEqual(items[93]["bmad_id"], "AH-E001")
        self.assertEqual(items[94]["parent_bmad_id"], "AH-E001")
        self.assertEqual(items[141]["bmad_id"], "AH-SP001")

    def test_completed_preexisting_issue_is_marked_reconstructed(self):
        item = sync.build_manifest([issue(1, "feat: first", state="closed")], "owner/repo")["items"][0]
        self.assertEqual(item["lifecycle"], "completed")
        self.assertEqual(item["provenance"], "reconstructed")

    def test_mapping_is_deterministic_when_live_issues_are_unsorted(self):
        forward = sync.build_manifest([issue(1, "first"), issue(2, "second")], "owner/repo")
        reverse = sync.build_manifest([issue(2, "second"), issue(1, "first")], "owner/repo")
        self.assertEqual(forward, reverse)


class PlanningBlockTests(unittest.TestCase):
    def setUp(self):
        self.item = sync.build_manifest([issue(1, "feat: first")], "JakeSelby/agent-harness")["items"][0]

    def test_upsert_preserves_original_body_and_is_idempotent(self):
        block = sync.planning_block(self.item, "JakeSelby/agent-harness")
        first = sync.upsert_planning_block("Original body", block)
        second = sync.upsert_planning_block(first, block)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("Original body"))
        self.assertEqual(first.count(sync.BEGIN), 1)
        self.assertIn("blob/main/" + self.item["artifact_path"], first)

    def test_upsert_collapses_complete_duplicates_without_deleting_prose(self):
        block = sync.planning_block(self.item, "JakeSelby/agent-harness")
        body = "Before\n\n{}\n\nBetween\n\n{}\n\nAfter".format(block, block)
        result = sync.upsert_planning_block(body, block)
        self.assertEqual(result.count(sync.BEGIN), 1)
        self.assertEqual(result.count(sync.END), 1)
        self.assertIn("Before", result)
        self.assertIn("Between", result)
        self.assertIn("After", result)

    def test_upsert_refuses_unmatched_or_nested_fences(self):
        block = sync.planning_block(self.item, "JakeSelby/agent-harness")
        malformed = [
            "Prose\n{}".format(sync.BEGIN),
            "Prose\n{}".format(sync.END),
            "{}\n{}\n{}\n{}".format(sync.BEGIN, sync.BEGIN, sync.END, sync.END),
        ]
        for body in malformed:
            with self.subTest(body=body):
                with self.assertRaisesRegex(RuntimeError, "malformed BMad Planning fences"):
                    sync.upsert_planning_block(body, block)


class AuditTests(unittest.TestCase):
    def test_audit_requires_an_explicit_native_type_projection_mode(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        manifest["native_type_projection"] = "unknown"
        findings = sync.audit_manifest(manifest)
        self.assertIn(
            "native_type_projection must be labels-only or native-and-labels",
            findings,
        )

    def test_audit_accepts_bidirectional_mapping_and_rejects_duplicate_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
            old_root = sync.ROOT
            try:
                sync.ROOT = root
                path = root / manifest["items"][0]["artifact_path"]
                path.parent.mkdir(parents=True)
                path.write_text(sync.render_artifact(manifest["items"][0]), encoding="utf-8")
                self.assertEqual(sync.audit_manifest(manifest), [])
                manifest["items"].append(dict(manifest["items"][0]))
                self.assertTrue(any("duplicate BMad ID" in finding for finding in sync.audit_manifest(manifest)))
            finally:
                sync.ROOT = old_root

    def test_audit_names_missing_broken_parent_and_reverse_link_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = sync.build_manifest(
                [issue(93, "Epic"), issue(94, "Child"), issue(101, "Missing")], "owner/repo"
            )
            old_root = sync.ROOT
            try:
                sync.ROOT = root
                first = root / manifest["items"][0]["artifact_path"]
                first.parent.mkdir(parents=True)
                first.write_text(sync.render_artifact(manifest["items"][0]), encoding="utf-8")
                child = root / manifest["items"][1]["artifact_path"]
                child.write_text(sync.render_artifact(manifest["items"][1]).replace(
                    'github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/94"',
                    'github_issue_url: "https://github.com/JakeSelby/agent-harness/issues/999"',
                ), encoding="utf-8")
                manifest["items"][1]["parent_bmad_id"] = None
                findings = sync.audit_manifest(manifest)
            finally:
                sync.ROOT = old_root
        self.assertTrue(any("parent mapping is incomplete" in finding for finding in findings))
        self.assertTrue(any("artifact github_issue_url does not match" in finding for finding in findings))
        self.assertTrue(any("missing artifact" in finding for finding in findings))

    def test_audit_checks_every_manifest_owned_artifact_field(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        fields = (
            "bmad_id", "type", "title", "lifecycle", "provenance", "github_issue",
            "github_issue_url", "parent_bmad_id", "parent_github_issue",
        )
        with tempfile.TemporaryDirectory() as temp:
            old_root = sync.ROOT
            try:
                sync.ROOT = Path(temp)
                path = sync.ROOT / manifest["items"][0]["artifact_path"]
                path.parent.mkdir(parents=True)
                rendered = sync.render_artifact(manifest["items"][0])
                for field in fields:
                    with self.subTest(field=field):
                        changed = re.sub(
                            r"^{}: .*$".format(field),
                            '{}: "wrong"'.format(field),
                            rendered,
                            count=1,
                            flags=re.MULTILINE,
                        )
                        path.write_text(changed, encoding="utf-8")
                        findings = sync.audit_manifest(manifest)
                        self.assertTrue(any(
                            "artifact {} does not match".format(field) in finding
                            for finding in findings
                        ))
                path.write_text(rendered.replace("parent_bmad_id: null\n", ""), encoding="utf-8")
                findings = sync.audit_manifest(manifest)
                self.assertTrue(any(
                    "artifact parent_bmad_id does not match" in finding for finding in findings
                ))
            finally:
                sync.ROOT = old_root

    def test_plan_reports_each_missing_remote_projection(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        actions = sync.planned_actions(manifest, [issue(1, "feat: first")])
        self.assertEqual(actions[0]["changes"], ["planning-block", "type-label"])

    def test_plan_includes_native_type_only_when_the_repository_supports_it(self):
        manifest = sync.build_manifest(
            [issue(1, "feat: first")], "org/repo", native_type_projection="native-and-labels"
        )
        actions = sync.planned_actions(manifest, [issue(1, "feat: first")])
        self.assertEqual(actions[0]["changes"], ["planning-block", "native-type", "type-label"])

    def test_plan_replaces_stale_owned_type_labels(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        live = issue(1, "feat: first", labels=["keep-me", "type::bug", "type::story"])
        live["body"] = sync.planning_block(manifest["items"][0], "owner/repo")
        live["type"] = {"name": "Feature"}
        actions = sync.planned_actions(manifest, [live])
        self.assertEqual(actions, [{"issue": 1, "changes": ["type-label"]}])

    def test_plan_reports_missing_issue_without_mutation(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        self.assertEqual(sync.planned_actions(manifest, []), [{"issue": 1, "action": "missing"}])


class ApplyTests(unittest.TestCase):
    def test_apply_preserves_prose_and_skips_an_already_projected_issue(self):
        manifest = sync.build_manifest(
            [issue(1, "feat: first", labels=["keep-me", "type::bug"])], "owner/repo"
        )
        original = issue(1, "feat: first", labels=["keep-me", "type::bug"])
        projected = issue(1, "feat: first", labels=["keep-me", "type::story"])
        projected["body"] = sync.upsert_planning_block(
            original["body"], sync.planning_block(manifest["items"][0], "owner/repo")
        )
        projected["type"] = None
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", side_effect=[[original], [projected]]), mock.patch.object(
            sync, "gh_command"
        ), mock.patch.object(sync, "gh_json") as gh:
            sync.apply_manifest(manifest)
        payload = gh.call_args.args[1]
        self.assertTrue(payload["body"].startswith("Original body"))
        self.assertEqual(payload["labels"], ["keep-me", "type::story"])
        self.assertNotIn("type", payload)

        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", side_effect=[[projected], [projected]]), mock.patch.object(
            sync, "gh_command"
        ), mock.patch.object(sync, "gh_json") as gh:
            sync.apply_manifest(manifest)
        gh.assert_not_called()

    def test_apply_sets_native_type_when_the_manifest_enables_projection(self):
        manifest = sync.build_manifest(
            [issue(1, "feat: first")], "org/repo", native_type_projection="native-and-labels"
        )
        original = issue(1, "feat: first")
        projected = issue(1, "feat: first", labels=["type::story"])
        projected["body"] = sync.upsert_planning_block(
            original["body"], sync.planning_block(manifest["items"][0], "org/repo")
        )
        projected["type"] = {"name": "Feature"}
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", side_effect=[[original], [projected]]), mock.patch.object(
            sync, "gh_command"
        ), mock.patch.object(sync, "gh_json") as gh:
            sync.apply_manifest(manifest)
        self.assertEqual(gh.call_args.args[1]["type"], "Feature")

    def test_apply_refuses_missing_remote_artifact_before_mutation(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[manifest["items"][0]["artifact_path"]]
        ), mock.patch.object(sync, "fetch_issues") as fetch, mock.patch.object(
            sync.subprocess, "run"
        ) as run, mock.patch.object(sync, "gh_json") as gh:
            with self.assertRaisesRegex(RuntimeError, "artifacts are not on main"):
                sync.apply_manifest(manifest)
        fetch.assert_not_called()
        run.assert_not_called()
        gh.assert_not_called()

    def test_apply_refuses_missing_issue_before_mutation(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", return_value=[]), mock.patch.object(
            sync.subprocess, "run"
        ) as run, mock.patch.object(sync, "gh_json") as gh:
            with self.assertRaisesRegex(RuntimeError, "mapped issues were not found"):
                sync.apply_manifest(manifest)
        run.assert_not_called()
        gh.assert_not_called()

    def test_apply_refuses_malformed_fences_before_mutation(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        malformed = issue(1, "feat: first")
        malformed["body"] = "Original body\n\n{}".format(sync.BEGIN)
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", return_value=[malformed]), mock.patch.object(
            sync, "gh_command"
        ) as gh:
            with self.assertRaisesRegex(RuntimeError, "malformed BMad Planning fences"):
                sync.apply_manifest(manifest)
        gh.assert_not_called()

    def test_apply_restores_prior_parent_when_reparenting_fails(self):
        manifest = sync.build_manifest([issue(93, "Epic"), issue(94, "Child")], "owner/repo")
        live = []
        for item in manifest["items"]:
            current = issue(item["github_number"], item["title"], labels=["type::{}".format(item["type"])])
            current["body"] = sync.planning_block(item, "owner/repo")
            current["type"] = {"name": item["native_type"]}
            live.append(current)
        reparented = [dict(value) for value in live]
        reparented[1]["parent_issue_url"] = "https://api.github.com/repos/owner/repo/issues/52"
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", side_effect=[live, reparented]), mock.patch.object(
            sync, "gh_command"
        ), mock.patch.object(
            sync, "gh_json", side_effect=[None, RuntimeError("add failed"), None]
        ) as gh:
            with self.assertRaisesRegex(RuntimeError, "add failed"):
                sync.apply_manifest(manifest)
        endpoints = [call.args[0][-3] for call in gh.call_args_list]
        self.assertIn("repos/owner/repo/issues/52/sub_issue", endpoints[0])
        self.assertIn("repos/owner/repo/issues/93/sub_issues", endpoints[1])
        self.assertIn("repos/owner/repo/issues/52/sub_issues", endpoints[2])

    def test_label_creation_failure_uses_runtime_error_boundary(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        failure = subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="label failed")
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "verify_remote_artifacts", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", return_value=[issue(1, "feat: first")]), mock.patch.object(
            sync.subprocess, "run", return_value=failure
        ):
            with self.assertRaisesRegex(RuntimeError, "label failed"):
                sync.apply_manifest(manifest)


class RemoteArtifactTests(unittest.TestCase):
    def test_remote_tree_distinguishes_present_and_missing_artifacts(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        artifact = manifest["items"][0]["artifact_path"]
        with mock.patch.object(sync, "gh_json", return_value={
            "truncated": False, "tree": [{"path": artifact}],
        }):
            self.assertEqual(sync.verify_remote_artifacts(manifest), [])
        with mock.patch.object(sync, "gh_json", return_value={"truncated": False, "tree": []}):
            self.assertEqual(sync.verify_remote_artifacts(manifest), [artifact])

    def test_remote_tree_refuses_truncated_response(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with mock.patch.object(sync, "gh_json", return_value={"truncated": True, "tree": []}):
            with self.assertRaisesRegex(RuntimeError, "truncated main tree"):
                sync.verify_remote_artifacts(manifest)


class GitHubCommandTests(unittest.TestCase):
    def test_timeout_is_converted_to_runtime_error(self):
        timeout = subprocess.TimeoutExpired(["gh", "api"], sync.GH_TIMEOUT_SECONDS)
        with mock.patch.object(sync.subprocess, "run", side_effect=timeout) as run:
            with self.assertRaisesRegex(RuntimeError, "timed out after 30 seconds"):
                sync.gh_command(["api", "repos/owner/repo"])
        self.assertEqual(run.call_args.kwargs["timeout"], sync.GH_TIMEOUT_SECONDS)


class CliTests(unittest.TestCase):
    def test_repo_override_belongs_to_bootstrap_only(self):
        map_path = mock.Mock()
        map_path.exists.return_value = False
        with mock.patch.object(sync, "MAP_PATH", map_path), mock.patch.object(
            sync, "fetch_issues", return_value=[]
        ) as fetch, mock.patch.object(sync, "write_manifest") as write:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sync.main([
                    "bootstrap", "--repo", "owner/repo",
                    "--native-type-projection", "native-and-labels",
                ]), 0)
        fetch.assert_called_once_with("owner/repo")
        self.assertEqual(write.call_args.args[0]["native_type_projection"], "native-and-labels")
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                sync.main(["plan", "--repo", "owner/repo"])

    def test_plan_rejects_a_malformed_projection_before_fetching(self):
        manifest = sync.build_manifest([], "owner/repo")
        manifest["native_type_projection"] = "unknown"
        with mock.patch.object(sync, "load_manifest", return_value=manifest), mock.patch.object(
            sync, "audit_manifest", return_value=["invalid projection"]
        ), mock.patch.object(sync, "fetch_issues") as fetch, redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "invalid projection"):
                sync.main(["plan"])
        fetch.assert_not_called()

    def test_schema_one_manifest_defaults_to_the_original_native_projection(self):
        manifest = sync.build_manifest([], "owner/repo")
        manifest["schema_version"] = 1
        manifest.pop("native_type_projection")
        self.assertEqual(sync.projection_mode(manifest), "native-and-labels")


class ReserveTests(unittest.TestCase):
    def test_reserve_uses_next_id_without_recycling(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sync, "ROOT", Path(temp)), mock.patch.object(
            sync, "audit_manifest", return_value=[]
        ), mock.patch.object(
            sync, "fetch_issues", return_value=[issue(1, "feat: first"), issue(2, "feat: second")]
        ), mock.patch.object(sync, "write_manifest"):
            item = sync.reserve(manifest, "owner/repo", 2, "story", None)
        self.assertEqual(item["bmad_id"], "AH-S002")
        self.assertEqual(manifest["next_ids"]["story"], 3)

    def test_reserve_refuses_duplicate_and_missing_issue(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with self.assertRaisesRegex(RuntimeError, "already has a BMad ID"):
            sync.reserve(manifest, "owner/repo", 1, "story", None)
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "fetch_issues", return_value=[]
        ):
            with self.assertRaisesRegex(RuntimeError, "was not found"):
                sync.reserve(manifest, "owner/repo", 2, "story", None)

    def test_reserve_refuses_parent_without_bmad_id(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "fetch_issues", return_value=[issue(2, "feat: second")]
        ):
            with self.assertRaisesRegex(RuntimeError, "parent issue #99 does not have a BMad ID"):
                sync.reserve(manifest, "owner/repo", 2, "story", 99)

    def test_reserve_audits_before_fetching_or_allocating(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with mock.patch.object(sync, "audit_manifest", return_value=["broken mapping"]), mock.patch.object(
            sync, "fetch_issues"
        ) as fetch:
            with self.assertRaisesRegex(RuntimeError, "broken mapping"):
                sync.reserve(manifest, "owner/repo", 2, "story", None)
        fetch.assert_not_called()
        self.assertEqual(manifest["next_ids"]["story"], 2)

    def test_reserve_refuses_invalid_or_exhausted_counter(self):
        for sequence in (0, 1000, "2"):
            manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
            manifest["next_ids"]["story"] = sequence
            with self.subTest(sequence=sequence), mock.patch.object(
                sync, "audit_manifest", return_value=[]
            ), mock.patch.object(sync, "fetch_issues", return_value=[issue(2, "feat: second")]):
                with self.assertRaisesRegex(RuntimeError, "ID sequence is invalid"):
                    sync.reserve(manifest, "owner/repo", 2, "story", None)

    def test_reserve_refuses_preexisting_target_artifact(self):
        manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sync, "ROOT", Path(temp)), mock.patch.object(
            sync, "audit_manifest", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", return_value=[issue(2, "feat: second")]):
            target = sync.ROOT / "_bmad-output/implementation-artifacts/AH-S002.md"
            target.parent.mkdir(parents=True)
            target.write_text("unrelated\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "target artifact already exists"):
                sync.reserve(manifest, "owner/repo", 2, "story", None)

    def test_manifest_write_preserves_existing_artifact_amendments(self):
        with tempfile.TemporaryDirectory() as temp:
            old_root = sync.ROOT
            try:
                sync.ROOT = Path(temp)
                manifest = sync.build_manifest([issue(1, "feat: first")], "owner/repo")
                path = sync.ROOT / manifest["items"][0]["artifact_path"]
                path.parent.mkdir(parents=True)
                path.write_text("durable amendment\n", encoding="utf-8")
                sync.write_manifest(manifest)
                self.assertEqual(path.read_text(encoding="utf-8"), "durable amendment\n")
            finally:
                sync.ROOT = old_root



class NewIssueTests(unittest.TestCase):
    def setUp(self):
        self.manifest = sync.build_manifest([issue(1, "Deliver the program")], "owner/repo")

    def test_new_files_a_typed_issue_then_reserves_it(self):
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "gh_json", return_value={"number": 2, "labels": [{"name": "type::bug"}]}
        ) as gh, mock.patch.object(sync, "reserve", return_value={"bmad_id": "AH-B001"}) as reserve:
            item = sync.create_issue(self.manifest, "owner/repo", "A defect", "Body", "bug", 1, 7)
        self.assertEqual(item["bmad_id"], "AH-B001")
        self.assertEqual(gh.call_args.args[0], ["api", "--method", "POST", "repos/owner/repo/issues", "--input", "-"])
        self.assertEqual(
            gh.call_args.kwargs["input_data"],
            {"title": "A defect", "body": "Body", "labels": ["type::bug"], "milestone": 7},
        )
        reserve.assert_called_once_with(self.manifest, "owner/repo", 2, "bug", 1)

    def test_new_files_nothing_when_the_map_or_parent_is_invalid(self):
        with mock.patch.object(sync, "audit_manifest", return_value=["broken mapping"]), mock.patch.object(
            sync, "gh_json"
        ) as gh:
            with self.assertRaisesRegex(RuntimeError, "broken mapping"):
                sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", None, None)
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(sync, "gh_json") as gh2:
            with self.assertRaisesRegex(RuntimeError, "parent issue #99 does not have a BMad ID"):
                sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", 99, None)
        gh.assert_not_called()
        gh2.assert_not_called()

    def test_failed_creation_reserves_nothing(self):
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "gh_json", side_effect=RuntimeError("HTTP 403")
        ), mock.patch.object(sync, "reserve") as reserve:
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", None, None)
        reserve.assert_not_called()

    def test_any_failure_after_filing_names_the_filed_issue(self):
        created = {"number": 2, "labels": [{"name": "type::story"}]}
        for failure in (RuntimeError("target artifact already exists"), KeyError("story"), OSError("disk full")):
            with self.subTest(failure=failure), mock.patch.object(
                sync, "audit_manifest", return_value=[]
            ), mock.patch.object(sync, "gh_json", return_value=created), mock.patch.object(
                sync, "reserve", side_effect=failure
            ):
                with self.assertRaisesRegex(RuntimeError, r"issue #2 was filed but not reserved.*reserve --issue 2"):
                    sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", None, None)

    def test_a_dropped_type_label_is_reported_and_reserves_nothing(self):
        with mock.patch.object(sync, "audit_manifest", return_value=[]), mock.patch.object(
            sync, "gh_json", return_value={"number": 2, "labels": []}
        ), mock.patch.object(sync, "reserve") as reserve:
            with self.assertRaisesRegex(RuntimeError, r"issue #2 was filed.*did not apply type::story"):
                sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", None, None)
        reserve.assert_not_called()

    def test_an_empty_github_response_is_reported(self):
        for created in (None, {}, {"number": "2"}):
            with self.subTest(created=created), mock.patch.object(
                sync, "audit_manifest", return_value=[]
            ), mock.patch.object(sync, "gh_json", return_value=created), mock.patch.object(sync, "reserve") as reserve:
                with self.assertRaisesRegex(RuntimeError, "did not return the new issue's number"):
                    sync.create_issue(self.manifest, "owner/repo", "Title", "Body", "story", None, None)
            reserve.assert_not_called()

    def test_cli_reads_the_body_from_a_file(self):
        with tempfile.TemporaryDirectory() as temp:
            body = Path(temp) / "body.md"
            body.write_text("## Problem\n", encoding="utf-8")
            with mock.patch.object(sync, "load_manifest", return_value=self.manifest), mock.patch.object(
                sync, "create_issue", return_value={"github_number": 2, "bmad_id": "AH-S002"}
            ) as create, redirect_stdout(io.StringIO()) as out:
                self.assertEqual(
                    sync.main(["new", "--title", "T", "--kind", "story", "--body-file", str(body), "--parent", "1"]), 0
                )
        create.assert_called_once_with(self.manifest, "owner/repo", "T", "## Problem\n", "story", 1, None)
        self.assertIn("filed #2 and reserved AH-S002", out.getvalue())


if __name__ == "__main__":
    unittest.main()
