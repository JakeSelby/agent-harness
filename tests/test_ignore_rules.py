# SPDX-License-Identifier: MIT
"""The repository's own ignore rules cover the harness bookkeeping a checkout cannot commit.

Every check runs in a throwaway repository seeded with this repository's `.gitignore` and
nothing else, so a per-checkout `.git/info/exclude` can never stand in for a rule that was
deleted here, and `core.excludesFile` from the developer's home cannot either.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_harness import REPO

BOOKKEEPING = (
    ".agent-harness/task.json",
    ".agent-harness/sync.lock",
    ".agent-harness/evidence/replay-001.jsonl",
)
INPUTS = (".agent-harness/plans/work.md", ".agent-harness/progress.md")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "core.excludesFile=/dev/null", *args],
                          capture_output=True, text=True)


class IgnoreRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text((REPO / ".gitignore").read_text())
        for name in BOOKKEEPING + INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")

    def ignored(self, name):
        return git(self.root, "check-ignore", "-v", "--", name)

    def test_every_bookkeeping_path_is_ignored_by_the_repository_ignore_file(self):
        for name in BOOKKEEPING:
            with self.subTest(path=name):
                result = self.ignored(name)
                self.assertEqual(result.returncode, 0, "%s is not ignored" % name)
                self.assertTrue(result.stdout.startswith(".gitignore:"), result.stdout)

    def test_ignored_bookkeeping_never_reaches_the_staged_or_untracked_listing(self):
        """`lint_tree` walks this listing, so an unignored transcript reddens another session's gate."""
        listed = git(self.root, "ls-files", "--cached", "--others", "--exclude-standard").stdout.split()
        self.assertEqual([name for name in BOOKKEEPING if name in listed], [])
        self.assertEqual(sorted(name for name in INPUTS if name in listed), sorted(INPUTS))

    def test_plans_and_progress_stay_visible_as_task_inputs(self):
        for name in INPUTS:
            with self.subTest(path=name):
                self.assertEqual(self.ignored(name).returncode, 1,
                                 "%s must not be ignored; a handoff reads it" % name)

    def test_the_fixture_would_fail_if_a_rule_were_removed(self):
        kept = [line for line in (REPO / ".gitignore").read_text().splitlines()
                if not line.startswith(".agent-harness/")]
        (self.root / ".gitignore").write_text("\n".join(kept) + "\n")
        for name in BOOKKEEPING:
            with self.subTest(path=name):
                self.assertEqual(self.ignored(name).returncode, 1)


if __name__ == "__main__":
    unittest.main()
