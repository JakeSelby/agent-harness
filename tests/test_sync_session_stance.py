# SPDX-License-Identifier: MIT
"""A `HARNESS_STANCE_*` variable is a session selection, and a real sync never links it.

`harness stances` and the hooks resolve the variable; the session-start hook injects the chosen
variant's text; `harness sync` keeps linking the user-level variant and prints a scope notice;
`harness diff` compares against the user's layers, so the session selection is not drift.
Regression test for #294.

Run: python3 -m unittest tests.test_sync_session_stance
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
STANCES = REPO / "primitives" / "stances"


class SyncWithSessionStance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        config = self.home / ".config" / "agent-harness"
        config.mkdir(parents=True)
        (config / "config.json").write_text(json.dumps({"stances": {"testing": "required"}}),
                                            encoding="utf-8")

    def cli(self, env, *args):
        merged = dict(without_harness_vars(), HOME=str(self.home), **env)
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness")] + list(args),
                              capture_output=True, text=True, env=merged, cwd=str(self.home))

    def linked_testing(self):
        link = self.home / ".claude" / "rules" / "harness-stances" / "testing.md"
        self.assertTrue(link.is_symlink(), link)
        return os.path.realpath(link)

    def test_sync_keeps_the_user_variant_linked_and_says_why(self):
        session = {"HARNESS_STANCE_TESTING": "off"}
        synced = self.cli(session, "sync")
        self.assertEqual(synced.returncode, 0, synced.stdout + synced.stderr)
        self.assertIn("sync projects user defaults; project/session overrides stay in the session",
                      synced.stdout)
        self.assertEqual(self.linked_testing(), str((STANCES / "testing" / "required.md").resolve()))

        # The session resolves the variable all the same...
        stances = self.cli(session, "stances", "--json")
        self.assertEqual(stances.returncode, 0, stances.stderr)
        data = json.loads(stances.stdout)
        self.assertEqual((data["stances"]["testing"]["variant"], data["sources"]["testing"]),
                         ("off", "session"))

        # ...and diff reports the linked state against the user's layers, so it is not drift.
        diff = self.cli(session, "diff")
        self.assertEqual(diff.returncode, 0, diff.stdout + diff.stderr)
        self.assertIn("a project or session selection is not drift", diff.stdout)
        self.assertIn("no drift", diff.stdout)

    def test_diff_without_a_session_selection_prints_no_scope_line(self):
        synced = self.cli({}, "sync")
        self.assertEqual(synced.returncode, 0, synced.stdout + synced.stderr)
        self.assertNotIn("project/session overrides", synced.stdout)
        diff = self.cli({}, "diff")
        self.assertEqual(diff.returncode, 0, diff.stdout + diff.stderr)
        self.assertNotIn("scope", diff.stdout)


    def test_an_identity_override_alone_prints_no_scope_line(self):
        synced = self.cli({}, "sync")
        self.assertEqual(synced.returncode, 0, synced.stdout + synced.stderr)
        diff = self.cli({"HARNESS_IDENTITY_NAME": "Someone"}, "diff")
        self.assertEqual(diff.returncode, 0, diff.stdout + diff.stderr)
        self.assertNotIn("scope", diff.stdout)

if __name__ == "__main__":
    unittest.main()
