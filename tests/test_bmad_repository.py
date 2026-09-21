# SPDX-License-Identifier: MIT
"""Tests for the repository's own BMad publication boundary."""

import subprocess
import tempfile
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


def team_workflows(directory: Path) -> set:
    """Workflow stems in a custom directory, ignoring personal `*.user.toml` overrides."""
    return {path.stem for path in directory.glob("bmad-*.toml") if not path.name.endswith(".user.toml")}


class BMadRepositoryTests(unittest.TestCase):
    def test_every_team_workflow_loads_the_single_governance_source(self):
        self.assertEqual(team_workflows(CUSTOM), WORKFLOWS)
        for name in WORKFLOWS:
            text = (CUSTOM / f"{name}.toml").read_text(encoding="utf-8")
            self.assertEqual(text.count("docs/bmad-governance.md"), 1)

    def test_personal_overrides_do_not_join_the_team_workflow_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in WORKFLOWS:
                (directory / f"{name}.toml").write_text("", encoding="utf-8")
            (directory / "bmad-build.user.toml").write_text("", encoding="utf-8")
            self.assertEqual(team_workflows(directory), WORKFLOWS)
            (directory / "bmad-extra.toml").write_text("", encoding="utf-8")
            self.assertEqual(team_workflows(directory), WORKFLOWS | {"bmad-extra"})

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
