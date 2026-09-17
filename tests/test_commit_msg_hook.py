# SPDX-License-Identifier: MIT
"""Unit tests for the repo-starter `commit-msg` hook.

The hook ships in `templates/repo/hooks/` and is installed per repository, so it is exercised
the way git runs it: as a subprocess handed a message file, with `HOME` pointing at a config
that selects the stance.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "templates" / "repo" / "hooks" / "commit-msg"


class CommitMsgHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self, commits):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"stances": {"commits": commits}}))

    def run_hook(self, message, env_extra=None, pass_path=True):
        msg = self.home / "COMMIT_EDITMSG"
        msg.write_text(message, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        env["HOME"] = str(self.home)
        env.update(env_extra or {})
        args = [sys.executable, str(HOOK)] + ([str(msg)] if pass_path else [])
        return subprocess.run(args, capture_output=True, text=True, env=env)

    # --- the enforcing path -------------------------------------------------

    def test_conventional_subject_passes(self):
        self.write_config("conventional-attributed")
        out = self.run_hook("feat(hooks): add a thing\n\nCo-Authored-By: A Name\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stderr, "")

    def test_bare_subject_is_refused_and_names_the_subject(self):
        self.write_config("conventional-attributed")
        out = self.run_hook("added a thing\n")
        self.assertEqual(out.returncode, 1)
        self.assertIn("added a thing", out.stderr)
        self.assertIn("type(scope): summary", out.stderr)

    def test_scope_and_breaking_marker_are_accepted(self):
        self.write_config("conventional")
        for subject in ("fix: x", "fix(core): x", "feat(a-b)!: x", "revert: x"):
            with self.subTest(subject=subject):
                self.assertEqual(self.run_hook(subject + "\n").returncode, 0)

    def test_a_type_that_is_not_in_the_list_is_refused(self):
        self.write_config("conventional")
        self.assertEqual(self.run_hook("wip: x\n").returncode, 1)

    # --- the stance gate ----------------------------------------------------

    def test_off_passes_anything(self):
        self.write_config("off")
        self.assertEqual(self.run_hook("whatever\n").returncode, 0)

    def test_as_you_go_passes_anything(self):
        self.write_config("as-you-go")
        self.assertEqual(self.run_hook("whatever\n").returncode, 0)

    def test_a_missing_config_still_enforces_the_default(self):
        out = self.run_hook("whatever\n")
        self.assertEqual(out.returncode, 1, "a deliberately installed hook should not no-op")

    def test_an_unreadable_config_falls_back_rather_than_raising(self):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text("{not json")
        out = self.run_hook("whatever\n")
        self.assertEqual(out.returncode, 1)
        self.assertNotIn("Traceback", out.stderr)

    def test_env_override_beats_the_config(self):
        self.write_config("conventional-attributed")
        out = self.run_hook("whatever\n", {"HARNESS_STANCE_COMMITS": "off"})
        self.assertEqual(out.returncode, 0)

    # --- subjects git writes ------------------------------------------------

    def test_merge_revert_and_fixup_subjects_are_exempt(self):
        self.write_config("conventional")
        for subject in ('Merge branch "main"', 'Revert "feat: x"', "fixup! feat: x",
                        "squash! feat: x", "amend! feat: x"):
            with self.subTest(subject=subject):
                self.assertEqual(self.run_hook(subject + "\n").returncode, 0)

    def test_comment_lines_are_not_the_subject(self):
        self.write_config("conventional")
        out = self.run_hook("# please enter a message\n\nfeat: real subject\n")
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_an_empty_message_is_left_to_git(self):
        self.write_config("conventional")
        self.assertEqual(self.run_hook("\n# only comments\n").returncode, 0)

    # --- the trailer warning ------------------------------------------------

    def test_attributed_warns_on_a_missing_trailer_without_failing(self):
        self.write_config("conventional-attributed")
        out = self.run_hook("feat: x\n")
        self.assertEqual(out.returncode, 0)
        self.assertIn("Co-Authored-By", out.stderr)

    def test_conventional_alone_does_not_warn_about_the_trailer(self):
        self.write_config("conventional")
        out = self.run_hook("feat: x\n")
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stderr, "")

    # --- invocation ---------------------------------------------------------

    def test_no_message_path_is_an_error_not_a_crash(self):
        self.write_config("conventional")
        out = self.run_hook("feat: x\n", pass_path=False)
        self.assertEqual(out.returncode, 1)
        self.assertNotIn("Traceback", out.stderr)

    def test_the_hook_is_executable(self):
        self.assertTrue(os.access(HOOK, os.X_OK), "git will not run a non-executable hook")


class PatternParityTests(unittest.TestCase):
    """The hook ships standalone, so its pattern is a copy. Keep the copy honest."""

    def test_the_conventional_pattern_matches_the_detector(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "d", REPO / "claude" / "hooks" / "rule-detectors.py")
        detectors = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(detectors)
        hook_src = HOOK.read_text(encoding="utf-8")
        self.assertIn(detectors.CONVENTIONAL_RE.pattern, hook_src,
                      "the hook's pattern drifted from claude/hooks/rule-detectors.py")


if __name__ == "__main__":
    unittest.main()
