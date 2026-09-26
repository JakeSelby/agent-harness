# SPDX-License-Identifier: MIT
"""Pins the team customization that lets bmad-code-review run straight through an approved plan."""

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

TEAM = REPO / "_bmad" / "custom" / "bmad-code-review.toml"
TEMPLATE = REPO / "templates" / "bmad" / "custom" / "bmad-code-review.user.toml"
# The four halts in BMad 6.12.0's step files, by the heading each sits under, and the answer
# an approved plan stands in for.
CHECKPOINTS = {
    '"CHECKPOINT", present the summary and proceed',
    '"Resolve decision-needed findings", resolve nothing',
    '"Handle `patch` findings", take "Apply every patch"',
    '"Next steps", take "Done"',
}


def facts(path: Path) -> list:
    doc = harness.reconcile.tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    return doc["workflow"]["persistent_facts"]


def mode_fact() -> str:
    found = [fact for fact in facts(TEAM) if fact.startswith("Approved-plan mode.")]
    assert len(found) == 1, found
    return found[0]


class ApprovedPlanModeTests(unittest.TestCase):
    def test_mode_rides_a_key_the_resolver_merges_and_keeps_governance_first(self):
        keys, entries = harness.toml_surface(TEAM.read_text(encoding="utf-8"))
        self.assertEqual(keys, {"workflow.persistent_facts"})
        self.assertEqual(entries, set())
        self.assertEqual(facts(TEAM)[0], "file:{project-root}/docs/bmad-governance.md")
        self.assertEqual(len(facts(TEAM)), 2)

    def test_every_checkpoint_has_its_standing_answer(self):
        text = mode_fact()
        for answer in CHECKPOINTS:
            self.assertIn(answer, text)

    def test_mode_applies_only_to_an_approved_plan_and_keeps_blocking_halts(self):
        text = mode_fact()
        self.assertIn('approved with "build" or "go with N"', text)
        self.assertIn("`unattended`", text)
        self.assertIn("Invoked any other way, the review halts at every checkpoint", text)
        self.assertIn("Every other halt still stops the run", text)

    def test_findings_are_recorded_and_only_decisions_surface(self):
        text = mode_fact()
        self.assertIn("unchecked `[Review][Decision]` item in the story", text)
        self.assertIn("Every finding is still written to the story's review findings section", text)
        self.assertIn("then only the decision-needed findings", text)

    def test_shipped_template_does_not_duplicate_the_appended_fact(self):
        # persistent_facts append across team and user files, so a copy in the template
        # would load twice in any repository that also carries the team file.
        self.assertNotIn("Approved-plan mode", TEMPLATE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
