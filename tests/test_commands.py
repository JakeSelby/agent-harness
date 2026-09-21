# SPDX-License-Identifier: MIT
"""Unit tests for the slash commands and their sync. Run: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

COMMANDS = REPO / "claude" / "commands"
EXPECTED = ["build.md", "handoff.md", "land.md", "plan.md", "research.md", "review.md"]
MAX_BODY_LINES = 35


def split(path):
    """Frontmatter as a flat dict, plus the body below it."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    head, _, body = text[4:].partition("\n---\n")
    front = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            front[key.strip()] = value.strip()
    return front, body


def sync(adopt=True):
    return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=adopt, adopt_codex=False, print_only=False))


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        for k in list(os.environ):
            if k.startswith("HARNESS_"):
                del os.environ[k]
        os.environ["HARNESS_QUIET"] = "1"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()


class CommandSyncTests(TempHome):
    def test_sync_links_every_command_and_uninstall_removes_them(self):
        self.assertEqual(sync(), 0)
        live = self.home / ".claude" / "commands"
        for name in EXPECTED:
            self.assertTrue((live / name).is_symlink(), msg=name)
            self.assertEqual((live / name).resolve(), (COMMANDS / name).resolve(), msg=name)
        manifest = json.loads((self.home / ".local/state/agent-harness/manifest.json").read_text())
        recorded = {Path(l["path"]).name for l in manifest["links"] if Path(l["path"]).parent == live}
        self.assertEqual(recorded, set(EXPECTED))
        self.assertEqual(sync(adopt=False), 0)
        self.assertEqual(harness._diff_lines(), [])
        harness.cmd_uninstall(harness.argparse.Namespace())
        for name in EXPECTED:
            self.assertFalse((live / name).is_symlink() or (live / name).exists(), msg=name)

    def test_a_command_file_the_user_wrote_is_never_replaced_without_adopt(self):
        live = self.home / ".claude" / "commands"
        live.mkdir(parents=True)
        (live / "review.md").write_text("mine")
        self.assertEqual(sync(adopt=False), 2)
        self.assertEqual((live / "review.md").read_text(), "mine")
        self.assertEqual(sync(), 0)
        self.assertTrue((live / "review.md").is_symlink())


class LinkDirFilesTests(TempHome):
    def _dirs(self):
        source = self.home / "source"
        source.mkdir()
        return source, self.home / ".claude" / "commands"

    def test_every_file_in_the_source_directory_is_linked(self):
        source, dest = self._dirs()
        (source / "one.md").write_text("one\n")
        (source / "two.md").write_text("two\n")
        manifest, report = {}, []
        harness.link_dir_files(source, dest, manifest, False, True, report)
        self.assertEqual(report, [])
        self.assertEqual({Path(l["path"]).name for l in manifest["links"]}, {"one.md", "two.md"})
        self.assertEqual((dest / "two.md").resolve().read_text(), "two\n")

    def test_a_file_dropped_from_the_source_unlinks_on_the_next_sync(self):
        source, dest = self._dirs()
        (source / "one.md").write_text("one\n")
        (source / "two.md").write_text("two\n")
        manifest, report = {}, []
        harness.link_dir_files(source, dest, manifest, False, True, report)
        (source / "two.md").unlink()
        harness.link_dir_files(source, dest, manifest, False, True, report)
        self.assertTrue((dest / "one.md").is_symlink())
        self.assertFalse((dest / "two.md").is_symlink())
        self.assertEqual({Path(l["path"]).name for l in manifest["links"]}, {"one.md"})

    def test_a_missing_source_directory_is_not_an_error(self):
        manifest, report = {}, []
        harness.link_dir_files(self.home / "absent", self.home / ".claude" / "commands", manifest, False, True, report)
        self.assertEqual(manifest, {})
        self.assertEqual(report, [])


class CommandContentTests(unittest.TestCase):
    def test_the_shipped_commands_are_the_expected_ones(self):
        self.assertEqual(sorted(p.name for p in COMMANDS.iterdir()), EXPECTED)

    def test_each_command_declares_its_frontmatter_and_takes_arguments(self):
        for name in EXPECTED:
            front, body = split(COMMANDS / name)
            self.assertTrue(front.get("description"), msg=name)
            self.assertTrue(front.get("argument-hint"), msg=name)
            self.assertIn("$ARGUMENTS", body, msg=name)

    def test_every_body_stays_short_enough_to_read_in_one_screen(self):
        for name in EXPECTED:
            _, body = split(COMMANDS / name)
            self.assertLessEqual(len(body.strip().splitlines()), MAX_BODY_LINES, msg=name)

    def test_every_command_that_needs_a_repository_says_so_before_it_starts(self):
        """A command that discovers its precondition halfway through has already done work."""
        for name, needle in (("build.md", "Check first, before spawning anything"),
                             ("review.md", "before spawning anything")):
            self.assertIn(needle, split(COMMANDS / name)[1], msg=name)

    def test_the_repository_bound_commands_name_a_fallback_rather_than_only_stopping(self):
        build = split(COMMANDS / "build.md")[1]
        self.assertIn("No repository: say so and offer to make the change in place", build)
        self.assertIn("stop at the local commit", build)
        review = split(COMMANDS / "review.md")[1]
        self.assertIn("offer to\n   review named files or a pasted patch instead", review)

    def test_the_writing_commands_have_a_path_outside_a_repository(self):
        for name in ("plan.md", "handoff.md"):
            body = split(COMMANDS / name)[1]
            self.assertIn("no repository", body, msg=name)

    def test_plan_states_that_it_needs_no_repository(self):
        self.assertIn("needs no repository", split(COMMANDS / "plan.md")[1])

    def test_the_fan_out_commands_name_the_agent_they_spawn(self):
        self.assertIn("`gatherer`", split(COMMANDS / "research.md")[1])
        self.assertIn("`reviewer`", split(COMMANDS / "review.md")[1])

    def test_the_sequence_commands_name_the_skill_they_run(self):
        self.assertIn("plan-authoring", split(COMMANDS / "plan.md")[1])
        self.assertIn("worktree-per-agent", split(COMMANDS / "build.md")[1])

    def test_land_verifies_the_current_head_before_it_merges(self):
        body = split(COMMANDS / "land.md")[1]
        self.assertIn("gh pr merge --squash --delete-branch", body)
        self.assertIn("current head", body)
        self.assertIn("issue-ownership", body)

    def test_land_cleans_up_only_through_the_reversible_commands(self):
        """The refusals are the safety check; a forced form would delete unreviewed work."""
        body = split(COMMANDS / "land.md")[1]
        self.assertIn("harness worktree remove", body)
        self.assertIn("git branch -d <branch>", body)
        self.assertIn("harness worktree audit", body)
        self.assertIn("Never force a removal", body)
        self.assertIn("Never `git branch -D`", body)
        self.assertIn("compound command", body)
        self.assertNotIn("git branch -D <", body)

    def test_land_gates_the_merge_and_defers_the_release_rule_to_the_repository(self):
        body = split(COMMANDS / "land.md")[1]
        self.assertIn("approval-gated", body)
        self.assertIn("never tags and never deploys", body)
        self.assertIn("no release due", body)
        self.assertIn("the repository's own agent instructions", body)

    def test_ownership_records_the_commands_directory(self):
        ownership = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())
        self.assertIn("commands", ownership["claude"])


if __name__ == "__main__":
    unittest.main()
