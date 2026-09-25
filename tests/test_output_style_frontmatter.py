# SPDX-License-Identifier: MIT
"""Every shipped output style keeps Claude Code's default coding instructions (#810).

A custom output style without `keep-coding-instructions: true` replaces Claude Code's coding
instructions in the system prompt, so selecting the style would silently strip them.
"""
import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

STYLES = REPO / "claude" / "output-styles"


def frontmatter(path: Path) -> dict:
    """The `key: value` pairs between the opening and closing `---` fences."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("\"'")
    return {}


class OutputStyleFrontmatterTests(unittest.TestCase):
    def test_the_harness_ships_at_least_one_output_style(self):
        self.assertTrue(harness.harness_output_styles())

    def test_every_shipped_style_keeps_the_coding_instructions(self):
        for variant in harness.harness_output_styles():
            with self.subTest(style=variant):
                fields = frontmatter(STYLES / (variant + ".md"))
                self.assertEqual(fields.get("keep-coding-instructions"), "true")


if __name__ == "__main__":
    unittest.main()
