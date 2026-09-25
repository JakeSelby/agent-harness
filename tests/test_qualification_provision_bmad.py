# SPDX-License-Identifier: MIT
"""The provisioned BMad root is installed with the command docs/bmad.md gives the optional suite."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_native_acceptance_cases import MODULE_FOR

DOCS = Path(__file__).resolve().parents[1] / "docs" / "bmad.md"


def documented_suite_install():
    """The optional suite's install line from docs/bmad.md, continuations joined, as argv."""
    lines = DOCS.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if "--directory <framework-root>" in line)
    command = ""
    for line in lines[start:]:
        command += line.rstrip().rstrip("\\") + " "
        if not line.rstrip().endswith("\\"):
            break
    version = next(line.split("=", 1)[1] for line in reversed(lines[:start])
                   if line.startswith("BMAD_VERSION="))
    return shlex.split(command.replace('"$BMAD_VERSION"', version))


class ProvisionedBmadInstallTests(unittest.TestCase):

    def setUp(self):
        self.provision = MODULE_FOR("qualification_provision")

    def test_the_install_is_the_documented_suite_command_flag_for_flag(self):
        documented = documented_suite_install()
        self.assertEqual(documented[documented.index("--directory") + 1], "<framework-root>")
        expected = [item if item != "<framework-root>" else "/round/bmad" for item in documented]
        self.assertEqual(self.provision.bmad_install_args(Path("/round/bmad")), expected)

    def test_the_install_carries_the_compatibility_shims(self):
        # Without them `integration apply bmad` exits 1 on legacy review-name drift (#762).
        self.assertIn("--shims", self.provision.bmad_install_args(Path("/round/bmad")))

    def test_provisioning_runs_exactly_that_install(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            target = out / self.provision.BMAD
            calls = []

            def fake_run(args, cwd=None, timeout=None):
                calls.append([str(item) for item in args])
                if args[0] == "npx":
                    (target / "_bmad").mkdir(parents=True)
                return subprocess.CompletedProcess(args, 0, "", "")

            with mock.patch.object(self.provision, "run", side_effect=fake_run), \
                    mock.patch.object(self.provision.shutil, "which", return_value="/usr/bin/npx"):
                path, note = self.provision.bmad(out)
            self.assertEqual((path, note), (target, ""))
            self.assertIn(self.provision.bmad_install_args(target), calls)


if __name__ == "__main__":
    unittest.main()
