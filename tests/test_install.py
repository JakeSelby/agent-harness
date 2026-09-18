# SPDX-License-Identifier: MIT
"""Unit tests for the installer's handling of tools that are not on the machine."""
import argparse
import contextlib
import io
import importlib.machinery
import importlib.util
import os
import stat
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)


@contextlib.contextmanager
def loud():
    """The suite runs quiet; these tests are about what the installer prints."""
    prior = os.environ.pop("HARNESS_QUIET", None)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield buf
    finally:
        if prior is not None:
            os.environ["HARNESS_QUIET"] = prior


class ToolLookupTests(unittest.TestCase):
    def test_path_wins(self):
        with unittest.mock.patch.object(harness.shutil, "which", return_value="/usr/bin/gh"):
            self.assertEqual(harness._tool("gh"), "/usr/bin/gh")

    def test_keg_only_bin_is_searched_when_path_misses(self):
        with tempfile.TemporaryDirectory() as tmp:
            npm = Path(tmp) / "npm"
            npm.write_text("#!/bin/sh\n")
            npm.chmod(npm.stat().st_mode | stat.S_IXUSR)
            with unittest.mock.patch.object(harness.shutil, "which", return_value=None), \
                 unittest.mock.patch.object(harness, "KEG_ONLY_BINS", [tmp]):
                self.assertEqual(harness._tool("npm"), str(npm))

    def test_missing_everywhere_is_none(self):
        with unittest.mock.patch.object(harness.shutil, "which", return_value=None), \
             unittest.mock.patch.object(harness, "KEG_ONLY_BINS", []):
            self.assertIsNone(harness._tool("npm"))

    def test_a_non_executable_file_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "npm").write_text("not executable\n")
            with unittest.mock.patch.object(harness.shutil, "which", return_value=None), \
                 unittest.mock.patch.object(harness, "KEG_ONLY_BINS", [tmp]):
                self.assertIsNone(harness._tool("npm"))


class RunTests(unittest.TestCase):
    def test_missing_executable_is_reported_not_raised(self):
        with unittest.mock.patch.object(harness, "_tool", return_value=None):
            with loud() as out:
                ok = harness._run(["npm", "install", "-g", "@openai/codex"], dry=False)
        self.assertFalse(ok)
        self.assertIn("npm is not installed", out.getvalue())

    def test_a_missing_executable_never_reaches_subprocess(self):
        with unittest.mock.patch.object(harness, "_tool", return_value=None), \
             unittest.mock.patch.object(harness.subprocess, "run") as run:
            harness._run(["npm", "--version"], dry=False)
        run.assert_not_called()

    def test_absolute_paths_bypass_lookup(self):
        with unittest.mock.patch.object(harness, "_tool", return_value=None), \
             unittest.mock.patch.object(harness.subprocess, "run") as run:
            self.assertTrue(harness._run(["/bin/bash", "-c", "true"], dry=False))
        run.assert_called_once()

    def test_dry_run_resolves_but_does_not_execute(self):
        with unittest.mock.patch.object(harness, "_tool", return_value="/usr/bin/gh"), \
             unittest.mock.patch.object(harness.subprocess, "run") as run:
            self.assertTrue(harness._run(["gh", "--version"], dry=True))
        run.assert_not_called()

    def test_the_resolved_path_is_what_runs(self):
        with unittest.mock.patch.object(harness, "_tool", return_value="/keg/bin/npm"), \
             unittest.mock.patch.object(harness.subprocess, "run") as run:
            harness._run(["npm", "--version"], dry=False)
        self.assertEqual(run.call_args[0][0], ["/keg/bin/npm", "--version"])


class GhLoginLineTests(unittest.TestCase):
    def test_absent_gh_is_named_and_never_invoked(self):
        with unittest.mock.patch.object(harness, "_tool", return_value=None), \
             unittest.mock.patch.object(harness.subprocess, "run") as run:
            line = harness._gh_login_line()
        run.assert_not_called()
        self.assertIn("not installed", line)

    def test_present_but_logged_out(self):
        with unittest.mock.patch.object(harness, "_tool", return_value="/usr/bin/gh"), \
             unittest.mock.patch.object(harness.subprocess, "run",
                                        return_value=unittest.mock.Mock(returncode=1)):
            self.assertIn("gh auth login", harness._gh_login_line())

    def test_present_and_logged_in(self):
        with unittest.mock.patch.object(harness, "_tool", return_value="/usr/bin/gh"), \
             unittest.mock.patch.object(harness.subprocess, "run",
                                        return_value=unittest.mock.Mock(returncode=0)):
            self.assertEqual(harness._gh_login_line(), "logged in")


class InstallOnABareMachineTests(unittest.TestCase):
    """A machine with no brew, no npm, no gh: install reports, and finishes."""

    def _args(self):
        return argparse.Namespace(dry_run=True, no_brew=False, no_apps=False, no_vscode=False,
                                  no_codex=False, with_optional=False, adopt=False,
                                  adopt_codex=False)

    def test_install_completes_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            prior_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                with unittest.mock.patch.object(harness, "_tool", return_value=None), \
                     unittest.mock.patch.object(harness.shutil, "which", return_value=None), \
                     unittest.mock.patch.object(harness.platform, "system", return_value="Linux"):
                    with loud() as out:
                        rc = harness.cmd_install(self._args())
            finally:
                if prior_home is not None:
                    os.environ["HOME"] = prior_home
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("npm is not installed", text)
        self.assertIn("gh       — not installed", text)


if __name__ == "__main__":
    unittest.main()
