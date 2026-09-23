# SPDX-License-Identifier: MIT
"""Tests for the sprint-status.yaml derived from the BMad issue map and the story files."""

import importlib.util
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bmad_issue_sync", REPO / "scripts" / "bmad_issue_sync.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

REPOSITORY = "JakeSelby/agent-harness"


def item_for(kind, number, title=None, parent=None, lifecycle="active"):
    bmad_id = "AH-{}{:03d}".format(sync.PREFIX[kind], number)
    return {
        "bmad_id": bmad_id,
        "github_number": number,
        "github_url": "https://github.com/{}/issues/{}".format(REPOSITORY, number),
        "title": title or "A {} numbered {}".format(kind, number),
        "type": kind,
        "native_type": sync.NATIVE_TYPE[kind],
        "artifact_path": "_bmad-output/implementation-artifacts/{}.md".format(bmad_id),
        "parent_bmad_id": parent["bmad_id"] if parent else None,
        "parent_github_number": parent["github_number"] if parent else None,
        "lifecycle": lifecycle,
        "provenance": "authored",
    }


def manifest_for(items):
    next_ids = {kind: 1 for kind in sync.KINDS}
    for item in items:
        next_ids[item["type"]] = max(next_ids[item["type"]], int(item["bmad_id"][-3:]) + 1)
    return {
        "schema_version": 2,
        "repository": REPOSITORY,
        "native_type_projection": "labels-only",
        "generated_at": "2026-09-01",
        "next_ids": next_ids,
        "items": sorted(items, key=lambda value: value["github_number"]),
    }


def dated(text, updated):
    return re.sub(r'(?m)^updated: .*$', 'updated: "{}"'.format(updated), text, count=1)


def filled(item, updated="2026-09-02"):
    text = sync.render_artifact(item)
    head_end = sync.sync_layout(text)
    body = re.sub(r"<!-- fill: .*?-->", "Written content.", text[head_end:], flags=re.DOTALL)
    return dated(text[:head_end] + body, updated)


def skeleton(item, updated="2026-09-02"):
    return dated(sync.render_artifact(item), updated)


def legacy(item, updated="2026-09-02"):
    return dated(sync.render_legacy_stub(item), updated)


def statuses(text):
    return dict(re.findall(r"(?m)^  ([a-z0-9-]+): ([a-z-]+)$", text))


class SprintRoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "_bmad-output" / "implementation-artifacts").mkdir(parents=True)
        patcher = mock.patch.object(sync, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def write(self, item, text):
        (self.root / item["artifact_path"]).write_bytes(text.encode("utf-8"))

    def save(self, manifest):
        path = self.root / "_bmad-output" / "issue-map.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def status_file(self):
        return self.root / sync.SPRINT_STATUS_RELATIVE_PATH


class RenderingTests(SprintRoot):
    def setUp(self):
        super().setUp()
        self.epic = item_for("epic", 10, "Deliver the program")
        self.story = item_for("story", 12, "feat(bmad): a story, with punctuation!", parent=self.epic)
        self.bug = item_for("bug", 11, parent=self.epic, lifecycle="completed")
        self.orphan = item_for("chore", 5)
        self.manifest = manifest_for([self.epic, self.story, self.bug, self.orphan])
        for item in self.manifest["items"]:
            self.write(item, legacy(item))

    def test_header_comment_and_blocks(self):
        text = sync.render_sprint_status(self.manifest)
        self.assertTrue(text.startswith("# Derived from _bmad-output/issue-map.json"))
        self.assertIn("# regenerate with: python3 scripts/bmad_issue_sync.py sprint-status\n", text)
        self.assertIn(
            "\ngenerated: 2026-09-02\nproject: agent-harness\nproject_key: AH\n"
            "tracking_system: github-issues\n"
            'story_location: "_bmad-output/implementation-artifacts"\n\ndevelopment_status:\n',
            text,
        )
        body = text.split("development_status:\n", 1)[1]
        self.assertEqual(
            body,
            "  ah-e010-deliver-the-program: in-progress\n"
            "  ah-b011-a-bug-numbered-11: done\n"
            "  ah-s012-feat-bmad-a-story-with-punctuation: backlog\n"
            "\n"
            "  # Items with no epic\n"
            "  ah-c005-a-chore-numbered-5: backlog\n",
        )

    def test_a_long_title_is_cut_at_a_word_boundary(self):
        item = item_for("story", 1, "word " * 30)
        key = sync.sprint_key(item)
        self.assertTrue(key.startswith("ah-s001-word-word"))
        self.assertLessEqual(len(key) - len("ah-s001-"), sync.SLUG_LENGTH)
        self.assertFalse(key.endswith("-"))
        self.assertTrue(key.endswith("-word"))

    def test_an_empty_map_renders_an_empty_mapping(self):
        text = sync.render_sprint_status(manifest_for([]))
        self.assertTrue(text.endswith("development_status: {}\n"))


class DerivationTests(SprintRoot):
    def render(self, items, texts):
        for item, text in zip(items, texts):
            if text is not None:
                self.write(item, text)
        return statuses(sync.render_sprint_status(manifest_for(items)))

    def test_each_item_state(self):
        done = item_for("story", 1, lifecycle="completed")
        ready = item_for("story", 2)
        unfilled = item_for("story", 3)
        stub = item_for("bug", 4)
        missing = item_for("task", 5)
        broken = item_for("spike", 6)
        found = self.render(
            [done, ready, unfilled, stub, missing, broken],
            [legacy(done), filled(ready), skeleton(unfilled), legacy(stub), None,
             filled(broken).replace(sync.SYNC_END, "")],
        )
        self.assertEqual(found["ah-s001-a-story-numbered-1"], "done")
        self.assertEqual(found["ah-s002-a-story-numbered-2"], "ready-for-dev")
        self.assertEqual(found["ah-s003-a-story-numbered-3"], "backlog")
        self.assertEqual(found["ah-b004-a-bug-numbered-4"], "backlog")
        self.assertEqual(found["ah-t005-a-task-numbered-5"], "backlog")
        self.assertEqual(found["ah-sp006-a-spike-numbered-6"], "backlog")

    def test_epic_states(self):
        cases = {
            "done": (("completed", "legacy"), ("completed", "legacy")),
            "in-progress": (("completed", "legacy"), ("active", "skeleton")),
            "backlog": (("active", "skeleton"), ("active", "legacy")),
        }
        for expected, children in cases.items():
            with self.subTest(expected=expected):
                epic = item_for("epic", 1)
                items = [epic]
                for offset, (lifecycle, shape) in enumerate(children):
                    items.append(item_for("story", 2 + offset, parent=epic, lifecycle=lifecycle))
                texts = [legacy(epic)] + [
                    legacy(item) if shape == "legacy" else skeleton(item) for item in items[1:]
                ]
                self.assertEqual(self.render(items, texts)["ah-e001-a-epic-numbered-1"], expected)

    def test_a_ready_child_makes_its_epic_in_progress(self):
        epic = item_for("epic", 1)
        child = item_for("story", 2, parent=epic)
        found = self.render([epic, child], [legacy(epic), filled(child)])
        self.assertEqual(found["ah-e001-a-epic-numbered-1"], "in-progress")

    def test_an_epic_without_children_follows_its_own_state(self):
        open_epic = item_for("epic", 1)
        closed_epic = item_for("epic", 2, lifecycle="completed")
        found = self.render([open_epic, closed_epic], [legacy(open_epic), legacy(closed_epic)])
        self.assertEqual(found["ah-e001-a-epic-numbered-1"], "backlog")
        self.assertEqual(found["ah-e002-a-epic-numbered-2"], "done")

    def test_a_grandchild_sits_in_its_epic_block_and_a_child_epic_counts(self):
        epic = item_for("epic", 1)
        sub_epic = item_for("epic", 2, parent=epic)
        story = item_for("story", 3, parent=epic, lifecycle="completed")
        task = item_for("task", 4, parent=story, lifecycle="completed")
        sub_story = item_for("story", 5, parent=sub_epic)
        items = [epic, sub_epic, story, task, sub_story]
        for item in items:
            self.write(item, legacy(item))
        text = sync.render_sprint_status(manifest_for(items))
        body = text.split("development_status:\n", 1)[1]
        self.assertEqual(
            body,
            "  ah-e001-a-epic-numbered-1: in-progress\n"
            "  ah-s003-a-story-numbered-3: done\n"
            "  ah-t004-a-task-numbered-4: done\n"
            "\n"
            "  ah-e002-a-epic-numbered-2: backlog\n"
            "  ah-s005-a-story-numbered-5: backlog\n",
        )


class StabilityAndDriftTests(SprintRoot):
    def setUp(self):
        super().setUp()
        self.story = item_for("story", 1)
        self.manifest = manifest_for([self.story])
        self.write(self.story, skeleton(self.story, "2026-09-05"))
        self.save(self.manifest)

    def test_reruns_are_byte_identical_and_write_nothing(self):
        self.assertTrue(sync.write_sprint_status(self.manifest))
        first = self.status_file().read_bytes()
        with mock.patch.object(sync, "write_text_atomic") as write:
            self.assertFalse(sync.write_sprint_status(self.manifest))
        write.assert_not_called()
        self.assertEqual(sync.render_sprint_status(self.manifest).encode("utf-8"), first)

    def test_generated_is_the_newest_recorded_date_not_the_clock(self):
        self.assertIn("\ngenerated: 2026-09-05\n", sync.render_sprint_status(self.manifest))
        self.manifest["generated_at"] = "2026-09-09"
        self.assertIn("\ngenerated: 2026-09-09\n", sync.render_sprint_status(self.manifest))

    def run_cli(self, *args):
        with mock.patch.object(sync, "load_manifest", return_value=self.manifest), redirect_stdout(io.StringIO()) as out:
            code = sync.main(list(args))
        return code, out.getvalue()

    def test_audit_reports_a_missing_then_a_stale_file_and_passes_once_rendered(self):
        code, out = self.run_cli("audit")
        self.assertEqual(code, 1)
        self.assertIn("sprint-status.yaml is missing; run python3 scripts/bmad_issue_sync.py sprint-status", out)
        self.assertEqual(self.run_cli("sprint-status")[0], 0)
        self.assertEqual(self.run_cli("audit"), (0, "audit: 1 issue(s), 0 finding(s)\n"))
        self.assertEqual(self.run_cli("sprint-status", "--check"), (0, ""))
        self.write(self.story, filled(self.story, "2026-09-05"))
        code, out = self.run_cli("audit")
        self.assertEqual(code, 1)
        self.assertIn("sprint-status.yaml differs from the issue map and story files", out)
        self.assertEqual(self.run_cli("sprint-status", "--check")[0], 1)
        self.run_cli("sprint-status")
        self.assertIn("ah-s001-a-story-numbered-1: ready-for-dev", self.status_file().read_text(encoding="utf-8"))
        self.assertEqual(self.run_cli("audit")[0], 0)

    def test_a_hand_edit_is_drift(self):
        sync.write_sprint_status(self.manifest)
        path = self.status_file()
        path.write_text(path.read_text(encoding="utf-8").replace(": backlog", ": done"), encoding="utf-8")
        self.assertEqual(len(sync.sprint_status_findings(self.manifest)), 1)

    def test_delivery_audit_ignores_the_file(self):
        self.write(self.story, filled(self.story))
        self.assertEqual(self.run_cli("audit", "--delivery", "1")[0], 0)


def live_issue(number, title, state="open"):
    return {
        "number": number,
        "title": title,
        "state": state,
        "html_url": "https://github.com/{}/issues/{}".format(REPOSITORY, number),
        "labels": [],
        "parent_issue_url": None,
    }


class RegenerationTests(SprintRoot):
    def setUp(self):
        super().setUp()
        self.story = item_for("story", 1, "A story")
        self.manifest = manifest_for([self.story])
        sync.write_manifest(self.manifest)

    def rendered(self):
        return self.status_file().read_text(encoding="utf-8")

    def test_write_manifest_renders_the_file(self):
        self.assertEqual(self.rendered(), sync.render_sprint_status(self.manifest))
        self.assertEqual(sync.sprint_status_findings(self.manifest), [])

    def test_refresh_regenerates_it(self):
        live = [live_issue(1, "A story", state="closed")]
        with mock.patch.object(sync, "fetch_issues", return_value=live) as fetch, redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["refresh"]), 0)
        fetch.assert_called_once_with(REPOSITORY)
        self.assertIn("ah-s001-a-story: done", self.rendered())
        self.assertEqual(sync.sprint_status_findings(sync.load_manifest()), [])

    def test_new_regenerates_it(self):
        body = self.root / "body.md"
        body.write_text("Body", encoding="utf-8")
        created = {"number": 2, "labels": [{"name": "type::bug"}]}
        live = [live_issue(1, "A story"), live_issue(2, "A defect")]
        with mock.patch.object(sync, "gh_json", return_value=created) as gh, mock.patch.object(
            sync, "fetch_issues", return_value=live
        ), mock.patch.object(sync, "survey_ids_elsewhere", return_value=({}, 1, [])), redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main([
                "new", "--title", "A defect", "--kind", "bug", "--body-file", str(body), "--parent", "1",
            ]), 0)
        self.assertEqual(gh.call_count, 1)
        text = self.rendered()
        self.assertIn("  # Items with no epic\n  ah-b001-a-defect: backlog\n  ah-s001-a-story: backlog\n", text)
        self.assertEqual(sync.sprint_status_findings(sync.load_manifest()), [])

    def test_upgrade_regenerates_it(self):
        path = self.root / self.story["artifact_path"]
        path.write_text(sync.render_legacy_stub(self.story), encoding="utf-8")
        sync.write_sprint_status(self.manifest)
        with mock.patch.object(sync, "write_sprint_status", wraps=sync.write_sprint_status) as regenerate:
            sync.upgrade(self.manifest, ["AH-S001"])
        regenerate.assert_called_once_with(self.manifest)
        self.assertEqual(sync.sprint_status_findings(self.manifest), [])


if __name__ == "__main__":
    unittest.main()
