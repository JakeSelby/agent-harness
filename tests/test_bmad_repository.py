# SPDX-License-Identifier: MIT
"""Tests for the repository's own BMad publication boundary."""

import subprocess
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
CUSTOM = REPO / "_bmad" / "custom"
WORKFLOWS = {
    "bmad-architecture",
    "bmad-build",
    "bmad-code-review",
    "bmad-create-epics-and-stories",
    "bmad-prd",
    "bmad-product-brief",
    "bmad-project-context",
    "bmad-retrospective",
    "bmad-sprint-planning",
    "bmad-ux",
}


class BMadRepositoryTests(unittest.TestCase):
    def test_every_team_workflow_loads_the_single_governance_source(self):
        actual = {path.stem for path in CUSTOM.glob("bmad-*.toml")}
        self.assertEqual(actual, WORKFLOWS)
        for name in WORKFLOWS:
            text = (CUSTOM / f"{name}.toml").read_text(encoding="utf-8")
            self.assertEqual(text.count("docs/bmad-governance.md"), 1)

    def test_team_config_keeps_public_artifacts_inside_the_repository(self):
        text = (CUSTOM / "config.toml").read_text(encoding="utf-8")
        self.assertIn('project_name = "agent-harness"', text)
        self.assertIn('{project-root}/_bmad-output/planning-artifacts', text)
        self.assertIn('{project-root}/_bmad-output/implementation-artifacts', text)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("jake-product-ideas", text)

    def test_generated_bmad_apparatus_is_not_tracked(self):
        tracked = subprocess.run(
            ["git", "ls-files", "_bmad", ".agents", ".claude/skills", ".github/agents"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        unexpected = [path for path in tracked if path.startswith("_bmad/") and not path.startswith("_bmad/custom/")]
        unexpected += [path for path in tracked if not path.startswith("_bmad/")]
        self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
