# SPDX-License-Identifier: MIT
"""Tests for dedicated-root worktree management."""
import argparse
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repos" / "project"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "-C", str(self.repo), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        email = "test" + "@" + "example.invalid"
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", email], check=True)
        (self.repo / "README.md").write_text("test\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True)
        self.old_root = os.environ.get("HARNESS_WORKTREE_ROOT")
        os.environ["HARNESS_WORKTREE_ROOT"] = str(self.base / "worktrees")

    def tearDown(self):
        if self.old_root is None:
            os.environ.pop("HARNESS_WORKTREE_ROOT", None)
        else:
            os.environ["HARNESS_WORKTREE_ROOT"] = self.old_root
        self.tmp.cleanup()

    def args(self, action, name=None):
        return argparse.Namespace(
            action=action, name=name, repo=str(self.repo), branch=None,
            base="HEAD", no_fetch=True,
        )

    def test_destination_is_grouped_by_repository(self):
        self.assertEqual(
            harness.worktree_destination(self.repo, "task-one"),
            (self.base / "worktrees" / "project" / "task-one").resolve(),
        )

    def test_invalid_name_is_rejected(self):
        with self.assertRaises(SystemExit):
            harness.worktree_destination(self.repo, "../escape")

    def test_create_audit_and_remove_clean_worktree(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.assertTrue(dest.is_dir())
        self.assertEqual(harness.git_root(str(dest)), self.repo.resolve())
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("audit")), 0)
        self.assertIn(f"clean\ttask-one\t{dest}", output.getvalue())
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 0)
        self.assertFalse(dest.exists())

    def test_remove_refuses_dirty_worktree(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        (dest / "untracked.txt").write_text("keep me\n")
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 1)
        self.assertTrue((dest / "untracked.txt").exists())

    def test_remove_refuses_ignored_files(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        (dest / ".gitignore").write_text("cache/\n")
        subprocess.run(["git", "-C", str(dest), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(dest), "commit", "-qm", "ignore cache"], check=True)
        (dest / "cache").mkdir()
        (dest / "cache" / "payload").write_text("keep me\n")
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 1)
        self.assertTrue((dest / "cache" / "payload").exists())

    def test_remove_refuses_unreferenced_detached_commit(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        (dest / "README.md").write_text("changed\n")
        subprocess.run(["git", "-C", str(dest), "commit", "-qam", "detached work"], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "--detach", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "branch", "-D", "task-one"], check=True)
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 1)
        self.assertTrue(dest.exists())

    def test_same_named_repositories_cannot_share_a_bucket(self):
        other = self.base / "elsewhere" / "project"
        other.mkdir(parents=True)
        subprocess.run(["git", "-C", str(other), "init", "-q", "-b", "main"], check=True)
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        with self.assertRaises(SystemExit):
            harness.ensure_worktree_bucket(other)

    def test_nonempty_markerless_bucket_is_not_claimed(self):
        bucket = self.base / "worktrees" / "project"
        bucket.mkdir(parents=True)
        (bucket / "existing-task").mkdir()
        with self.assertRaises(SystemExit):
            harness.ensure_worktree_bucket(self.repo)


if __name__ == "__main__":
    unittest.main()
