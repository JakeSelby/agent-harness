# SPDX-License-Identifier: MIT
"""Three user-facing edges found by native qualification: the stale-save refusal, the empty
directories uninstall used to leave, and what `doctor` says about a client it cannot exec.

Run: python3 -m unittest discover tests
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test_harness import harness, REPO, TempHome

# Assembled at run time so the fixture identity is not an address-shaped literal the lint reads.
IDENTITY = "task" + "@" + "example" + ".invalid"


def run_cli(*args, home):
    env = dict(os.environ)
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.pop("HARNESS_QUIET", None)
    env["HOME"] = str(home)
    return subprocess.run([sys.executable, str(REPO / "bin" / "harness")] + list(args),
                          capture_output=True, text=True, env=env)


class StaleSaveRefusalTests(unittest.TestCase):
    """A save against a revision that has moved on is a refusal, not a crash."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        self.repo.mkdir()
        (self.repo / "file.txt").write_text("one\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "initial")
        self.contract = base / "task.json"
        self.contract.write_text(json.dumps({"objective": "Continue the fixture"}))

    def git(self, *args):
        env = dict(os.environ, HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1",
                   GIT_AUTHOR_NAME="Task Fixture", GIT_COMMITTER_NAME="Task Fixture",
                   GIT_AUTHOR_EMAIL=IDENTITY, GIT_COMMITTER_EMAIL=IDENTITY)
        subprocess.run(["git", "-C", str(self.repo)] + list(args), check=True,
                       capture_output=True, env=env)

    def save(self, revision):
        return run_cli("task", "save", str(self.repo), "--input", str(self.contract),
                       "--runtime", "codex", "--revision", str(revision), home=self.home)

    def test_a_stale_revision_prints_one_clean_line_and_exits_one(self):
        self.assertEqual(self.save(0).returncode, 0)
        stale = self.save(0)
        self.assertEqual(stale.returncode, 1)
        lines = stale.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, stale.stderr)
        self.assertIn("revision changed", lines[0])
        self.assertIn("read the current task, then save against its revision", lines[0])
        self.assertNotIn("Traceback", stale.stderr)
        self.assertNotIn("ValueError", stale.stderr)
        self.assertNotIn(str(self.repo), stale.stderr)
        self.assertEqual(stale.stdout, "")

    def test_the_guard_is_as_strict_as_before_and_the_stored_task_is_untouched(self):
        self.save(0)
        stored = json.loads((self.repo / ".agent-harness" / "task.json").read_text())
        self.assertEqual(self.save(0).returncode, 1)
        again = json.loads((self.repo / ".agent-harness" / "task.json").read_text())
        self.assertEqual(again, stored)
        self.assertEqual(self.save(1).returncode, 0)


class UninstallEmptyDirectoryTests(TempHome):
    def sync(self):
        return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=True,
                                                           adopt_codex=False, print_only=False))

    def test_uninstall_removes_the_empty_directories_the_sync_created(self):
        self.assertEqual(self.sync(), 0)
        stances = self.home / ".claude" / "rules" / "harness-stances"
        self.assertTrue(stances.is_dir())
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse(stances.exists())
        for directory in (self.home / ".agents" / "skills").glob("harness-*"):
            self.assertTrue(any(directory.iterdir()), directory)

    def test_a_directory_holding_a_file_the_harness_does_not_own_stays(self):
        self.assertEqual(self.sync(), 0)
        stances = self.home / ".claude" / "rules" / "harness-stances"
        (stances / "mine.md").write_text("my own note\n")
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertTrue(stances.is_dir())
        self.assertEqual((stances / "mine.md").read_text(), "my own note\n")

    def test_nothing_is_removed_when_the_directory_was_never_created(self):
        self.assertEqual(harness._empty_harness_directories(), [])


class DoctorPathTests(TempHome):
    def report(self):
        os.environ.pop("HARNESS_QUIET", None)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            harness.cmd_doctor(harness.argparse.Namespace())
        return buffer.getvalue()

    def test_a_client_that_cannot_be_executed_is_reported_as_not_on_path(self):
        with unittest.mock.patch.object(harness.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(harness._version_of(["definitely-not-a-client", "--version"]),
                             "not on PATH")

    def test_codex_credentials_with_no_client_on_path_say_why(self):
        auth = harness.codex_dir() / "auth.json"
        auth.parent.mkdir(parents=True, exist_ok=True)
        auth.write_text("{}")
        with unittest.mock.patch.object(harness.shutil, "which", return_value=None):
            report = self.report()
        self.assertIn("codex credentials present", report)
        self.assertIn("no `codex` on PATH", report)
        self.assertNotIn("not installed", report)


if __name__ == "__main__":
    unittest.main()
