# SPDX-License-Identifier: MIT
"""A plan `/build` commits must pass the lint as approved, so the skill says how to lint one.

The skill tells the author to copy the plan alone into an empty directory and run the lint on
that directory. These tests hold the skill to saying so and hold the command to working as the
skill describes: a withheld project name or an address in the plan is a finding, and a plan
written around them is clean.

Run: python3 -m unittest discover tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
CITIZEN = REPO / "bin" / "citizen"
SOURCE = REPO / "primitives" / "skills" / "plan-authoring" / "SKILL.md"
PROJECTION = REPO / "claude" / "skills" / "plan-authoring" / "SKILL.md"

# A project name the lint allows only under docs/, as a lint-terms file would declare it.
PROJECT = "exampleproject"

CARD = "# A title\n\n> What this builds.\n\n## Steps\n\n1. **Wire {check}** into the gate.\n   *Exit:* {trailer}\n"


def lint_plan(text):
    """Run the lint the way the skill says: the plan alone in an empty temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        (home / ".config" / "agent-harness").mkdir(parents=True)
        plans = Path(tmp) / "plan"
        plans.mkdir()
        (plans / "a-plan.md").write_text(text, encoding="utf-8")
        env = without_harness_vars()
        env.update(HOME=str(home), HARNESS_LINT_TERMS="docs-ok:" + PROJECT)
        return subprocess.run([sys.executable, str(CITIZEN), "lint", str(plans)],
                              capture_output=True, text=True, env=env, timeout=60)


class PlanLintTests(unittest.TestCase):
    def test_a_withheld_name_and_an_address_are_findings(self):
        out = lint_plan(CARD.format(check=PROJECT + " trust_check",
                                    trailer="the commit carries bot" + "@example.org"))
        self.assertEqual(out.returncode, 1, msg=out.stdout + out.stderr)
        self.assertIn("a-plan.md:7: project name allowed only under docs/", out.stdout)
        self.assertIn("a-plan.md:8: email address", out.stdout)

    def test_a_plan_written_around_them_is_clean(self):
        out = lint_plan(CARD.format(check="the trust check",
                                    trailer="the commit carries the Co-Authored-By trailer"))
        self.assertEqual(out.returncode, 0, msg=out.stdout + out.stderr)
        self.assertIn("lint: 0 finding(s)", out.stdout)


class SkillTests(unittest.TestCase):
    def test_the_skill_says_to_lint_the_plan_before_posting(self):
        for path in (SOURCE, PROJECTION):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(REPO)):
                self.assertIn("run it on the plan before you post the review message", text)
                self.assertIn("the Co-Authored-By trailer", text)
                self.assertIn("<harness checkout>/bin/citizen lint <that directory>", text)
                self.assertIn("reports no finding on the plan", text)


if __name__ == "__main__":
    unittest.main()
