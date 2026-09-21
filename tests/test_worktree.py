# SPDX-License-Identifier: MIT
"""Tests for dedicated-root worktree management."""
import argparse
import importlib.machinery
import importlib.util
import os
import shutil
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

    def args(self, action, name=None, merged=False, also_clear=None):
        return argparse.Namespace(
            action=action, name=name, repo=str(self.repo), branch=None,
            base="HEAD", no_fetch=True, merged=merged, also_clear=also_clear or [],
        )

    def ignore(self, dest, pattern):
        (dest / ".gitignore").write_text(pattern + "\n")
        subprocess.run(["git", "-C", str(dest), "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", str(dest), "commit", "-qm", "ignore " + pattern], check=True)

    def stub_gh(self, script):
        """Put a fake `gh` on a PATH holding nothing else but git, so no live service is called.

        `script` of None leaves `gh` off that PATH, which is how the missing-tool path is tested.
        """
        bindir = self.base / "stub-bin"
        bindir.mkdir(exist_ok=True)
        if script is not None:
            executable = bindir / "gh"
            executable.write_text(script)
            executable.chmod(0o755)
        link = bindir / "git"
        if not link.exists():
            os.symlink(shutil.which("git"), link)
        self.addCleanup(os.environ.__setitem__, "PATH", os.environ["PATH"])
        os.environ["PATH"] = str(bindir)

    def merged_pr_stub(self, oid, number=7):
        return "#!/bin/sh\necho '" + f'[{{"number": {number}, "headRefOid": "{oid}"}}]' + "'\n"

    def tip_of(self, dest):
        out = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                             check=True, capture_output=True, text=True)
        return out.stdout.strip()

    def branches(self):
        out = subprocess.run(["git", "-C", str(self.repo), "branch", "--format=%(refname:short)"],
                             check=True, capture_output=True, text=True)
        return out.stdout.split()

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
        """An ignored name that is not a known cache is still someone's work, and still refuses."""
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.ignore(dest, "cache/")
        (dest / "cache").mkdir()
        (dest / "cache" / "payload").write_text("keep me\n")
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 1)
        self.assertTrue((dest / "cache" / "payload").exists())

    def test_classify_separates_regenerable_entries_from_everything_else(self):
        status = ' M bin/harness\n?? notes.txt\n!! __pycache__/\n!! docs/.astro/\n!! secrets.env\n!! "odd \\303\\251/__pycache__/"\n'
        regenerable, blocking = harness.classify_worktree_status(status)
        self.assertEqual(regenerable, ["__pycache__/", "docs/.astro/"])
        self.assertEqual(blocking, ["bin/harness", "notes.txt", "secrets.env", '"odd \\303\\251/__pycache__/"'])

    def test_also_clear_adds_one_name(self):
        regenerable, blocking = harness.classify_worktree_status("!! dist/\n", ["dist"])
        self.assertEqual((regenerable, blocking), (["dist/"], []))

    def test_remove_clears_regenerable_caches(self):
        """A gate run writes `__pycache__`; that must not be what keeps a finished worktree alive."""
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.ignore(dest, "__pycache__/")
        (dest / "__pycache__").mkdir()
        (dest / "__pycache__" / "harness.pyc").write_text("bytecode\n")
        (dest / "tests" / "__pycache__").mkdir(parents=True)
        (dest / "tests" / "__pycache__" / "test.pyc").write_text("bytecode\n")
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 0)
        self.assertFalse(dest.exists())

    def test_audit_reports_a_cache_only_worktree_as_clean(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.ignore(dest, "__pycache__/")
        (dest / "__pycache__").mkdir()
        (dest / "__pycache__" / "harness.pyc").write_text("bytecode\n")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("audit")), 0)
        self.assertIn(f"clean\ttask-one\t{dest}", output.getvalue())

    def test_also_clear_covers_a_directory_the_built_in_list_misses(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.ignore(dest, "dist/")
        (dest / "dist").mkdir()
        (dest / "dist" / "index.js").write_text("built\n")
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 1)
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", also_clear=["dist"])), 0)
        self.assertFalse(dest.exists())

    def test_merged_removal_deletes_the_branch_after_a_squash(self):
        """The branch tip is no ancestor of main after a squash, so the merged head is the proof."""
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        (dest / "feature.txt").write_text("work\n")
        subprocess.run(["git", "-C", str(dest), "add", "feature.txt"], check=True)
        subprocess.run(["git", "-C", str(dest), "commit", "-qm", "feature"], check=True)
        self.stub_gh(self.merged_pr_stub(self.tip_of(dest)))
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 0)
        self.assertFalse(dest.exists())
        self.assertNotIn("task-one", self.branches())

    def test_merged_removal_refuses_when_the_tip_is_not_the_merged_head(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.stub_gh(self.merged_pr_stub("0" * 40))
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 1)
        self.assertIn("is not the merged head", output.getvalue())
        self.assertTrue(dest.exists())
        self.assertIn("task-one", self.branches())

    def test_merged_removal_refuses_when_no_pull_request_matches(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.stub_gh("#!/bin/sh\necho '[]'\n")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 1)
        self.assertIn("no merged pull request", output.getvalue())
        self.assertTrue(dest.exists())

    def test_merged_removal_refuses_when_gh_fails(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.stub_gh("#!/bin/sh\necho 'gh: not logged in' >&2\nexit 1\n")
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 1)
        self.assertIn("not logged in", output.getvalue())
        self.assertTrue(dest.exists())

    def test_merged_removal_refuses_when_gh_is_missing(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.stub_gh(None)
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 1)
        self.assertIn("gh is not installed", output.getvalue())
        self.assertTrue(dest.exists())
        self.assertIn("task-one", self.branches())

    def test_merged_removal_refuses_before_it_clears_a_cache(self):
        """The proof runs first, so a refused removal leaves the caches and the checkout intact."""
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.ignore(dest, "__pycache__/")
        (dest / "__pycache__").mkdir()
        (dest / "__pycache__" / "harness.pyc").write_text("bytecode\n")
        self.stub_gh(self.merged_pr_stub("0" * 40))
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one", merged=True)), 1)
        self.assertTrue((dest / "__pycache__" / "harness.pyc").exists())

    def test_removal_without_merged_keeps_the_branch(self):
        self.assertEqual(harness.cmd_worktree(self.args("create", "task-one")), 0)
        dest = (self.base / "worktrees" / "project" / "task-one").resolve()
        self.assertEqual(harness.cmd_worktree(self.args("remove", "task-one")), 0)
        self.assertFalse(dest.exists())
        self.assertIn("task-one", self.branches())

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
