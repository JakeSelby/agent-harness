# SPDX-License-Identifier: MIT
"""Each scripted case drives `bin/harness` with the contract the CLI actually has.

The first live round of the scripted cases failed three of them on the driver, not on the
behaviour under test: `role run` without the `--runtime` it requires, `task save` given the JSON
contract where it reads a file path, and `uninstall` expected to exit 2 in a run that left it
nothing to preserve. Earlier tests fed the drivers' values straight into the library and so never
met the CLI's argument parsing. These go through it: `role run` through the real parser and
handler with only the worker stubbed, and the other two through the real CLI in a disposable
home. No client is launched.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import harness
from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in


def disposable_home(directory):
    home = home_in(directory)
    home.project = home.root / "project"
    home.project.mkdir()
    return home


def codex_home(directory):
    home = MODULE.CodexHome.__new__(MODULE.CodexHome)
    home.root = Path(directory)
    home.project = home.root / "project"
    home.project.mkdir()
    home.client_dir = home.root / ".codex"
    return home


class RoleRunTests(unittest.TestCase):
    """`role_run` is parsed and checked by the CLI's own `role` parser and `cmd_role`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brief = Path(self.tmp.name) / "brief.md"
        self.brief.write_text(MODULE.GATHER_BRIEF)

    def drive(self, home, argv_filter=None):
        """Run `role_run` against `harness.main`; return (exit code, stderr, worker calls)."""
        calls = []

        def worker(*args, **kwargs):
            calls.append(args)
            return {"status": "completed", "mode": "isolated-cli"}

        def cli(*args, **kwargs):
            argv = list(argv_filter(args) if argv_filter else args)
            err = io.StringIO()
            with patch.object(harness.workers, "run", side_effect=worker), \
                    patch.object(harness, "load_config", return_value={}), \
                    redirect_stdout(io.StringIO()), redirect_stderr(err):
                code = harness.main(argv)
            return code, err.getvalue()

        home.harness = cli
        code, err = MODULE.role_run(home, "gatherer", self.brief)
        return code, err, calls

    def test_the_driver_passes_the_runtime_the_cli_requires(self):
        code, err, calls = self.drive(disposable_home(self.tmp.name))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "claude-code")
        self.assertEqual(calls[0][3], "gatherer")

    def test_the_runtime_is_the_client_under_test_rather_than_a_constant(self):
        code, _, calls = self.drive(codex_home(self.tmp.name))
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][2], "codex")

    def test_the_same_argv_without_the_runtime_is_the_refusal_the_round_observed(self):
        def drop_runtime(args):
            args = list(args)
            at = args.index("--runtime")
            return args[:at] + args[at + 2:]

        code, err, calls = self.drive(disposable_home(self.tmp.name), drop_runtime)
        self.assertEqual(code, 1)
        self.assertIn("role run requires a role, --runtime and --prompt-file", err)
        self.assertEqual(calls, [])


class TaskSaveTests(unittest.TestCase):
    """`save_task` runs the real `harness task save`, whose `--input` is a file path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = disposable_home(self.tmp.name)
        self.repo = MODULE.task_repo(self.home)

    def test_the_contract_is_passed_as_a_file_and_saved(self):
        MODULE.save_task(self.home, self.repo, "claude-code", 0)
        self.assertEqual(MODULE.task_revision(self.repo), 1)
        record = json.loads((self.repo / ".agent-harness" / "task.json").read_text())
        self.assertEqual(record["objective"], MODULE.TASK_OBJECTIVE)

    def test_the_whole_revision_sequence_the_case_runs_holds_through_the_cli(self):
        MODULE.save_task(self.home, self.repo, "claude-code", 0)
        MODULE.save_task(self.home, self.repo, "codex", 1)
        self.assertEqual(MODULE.task_revision(self.repo), 2)
        stale = MODULE.save_task(self.home, self.repo, "codex", 1, expected=1)
        self.assertIn(MODULE.STALE_SAVE, stale)

    def test_the_contract_file_is_outside_the_repository_so_the_record_starts_current(self):
        MODULE.save_task(self.home, self.repo, "claude-code", 0)
        shown = json.loads(self.home.harness("task", "show", cwd=self.repo))
        self.assertEqual(shown["status"], "current")

    def test_json_text_as_input_is_what_the_cli_refuses(self):
        with self.assertRaises(AssertionError) as caught:
            self.home.harness("task", "save", "--runtime", "claude-code", "--revision", "0",
                              "--input", MODULE.task_contract(), cwd=self.repo)
        self.assertIn("returned 1", str(caught.exception))
        self.assertIsNone(MODULE.task_revision(self.repo))

    def test_the_help_says_input_is_a_path(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            harness.main(["task", "--help"])
        self.assertIn("path to a JSON task contract", " ".join(out.getvalue().split()))


class MigrationUninstallTests(unittest.TestCase):
    """The uninstall case against the real CLI, with only the closing native turn stubbed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = disposable_home(self.tmp.name)

    def test_the_case_passes_against_the_cli_it_drives(self):
        with patch.object(MODULE.Home, "session", return_value={"result": "PRESERVED\nNONE"}):
            note = MODULE.case_migration_uninstall(self.home)
        self.assertIn(MODULE.PRESERVED, note)
        settings = json.loads((self.home.client_dir / "settings.json").read_text())
        self.assertEqual(settings[MODULE.HAND_EDIT_KEY[0]], MODULE.HAND_EDIT_VALUE)
        self.assertEqual(settings["env"], {MODULE.OWN_KEY: "kept"})

    def test_without_a_hand_edit_uninstall_exits_0_and_reports_nothing_preserved(self):
        # The CLI's contract the case used to miss: exit 2 and a preservation line need a conflict.
        self.home.seed()
        MODULE.seed_prior_install(self.home)
        self.home.harness("sync", expected=2)
        self.home.harness("sync", "--adopt")
        removed = self.home.harness("uninstall", expected=0)
        self.assertNotIn(MODULE.PRESERVED, removed)

    def test_a_setting_the_store_does_not_own_is_unverified_rather_than_edited(self):
        self.home.client_dir.mkdir()
        (self.home.client_dir / "settings.json").write_text("{}\n")
        with self.assertRaises(MODULE.Unverified):
            MODULE.hand_edit_owned_setting(self.home)
        self.assertEqual((self.home.client_dir / "settings.json").read_text(), "{}\n")


if __name__ == "__main__":
    unittest.main()
