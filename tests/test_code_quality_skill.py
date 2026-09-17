# SPDX-License-Identifier: MIT
"""Unit tests for the `code-quality-instruments` skill and its stance pointer.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

SKILL = REPO / "claude" / "skills" / "code-quality-instruments" / "SKILL.md"
REQUIRED = REPO / "claude" / "stances" / "testing" / "required.md"
BUDGET = 196


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter block"
    return dict(
        (k.strip(), v.strip())
        for k, _, v in (line.partition(":") for line in m.group(1).splitlines() if ":" in line)
    )


class SkillShapeTests(unittest.TestCase):
    def test_the_skill_exists_with_frontmatter(self):
        self.assertTrue(SKILL.is_file())
        fm = frontmatter(SKILL)
        self.assertEqual(fm["name"], "code-quality-instruments")
        self.assertTrue(fm["description"].startswith("Measure"), fm["description"])

    def test_the_description_says_when_to_use_it(self):
        # The description is the only part loaded until the skill is invoked, so it has to
        # carry the trigger, not just the topic.
        self.assertIn("Use when", frontmatter(SKILL)["description"])

    def test_every_language_we_work_in_has_an_instrument(self):
        body = SKILL.read_text(encoding="utf-8")
        for language in ("Python", "TypeScript", "Rust", "Go"):
            with self.subTest(language=language):
                self.assertIn(language, body)

    def test_it_names_a_mutation_tool_per_language(self):
        body = SKILL.read_text(encoding="utf-8")
        for tool in ("mutmut", "Stryker", "cargo-mutants", "go-mutesting"):
            with self.subTest(tool=tool):
                self.assertIn(tool, body)

    def test_it_routes_adoption_through_the_licensing_stance(self):
        """Naming a third-party tool without that pointer would contradict the licensing stance."""
        self.assertIn("licensing-review", SKILL.read_text(encoding="utf-8"))

    def test_it_carries_the_differential_and_serial_operating_rules(self):
        body = SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("mutate the diff", body)
        self.assertIn("one at a time", body)


class StancePointerTests(unittest.TestCase):
    def test_the_required_variant_points_at_the_skill(self):
        self.assertIn("code-quality-instruments", REQUIRED.read_text(encoding="utf-8"))

    def test_the_pointer_did_not_blow_the_always_loaded_budget(self):
        total, groups = harness.always_loaded_lines(REPO)
        self.assertLessEqual(total, BUDGET, msg=f"{total} lines: {groups}")

    def test_the_reasoning_stayed_out_of_the_always_loaded_layer(self):
        """The table and the operating rules belong in the skill, not the stance."""
        variant = REQUIRED.read_text(encoding="utf-8")
        for detail in ("mutmut", "Stryker", "branch coverage", "|"):
            with self.subTest(detail=detail):
                self.assertNotIn(detail, variant)


if __name__ == "__main__":
    unittest.main()
