# SPDX-License-Identifier: MIT
"""A freshly provisioned clone is clean, so the runner inside it accepts it without hand edits."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_native_acceptance_cases import MODULE_FOR


class ProvisionedCloneCleanlinessTests(unittest.TestCase):

    def setUp(self):
        self.provision = MODULE_FOR("qualification_provision")

    def status(self, target):
        return self.provision.git("status", "--porcelain", "--ignored=no",
                                  repo=target).stdout

    def test_a_fresh_clone_has_an_empty_porcelain_status(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "round"
            out.mkdir()
            target = self.provision.clone(out, self.provision.head())
            self.assertTrue((target / self.provision.CLONE_MARKER).is_file())
            self.assertEqual(self.status(target), "")

    def test_the_marker_is_excluded_locally_and_never_through_a_tracked_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "round"
            out.mkdir()
            target = self.provision.clone(out, self.provision.head())
            exclude = (target / ".git" / "info" / "exclude").read_text().splitlines()
            self.assertIn("/" + self.provision.CLONE_MARKER, exclude)
            self.assertEqual(self.provision.git("diff", "--name-only", "HEAD",
                                                repo=target).stdout, "")

    def test_a_second_provision_over_its_own_clone_stays_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "round"
            out.mkdir()
            self.provision.clone(out, self.provision.head())
            target = self.provision.clone(out, self.provision.head())
            self.assertEqual(self.status(target), "")

    def test_excluding_twice_writes_the_line_once(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "round"
            out.mkdir()
            target = self.provision.clone(out, self.provision.head())
            self.provision.exclude_marker(target)
            exclude = (target / ".git" / "info" / "exclude").read_text().splitlines()
            self.assertEqual(exclude.count("/" + self.provision.CLONE_MARKER), 1)

    def provision_with_status(self, returncode, stdout, stderr=""):
        """Provision while the clone's status check answers as given, and return the refusal."""
        real = self.provision.git

        def git(*args, **kwargs):
            if args[:1] == ("status",):
                return subprocess.CompletedProcess(args, returncode, stdout, stderr)
            return real(*args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "round"
            out.mkdir()
            with mock.patch.object(self.provision, "git", git):
                with self.assertRaises(SystemExit) as refused:
                    self.provision.clone(out, self.provision.head())
        return str(refused.exception)

    def test_a_clone_left_dirty_is_refused(self):
        message = self.provision_with_status(0, "?? stray\n")
        self.assertIn("is not clean", message)

    def test_a_failed_status_check_is_refused_rather_than_read_as_clean(self):
        message = self.provision_with_status(128, "", "fatal: not a git repository")
        self.assertIn("could not check whether the clone", message)
        self.assertIn("fatal: not a git repository", message)


if __name__ == "__main__":
    unittest.main()
