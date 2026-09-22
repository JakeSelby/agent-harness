# SPDX-License-Identifier: MIT
"""The suite must not inherit the caller's CLAUDE_CONFIG_DIR.

`claude_dir()` prefers that variable over the home a test controls, so a value left in the
developer's shell used to send a sync test's links, settings and rules into their real profile.
Runtime precedence is deliberate and untouched; these tests pin the suite's side of it.

Run: python3 -m unittest discover tests
"""
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from isolation import CONFIG_DIR, isolate_home, without_config_dir, without_harness_vars

ELSEWHERE = "/elsewhere/.claude"  # a profile no test controls


class EnvironmentHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = unittest.mock.patch.dict(os.environ, {CONFIG_DIR: ELSEWHERE,
                                                        "HARNESS_STANCE_TESTING": "off"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_subprocess_environment_does_not_carry_an_inherited_config_dir(self):
        self.assertEqual(os.environ[CONFIG_DIR], ELSEWHERE)
        self.assertNotIn(CONFIG_DIR, without_config_dir())
        self.assertNotIn(CONFIG_DIR, without_harness_vars())
        self.assertNotIn("HARNESS_STANCE_TESTING", without_harness_vars())
        self.assertEqual(without_harness_vars()["PATH"], os.environ["PATH"])

    def test_a_given_environment_is_copied_rather_than_changed(self):
        given = {CONFIG_DIR: ELSEWHERE, "HOME": str(self.home)}
        self.assertEqual(without_config_dir(given), {"HOME": str(self.home)})
        self.assertEqual(given[CONFIG_DIR], ELSEWHERE)

    def test_isolating_a_temporary_home_drops_the_config_dir_from_this_process(self):
        isolate_home(self.home)
        self.assertNotIn(CONFIG_DIR, os.environ)
        self.assertEqual(os.environ["HOME"], str(self.home))
        self.assertNotIn("HARNESS_STANCE_TESTING", os.environ)
        self.assertEqual(os.environ["HARNESS_QUIET"], "1")


class SyncStaysInsideItsFixtureTests(unittest.TestCase):
    """The regression itself: a sync test run with the variable set writes nothing to it."""

    def test_a_sync_test_writes_nothing_into_an_inherited_config_dir(self):
        import test_commands

        with tempfile.TemporaryDirectory() as config:
            with unittest.mock.patch.dict(os.environ, {CONFIG_DIR: config}):
                case = test_commands.CommandSyncTests(
                    "test_sync_links_every_command_and_uninstall_removes_them")
                result = case.run()
            self.assertEqual((result.errors, result.failures), ([], []))
            self.assertTrue(result.wasSuccessful())
            self.assertEqual(sorted(os.listdir(config)), [])


if __name__ == "__main__":
    unittest.main()
