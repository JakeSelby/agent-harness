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


class LiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.live = [issue(1, "feat: first"), issue(2, "feat: second", state="closed")]
        self.manifest = sync.build_manifest(self.live, "owner/repo")

    def projected(self, live_issue):
        item = next(i for i in self.manifest["items"] if i["github_number"] == live_issue["number"])
        live_issue["body"] = sync.upsert_planning_block(live_issue["body"], sync.planning_block(item, "owner/repo"))
        live_issue["labels"] = [{"name": "type::{}".format(item["type"])}]
        return live_issue

    def test_projected_and_current_mapping_has_no_findings(self):
        live = [self.projected(entry) for entry in self.live]
        self.assertEqual(sync.live_findings(self.manifest, live), ([], []))

    def test_open_to_completed_completed_to_active_and_title_drift(self):
        live = [self.projected(entry) for entry in self.live]
        live[0]["state"] = "closed"
        live[1]["state"] = "open"
        live[1]["title"] = "feat: renamed"
        findings, notices = sync.live_findings(self.manifest, live)
        self.assertEqual(notices, [])
        self.assertEqual(len(findings), 3)
        self.assertRegex(findings[0], r"#1: GitHub is closed but the manifest says active")
        self.assertRegex(findings[1], r"#2: title drift")
        self.assertRegex(findings[2], r"#2: GitHub is open but the manifest says completed")

    def test_lifecycle_drift_can_be_reported_without_failing(self):
        live = [self.projected(entry) for entry in self.live]
        live[0]["state"] = "closed"
        findings, notices = sync.live_findings(self.manifest, live, check_lifecycle=False)
        self.assertEqual(findings, [])
        self.assertEqual(len(notices), 1)

    def test_missing_issue_and_unprojected_issue_are_findings(self):
        findings, _ = sync.live_findings(self.manifest, [self.live[0]])
        self.assertIn("#1: projection drift (planning-block, type-label); run apply", findings)
        self.assertIn("#2: mapped issue was not found on GitHub", findings)

    def test_unmapped_issue_fails_once_accepted_and_waits_while_untriaged(self):
        live = [self.projected(entry) for entry in self.live]
        community = issue(3, "idea from a visitor")
        community["author_association"] = "NONE"
        owner = issue(4, "feat: maintainer work")
        owner["author_association"] = "OWNER"
        triaged = issue(5, "triaged idea", labels=["type::story"])
        triaged["author_association"] = "NONE"
        scheduled = issue(6, "scheduled idea")
        scheduled["milestone"] = {"title": "v1.0.0"}
        declined = issue(7, "declined", state="closed")
        declined.update(author_association="OWNER", state_reason="not_planned")
        findings, notices = sync.live_findings(self.manifest, live + [community, owner, triaged, scheduled, declined])
        self.assertEqual([finding.split(":")[0] for finding in findings], ["#4", "#5", "#6"])
        self.assertEqual([notice.split(":")[0] for notice in notices], ["#3", "#7"])

    def test_grace_period_defers_a_new_accepted_issue_only_until_it_lapses(self):
        live = [self.projected(entry) for entry in self.live]
        fresh = issue(3, "feat: filed today")
        fresh.update(author_association="OWNER", created_at="2026-01-10T12:00:00Z")
        now = sync.dt.datetime(2026, 1, 11, 12, 0, 0)
        findings, notices = sync.live_findings(self.manifest, live + [fresh], grace_days=2, now=now)
        self.assertEqual((findings, len(notices)), ([], 1))
        later = now + sync.dt.timedelta(days=2)
        findings, notices = sync.live_findings(self.manifest, live + [fresh], grace_days=2, now=later)
        self.assertEqual((len(findings), notices), (1, []))
        findings, _ = sync.live_findings(self.manifest, live + [fresh], now=now)
        self.assertEqual(len(findings), 1)

    def test_live_audit_is_read_only(self):
        with mock.patch.object(sync, "load_manifest", return_value=self.manifest), mock.patch.object(
            sync, "audit_manifest", return_value=[]
        ), mock.patch.object(sync, "fetch_issues", return_value=self.live), mock.patch.object(
            sync.subprocess, "run"
        ) as run, mock.patch.object(Path, "write_text") as write, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(sync.main(["audit", "--live"]), 1)
        run.assert_not_called()
        write.assert_not_called()
        self.assertIn("2 finding(s)", out.getvalue())

    def test_malformed_planning_fences_are_one_finding_not_the_end_of_the_audit(self):
        live = [self.projected(entry) for entry in self.live]
        live[0]["body"] += "\n" + sync.BEGIN
        findings, _ = sync.live_findings(self.manifest, live + [])
        self.assertEqual(findings, ["#1: issue body has malformed BMad Planning fences"])
        live[1]["labels"] = []
        findings, _ = sync.live_findings(self.manifest, live)
        self.assertEqual(len(findings), 2)
        self.assertIn("#2: projection drift (type-label); run apply", findings)

    def test_live_comparison_is_reported_as_skipped_when_the_local_audit_fails(self):
        with mock.patch.object(sync, "load_manifest", return_value=self.manifest), mock.patch.object(
            sync, "audit_manifest", return_value=["broken mapping"]
        ), mock.patch.object(sync, "fetch_issues") as fetch, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(sync.main(["audit", "--live"]), 1)
        fetch.assert_not_called()
        self.assertIn("notice: live comparison skipped", out.getvalue())

    def test_offline_audit_never_fetches(self):
        with mock.patch.object(sync, "load_manifest", return_value=self.manifest), mock.patch.object(
            sync, "audit_manifest", return_value=[]
        ), mock.patch.object(sync, "fetch_issues") as fetch, redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["audit"]), 0)
        fetch.assert_not_called()


