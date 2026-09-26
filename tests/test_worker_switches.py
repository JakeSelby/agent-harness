# SPDX-License-Identifier: MIT
"""An isolated worker run leaves out the rules, skills and roles its launching session switches off.

Run: python3 -m unittest discover tests
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import workers  # noqa: E402

CFG = json.loads((REPO / "config.example.json").read_text())


class WorkerSwitchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def resolve(self, role="gatherer", **selection):
        session = self.dir / "session.json"
        session.write_text(json.dumps(selection))
        env = without_harness_vars()
        env.update({"HOME": str(self.dir), "HARNESS_SESSION_CONFIG": str(session)})
        with patch.dict(os.environ, env, clear=True):
            return workers.resolution(REPO, json.loads(json.dumps(CFG)), "claude-code", role, model="some-model")

    def test_an_off_rule_is_not_in_the_instructions(self):
        rule = (REPO / "primitives" / "rules" / "secrets.md").read_text()
        self.assertIn(rule, self.resolve()["instructions"])
        ready = self.resolve(rules={"secrets": "off"})
        self.assertNotIn(rule, ready["instructions"])
        self.assertEqual(ready["selection"]["rules"]["secrets"], "off")

    def test_an_off_skill_is_not_a_read_root(self):
        skills = self.resolve(role="planner")["skills"]
        self.assertTrue(skills, "the planner reads at least one skill")
        name = skills[0].name
        ready = self.resolve(role="planner", skills={name: "off"})
        self.assertNotIn(name, [path.name for path in ready["skills"]])

    def test_an_off_role_does_not_run(self):
        self.assertEqual(self.resolve()["fields"]["name"], "gatherer")
        with self.assertRaisesRegex(ValueError, "gatherer role is switched off"):
            self.resolve(roles={"gatherer": "off"})


if __name__ == "__main__":
    unittest.main()
