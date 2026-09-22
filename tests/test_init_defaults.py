# SPDX-License-Identifier: MIT
"""Unit tests for `harness init --yes`, the non-interactive path the installer script uses."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

EXAMPLE = json.loads((REPO / "config.example.json").read_text())


@contextlib.contextmanager
def loud():
    prior = os.environ.pop("HARNESS_QUIET", None)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield buf
    finally:
        if prior is not None:
            os.environ["HARNESS_QUIET"] = prior


def options(**over):
    args = {"force": False, "yes": True, "preset": None, "name": None, "role": None,
            "github": None, "timezone": None}
    args.update(over)
    return argparse.Namespace(**args)


class InitDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = unittest.mock.patch.dict(os.environ, {"HOME": self.tmp.name,
                                                        "HARNESS_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def init(self, **over):
        with unittest.mock.patch.object(harness, "_detect_github", return_value=""), \
             unittest.mock.patch.object(harness, "_detect_git_name", return_value=""), \
             unittest.mock.patch.object(harness, "_detect_timezone", return_value="UTC"):
            with loud() as out:
                rc = harness.cmd_init(options(**over))
        return rc, out.getvalue(), harness.config_path()

    def test_no_terminal_is_needed_and_the_config_resolves(self):
        with unittest.mock.patch.object(harness.sys.stdin, "isatty", return_value=False):
            rc, _, path = self.init(name="A Name", role="Does a thing", github="a-handle")
        self.assertEqual(rc, 0)
        cfg = json.loads(path.read_text())
        self.assertEqual(cfg["identity"]["name"], "A Name")
        self.assertEqual(cfg["identity"]["github"], "a-handle")
        self.assertEqual(cfg["stances"], EXAMPLE["stances"])
        self.assertEqual(harness.placeholder_identity(cfg), [])
        harness.resolve_stances(harness.load_config(env={}))

    def test_what_the_machine_knows_is_used_and_the_rest_is_named(self):
        with unittest.mock.patch.object(harness, "_detect_github", return_value="detected"), \
             unittest.mock.patch.object(harness, "_detect_git_name", return_value="Detected Name"), \
             unittest.mock.patch.object(harness, "_detect_timezone", return_value="Europe/Lisbon"):
            with loud() as out:
                rc = harness.cmd_init(options())
        cfg = json.loads(harness.config_path().read_text())
        self.assertEqual(rc, 0)
        self.assertEqual(cfg["identity"]["name"], "Detected Name")
        self.assertEqual(cfg["identity"]["github"], "detected")
        self.assertEqual(cfg["identity"]["timezone"], "Europe/Lisbon")
        # The one field nothing on the machine can answer stays at the example value, and says so.
        self.assertEqual(harness.placeholder_identity(cfg), ["role"])
        self.assertIn("harness config set identity.role", out.getvalue())

    def test_the_general_preset_selects_its_own_stances(self):
        rc, _, path = self.init(preset="general")
        self.assertEqual(rc, 0)
        stances = json.loads(path.read_text())["stances"]
        self.assertEqual(stances["testing"], "off")
        self.assertEqual(stances["plan-ceremony"], "light")
        self.assertEqual(stances["voice"], EXAMPLE["stances"]["voice"])

    def test_an_existing_config_is_not_replaced_without_force(self):
        self.init(name="A Name", role="Does a thing", github="a-handle")
        rc, out, path = self.init(name="Another Name")
        self.assertEqual(rc, 1)
        self.assertIn("already exists", out)
        self.assertEqual(json.loads(path.read_text())["identity"]["name"], "A Name")
        rc, _, path = self.init(name="Another Name", force=True)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(path.read_text())["identity"]["name"], "Another Name")

    def test_the_interactive_path_is_untouched_by_the_new_flag(self):
        answers = iter(["A Name", "", "Does a thing", "a-handle", "UTC", "", ""]
                       + [""] * len(harness.STANCE_NAMES))
        with unittest.mock.patch("builtins.input", lambda _p: next(answers)), \
             unittest.mock.patch.object(harness.sys.stdin, "isatty", return_value=True), \
             unittest.mock.patch.object(harness, "_detect_github", return_value=""):
            with loud():
                rc = harness.cmd_init(options(yes=False))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(harness.config_path().read_text())["identity"]["name"], "A Name")


if __name__ == "__main__":
    unittest.main()