class RefreshTests(unittest.TestCase):
    def test_refresh_copies_title_and_state_into_manifest_and_artifact(self):
        live = [issue(1, "feat: first")]
        manifest = sync.build_manifest(live, "owner/repo")
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sync, "ROOT", Path(temp)):
            sync.write_manifest(manifest)
            live[0].update(state="closed", title="feat: renamed")
            self.assertEqual(sync.refresh(manifest, live), ["AH-S001"])
            saved = json.loads((Path(temp) / "_bmad-output" / "issue-map.json").read_text(encoding="utf-8"))
            self.assertEqual(sync.audit_manifest(saved), [])
            self.assertEqual(saved["items"][0]["title"], "feat: renamed")
            text = (Path(temp) / manifest["items"][0]["artifact_path"]).read_text(encoding="utf-8")
        self.assertEqual(manifest["items"][0]["lifecycle"], "completed")
        self.assertIn("# AH-S001 — feat: renamed", text)
        self.assertIn("- **State:** completed", text)

    def test_refresh_refuses_an_amended_artifact_before_writing_anything(self):
        live = [issue(1, "feat: first"), issue(2, "feat: second")]
        manifest = sync.build_manifest(live, "owner/repo")
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sync, "ROOT", Path(temp)):
            sync.write_manifest(manifest)
            first, second = (Path(temp) / item["artifact_path"] for item in manifest["items"])
            second.write_text(second.read_text(encoding="utf-8") + "\n## Amendment\n\nContext.\n", encoding="utf-8")
            before = first.read_text(encoding="utf-8")
            for entry in live:
                entry["state"] = "closed"
            with self.assertRaisesRegex(RuntimeError, "carries amendments.*AH-S002"):
                sync.refresh(manifest, live)
            self.assertEqual(first.read_text(encoding="utf-8"), before)
            self.assertEqual(sync.audit_manifest(manifest), [])
        self.assertEqual([item["lifecycle"] for item in manifest["items"]], ["active", "active"])

    def test_refresh_without_drift_writes_nothing(self):
        live = [issue(1, "feat: first")]
        manifest = sync.build_manifest(live, "owner/repo")
        with mock.patch.object(sync, "write_manifest") as write:
            self.assertEqual(sync.refresh(manifest, live), [])
        write.assert_not_called()


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


if __name__ == "__main__":
    unittest.main()
