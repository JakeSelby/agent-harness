# SPDX-License-Identifier: MIT
"""The command a constrained-role refusal names is one the refused client can run.

No documented install puts `harness` on `PATH`, so the refusal names the CLI by the absolute path
of the checkout the hook runs from (issue #761). These cases take the command out of the refusal
text itself and run it with a `PATH` that holds no `harness`.
Run: python3 -m unittest discover tests
"""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO
from harness_core import lifecycle

READ_ONLY = ("gatherer", "reviewer")


def named_command(reason):
    """The argv the refusal tells the client to run, up to its `role run` subcommand."""
    head = reason.split("Use ", 1)[1].split(" role run ", 1)[0]
    return shlex.split(head)


class RefusalCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": self.temp.name, "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()

    def reason(self, name, runtime):
        fields = lifecycle.constrained_role(name)
        self.assertIsNotNone(fields, name + " is no longer held to an isolated worker")
        return lifecycle.role_deny(runtime, name, fields)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_the_named_command_is_this_checkout_s_cli_by_absolute_path(self):
        for name in READ_ONLY:
            for runtime in ("claude-code", "codex"):
                with self.subTest(role=name, runtime=runtime):
                    argv = named_command(self.reason(name, runtime))
                    self.assertEqual(len(argv), 1, argv)
                    self.assertTrue(Path(argv[0]).is_absolute(), argv[0])
                    self.assertEqual(Path(argv[0]).resolve(), (REPO / "bin" / "harness").resolve())
                    self.assertTrue(os.access(argv[0], os.X_OK), argv[0] + " is not executable")

    def test_the_named_command_runs_with_no_harness_on_path(self):
        # Only the interpreter the shebang asks for; nothing that could hold a `harness`.
        bare = Path(self.temp.name) / "bin"
        bare.mkdir()
        (bare / "python3").symlink_to(os.path.realpath(sys.executable))
        self.assertIsNone(shutil.which("harness", path=str(bare)))
        argv = named_command(self.reason("reviewer", "claude-code"))
        env = dict(os.environ, PATH=str(bare))
        result = subprocess.run(argv + ["role", "--help"], env=env, cwd=self.temp.name,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("{run,status}", result.stdout)

    def test_a_checkout_path_with_a_space_is_quoted_for_the_shell(self):
        root = Path(self.temp.name) / "my checkout"
        with patch.object(lifecycle, "ROOT", root):
            argv = shlex.split(lifecycle.harness_command())
        self.assertEqual(argv, [str(root / "bin" / "harness")])


if __name__ == "__main__":
    unittest.main()
