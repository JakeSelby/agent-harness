"""`harness role run` refuses a read directory broad enough to expose other runs' files."""
import argparse
import contextlib
import copy
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import CFG, harness
from harness_core import workers


class BroadReadRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "user"
        self.home.mkdir()
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.home), "PATH": os.environ["PATH"]}, clear=True).start()

    def refusal(self, path):
        with self.assertRaises(ValueError) as caught:
            workers.granted_roots([str(path)])
        return str(caught.exception)

    def test_the_filesystem_root_home_and_temporary_roots_are_refused(self):
        for path in ["/", self.home, "/tmp", "/var/tmp", tempfile.gettempdir()]:
            with self.subTest(path=path):
                message = self.refusal(path)
                self.assertIn(str(Path(path).resolve()), message)
                self.assertIn("mktemp -d /tmp/harness-inputs.XXXXXX", message)

    def test_a_directory_above_home_or_a_temporary_root_is_refused(self):
        self.assertIn("above the home directory", self.refusal(self.home.parent))
        above = Path(tempfile.gettempdir()).resolve().parent
        expected = "the filesystem root" if above == Path("/") else "above a system temporary root"
        self.assertIn(expected, self.refusal(above))

    def test_a_dedicated_subdirectory_is_still_accepted(self):
        dedicated = Path(tempfile.mkdtemp(prefix="harness-inputs.", dir="/tmp")).resolve()
        self.addCleanup(dedicated.rmdir)
        inside_home = self.home / "artifacts"
        inside_home.mkdir()
        self.assertEqual(workers.granted_roots([str(dedicated), str(inside_home)]), [dedicated, inside_home])

    def test_a_missing_or_file_read_dir_keeps_its_own_error(self):
        target = self.base / "brief.md"
        target.write_text("brief")
        with self.assertRaisesRegex(ValueError, "must name an existing directory"):
            workers.granted_roots([str(target)])
        with self.assertRaises(FileNotFoundError):
            workers.granted_roots([str(self.base / "absent")])

    def test_role_run_refuses_tmp_before_any_worker_starts(self):
        brief = self.base / "brief.md"
        brief.write_text("Review the diff")
        state = self.home / ".local/state/agent-harness/workers"
        args = argparse.Namespace(action="run", name="reviewer", runtime="claude-code", prompt_file=str(brief),
                                  workspace=str(self.workspace), model="fixture-model", artifact=None,
                                  timeout=300, read_dir=["/tmp"])
        stderr = io.StringIO()
        with patch.object(harness, "load_config", return_value=copy.deepcopy(CFG)), \
             patch.object(workers, "execute") as execute, contextlib.redirect_stderr(stderr):
            self.assertEqual(harness.cmd_role(args), 1)
        execute.assert_not_called()
        self.assertIn("--read-dir " + str(Path("/tmp").resolve()) + " is a system temporary root", stderr.getvalue())
        self.assertFalse(state.exists(), "a refused run must leave no worker record")


if __name__ == "__main__":
    unittest.main()
