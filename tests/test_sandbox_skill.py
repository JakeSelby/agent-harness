# SPDX-License-Identifier: MIT
"""Unit tests for the sandbox skill and its docs page. Run: python3 -m unittest discover tests"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "claude" / "skills" / "sandbox" / "SKILL.md"
DOC = REPO / "docs" / "sandboxing.md"
STANCE = REPO / "claude" / "stances" / "autonomy" / "execute.md"

# The execute stance is always-loaded content under the 200-line cap bin/harness lint enforces,
# so the sandbox pointer replaced a line rather than adding one. This is its size before that.
EXECUTE_STANCE_LINE_CAP = 8


def frontmatter(path: Path) -> dict:
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---":
        return {}
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class SandboxSkillTests(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(SKILL.is_file())

    def test_frontmatter_carries_name_and_description(self):
        fields = frontmatter(SKILL)
        self.assertEqual(fields.get("name"), "sandbox")
        self.assertTrue(fields.get("description"))

    def test_description_says_when_to_use_the_skill(self):
        self.assertIn("Use ", frontmatter(SKILL)["description"])

    def test_docs_page_exists_and_links_the_skill(self):
        self.assertTrue(DOC.is_file())
        self.assertIn("sandbox", DOC.read_text())

    def test_readme_lists_the_docs_page(self):
        self.assertIn("docs/sandboxing.md", (REPO / "README.md").read_text())

    def test_execute_stance_points_at_the_skill_without_growing(self):
        lines = STANCE.read_text().splitlines()
        self.assertIn("`sandbox` skill", " ".join(lines))
        self.assertLessEqual(len(lines), EXECUTE_STANCE_LINE_CAP)


if __name__ == "__main__":
    unittest.main()
