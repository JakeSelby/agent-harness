# SPDX-License-Identifier: MIT
"""Regression checks for the roadmap filings in the committed BMad corpus."""

import importlib.util
import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("bmad_issue_sync_roadmap", REPO / "scripts" / "bmad_issue_sync.py")
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

# N1 through N20, in issue order. These IDs and issue numbers are permanent even
# when the roadmap's dates or the stories' implementation details change.
STORY_PARENTS = (
    "AH-E011", "AH-E013", "AH-E013", "AH-E013", "AH-E013",
    "AH-E013", "AH-E013", "AH-E013", "AH-E013", "AH-E013",
    "AH-E013", "AH-E014", "AH-E011", "AH-E003", "AH-E011",
    "AH-E006", "AH-E015", "AH-E013", "AH-E013", "AH-E005",
)
STORY_MILESTONES = (
    ("v0.14.0",) * 7 + ("v0.15.0",) * 5 + ("v0.16.0",) * 3
    + ("v0.17.0",) * 4 + ("v1.0.0",)
)

# Older accepted issues that gained their first BMad reservation in this PR.
RESERVATIONS = {
    428: ("AH-S252", "AH-E013", "active"),
    429: ("AH-B095", "AH-E013", "active"),
    482: ("AH-S253", "AH-E013", "active"),
    493: ("AH-S260", None, "active"),
    509: ("AH-S254", "AH-E013", "active"),
    510: ("AH-S255", "AH-E013", "active"),
    511: ("AH-S256", "AH-E013", "active"),
    512: ("AH-S257", "AH-E013", "active"),
    513: ("AH-S258", "AH-E013", "active"),
    514: ("AH-S259", "AH-E013", "active"),
    531: ("AH-B098", None, "completed"),
    677: ("AH-B096", "AH-E014", "active"),
    707: ("AH-B097", "AH-E014", "active"),
    715: ("AH-SP013", None, "active"),
}


class RoadmapFilingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((REPO / "_bmad-output" / "issue-map.json").read_text(encoding="utf-8"))
        cls.by_issue = {item["github_number"]: item for item in cls.manifest["items"]}
        cls.by_id = {item["bmad_id"]: item for item in cls.manifest["items"]}

    def test_twenty_new_stories_have_their_permanent_ids_and_parent_epics(self):
        for offset, parent_id in enumerate(STORY_PARENTS):
            number = 788 + offset
            with self.subTest(issue=number):
                item = self.by_issue[number]
                self.assertEqual(item["bmad_id"], "AH-S{:03d}".format(232 + offset))
                self.assertEqual(item["type"], "story")
                self.assertEqual(item["parent_bmad_id"], parent_id)
                self.assertEqual(item["parent_github_number"], self.by_id[parent_id]["github_number"])
                self.assertEqual(item["github_url"], "https://github.com/JakeSelby/agent-harness/issues/{}".format(number))

    def test_new_story_files_contain_a_story_context_and_testable_criteria(self):
        for number in range(788, 808):
            item = self.by_issue[number]
            with self.subTest(issue=number):
                text = (REPO / item["artifact_path"]).read_text(encoding="utf-8")
                sections = {}
                for heading in ("Story", "Context and value", "Acceptance criteria"):
                    section = re.search(r"(?ms)^## {}\n(.*?)(?=^## |\Z)".format(re.escape(heading)), text)
                    self.assertIsNotNone(section, heading)
                    self.assertTrue(sync.section_filled(section.group(1)), heading)
                    sections[heading] = section.group(1)
                self.assertRegex(sections["Acceptance criteria"], r"(?m)^1\. .+")

    def test_older_reservations_include_the_closed_parentless_issue(self):
        self.assertEqual(len(RESERVATIONS), 14)
        for number, (bmad_id, parent_id, lifecycle) in RESERVATIONS.items():
            with self.subTest(issue=number):
                item = self.by_issue[number]
                self.assertEqual((item["bmad_id"], item["parent_bmad_id"], item["lifecycle"]),
                                 (bmad_id, parent_id, lifecycle))
                self.assertEqual(item["parent_github_number"],
                                 self.by_id[parent_id]["github_number"] if parent_id else None)
        self.assertEqual(self.by_issue[787]["bmad_id"], "AH-C074")
        self.assertEqual(self.by_issue[808]["bmad_id"], "AH-C075")
        self.assertIsNone(self.by_issue[787]["parent_bmad_id"])
        self.assertIsNone(self.by_issue[808]["parent_bmad_id"])

    def test_proposal_amendment_maps_each_new_story_once(self):
        proposal = (REPO / "_bmad-output/planning-artifacts/sprint-change-proposal-2026-09-24.md").read_text(
            encoding="utf-8"
        )
        amendment = proposal.split("## Amendment, 2026-09-24: step 3 filings", 1)[1]
        lines = re.findall(r"(?m)^- N(\d+) → (AH-S\d{3}) → #(\d+), (v[\d.]+)$", amendment)
        self.assertEqual(len(lines), 20)
        for offset, (label, bmad_id, issue, milestone) in enumerate(lines):
            with self.subTest(story=label):
                self.assertEqual((int(label), bmad_id, int(issue)),
                                 (offset + 1, "AH-S{:03d}".format(232 + offset), 788 + offset))
                self.assertEqual(self.by_issue[int(issue)]["bmad_id"], bmad_id)
                self.assertEqual(milestone, STORY_MILESTONES[offset])

    def test_parented_filings_are_listed_under_the_matching_epic(self):
        epics = (REPO / "_bmad-output/planning-artifacts/epics.md").read_text(encoding="utf-8")
        sections = dict(re.findall(r"(?ms)^### (AH-E\d{3}):[^\n]*\n(.*?)(?=^### |\Z)", epics))
        for number in list(range(788, 808)) + list(RESERVATIONS):
            item = self.by_issue[number]
            parent_id = item["parent_bmad_id"]
            if parent_id is None:
                continue
            with self.subTest(issue=number):
                self.assertIn(parent_id, sections)
                self.assertIn("- {} [#{}]({}):".format(item["bmad_id"], number, item["github_url"]),
                              sections[parent_id])
        # A closed issue with no epic belongs in the historical no-epic list.
        self.assertIn("- AH-B098 [#531]", epics.split("### Issues #421 onward", 1)[1])

    def test_new_entries_and_closed_reservation_match_the_derived_status(self):
        status = (REPO / sync.SPRINT_STATUS_RELATIVE_PATH).read_text(encoding="utf-8")
        for number in list(range(788, 808)) + list(RESERVATIONS) + [787, 808]:
            item = self.by_issue[number]
            expected = "done" if number == 531 else "ready-for-dev" if number == 787 else "backlog"
            with self.subTest(issue=number):
                self.assertIn("  {}: {}\n".format(sync.sprint_key(item), expected), status)

    def test_local_map_artifacts_and_sprint_projection_remain_consistent(self):
        # Also catches duplicate IDs or issue numbers after a later reservation.
        self.assertEqual(sync.audit_manifest(self.manifest, sprint_status=True), [])


if __name__ == "__main__":
    unittest.main()
