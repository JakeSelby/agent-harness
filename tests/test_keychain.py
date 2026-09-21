"""A client launched under a substituted HOME on macOS never meets a home without a keychain."""
import contextlib
import io
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import harness, TempHome
from harness_core import keychain, workers


def completed(code, stderr=""):
    return subprocess.CompletedProcess([], code, stdout="", stderr=stderr)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)


class MissingTests(TempDir):
    def test_other_hosts_never_report_a_missing_keychain(self):
        self.assertFalse(keychain.missing(self.home, host="Linux"))

    def test_macos_reports_a_home_without_one_and_accepts_a_home_with_one(self):
        self.assertTrue(keychain.missing(self.home, host="Darwin"))
        path = keychain.default_path(self.home)
        path.parent.mkdir(parents=True)
        path.touch()
        self.assertFalse(keychain.missing(self.home, host="Darwin"))

    def test_the_default_home_is_the_environment_one(self):
        with patch.dict(os.environ, {"HOME": str(self.home)}):
            self.assertTrue(keychain.missing(host="Darwin"))


class ProvisionTests(TempDir):
    def test_other_hosts_run_nothing(self):
        with patch.object(keychain.subprocess, "run", side_effect=AssertionError("a process ran")):
            self.assertIsNone(keychain.provision(self.home, host="Linux"))
        self.assertFalse((self.home / "Library").exists())

    def test_macos_creates_the_keychain_inside_the_substituted_home(self):
        with patch.object(keychain.subprocess, "run", return_value=completed(0)) as ran:
            path = keychain.provision(self.home, host="Darwin")
        self.assertEqual(path, self.home / "Library" / "Keychains" / "login.keychain-db")
        self.assertTrue(path.parent.is_dir())
        create = ran.call_args_list[0]
        self.assertEqual(create.args[0][:4], ["security", "create-keychain", "-p", ""])
        self.assertEqual(create.args[0][-1], str(path))
        for call in ran.call_args_list:
            self.assertEqual(call.kwargs["env"]["HOME"], str(self.home))

    def test_an_existing_keychain_is_left_alone(self):
        path = keychain.default_path(self.home)
        path.parent.mkdir(parents=True)
        path.write_text("kept")
        with patch.object(keychain.subprocess, "run", side_effect=AssertionError("a process ran")):
            self.assertIsNone(keychain.provision(self.home, host="Darwin"))
        self.assertEqual(path.read_text(), "kept")

    def test_a_keychain_that_cannot_be_created_raises(self):
        with patch.object(keychain.subprocess, "run", return_value=completed(1, "could not create")):
            with self.assertRaisesRegex(OSError, "could not create"):
                keychain.provision(self.home, host="Darwin")


class WorkerEnvironmentTests(TempDir):
    def test_the_worker_home_is_provisioned_before_any_client_launch(self):
        with patch.object(workers.keychain, "provision") as provision:
            env = workers.environment({"PATH": os.environ["PATH"]}, self.home)
        provision.assert_called_once_with(env["HOME"])

    def test_a_home_without_a_keychain_refuses_the_worker(self):
        with patch.object(workers.keychain, "provision", side_effect=OSError("no keychain")):
            with self.assertRaisesRegex(ValueError, "no keychain"):
                workers.environment({"PATH": os.environ["PATH"]}, self.home)


class DoctorTests(TempHome):
    """`harness doctor` runs the installed client's own doctor, which stores a keychain item."""

    def setUp(self):
        super().setUp()
        self.bin = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.bin, ignore_errors=True)
        executable = self.bin / "claude"
        executable.write_text("#!/bin/sh\ntouch '%s'\necho fine\n" % (self.bin / "launched"),
                              encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    def doctor(self):
        os.environ.pop("HARNESS_QUIET", None)
        buffer = io.StringIO()
        path = str(self.bin) + os.pathsep + os.environ["PATH"]
        with patch.dict(os.environ, {"PATH": path}), \
                patch.object(harness, "_version_of", return_value="stub"), \
                patch.object(keychain.platform, "system", return_value="Darwin"), \
                contextlib.redirect_stdout(buffer):
            harness.cmd_doctor(harness.argparse.Namespace())
        return buffer.getvalue()

    def test_a_home_without_a_keychain_never_launches_the_client(self):
        text = self.doctor()
        self.assertFalse((self.bin / "launched").exists())
        self.assertIn("claude doctor: skipped", text)

    def test_a_home_with_a_keychain_still_runs_the_client_doctor(self):
        path = keychain.default_path(self.home)
        path.parent.mkdir(parents=True)
        path.touch()
        text = self.doctor()
        self.assertTrue((self.bin / "launched").exists())
        self.assertNotIn("skipped", text)


class CommandTests(TempDir):
    """`harness keychain HOME` is the same guard for a home built by hand."""

    def run_command(self, home):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = harness.cmd_keychain(harness.argparse.Namespace(home=str(home)))
        return code, buffer.getvalue()

    def test_it_provisions_the_named_home(self):
        made = keychain.default_path(self.home)
        with patch.object(harness.keychain, "provision", return_value=made) as provision:
            code, text = self.run_command(self.home)
        provision.assert_called_once_with(self.home.resolve())
        self.assertEqual((code, text.strip()), (0, str(made)))

    def test_it_refuses_your_own_home(self):
        with patch.object(harness.Path, "home", return_value=self.home), \
                patch.object(harness.keychain, "provision", side_effect=AssertionError("ran")):
            with self.assertRaisesRegex(SystemExit, "your own home"):
                self.run_command(self.home)

    def test_it_refuses_a_path_that_is_not_a_directory(self):
        with self.assertRaisesRegex(SystemExit, "not a directory"):
            self.run_command(self.home / "absent")

    def test_a_keychain_that_cannot_be_created_says_not_to_launch(self):
        with patch.object(harness.keychain, "provision", side_effect=OSError("could not create")):
            with self.assertRaisesRegex(SystemExit, "Do not launch a client"):
                self.run_command(self.home)


if __name__ == "__main__":
    unittest.main()
