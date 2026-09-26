# SPDX-License-Identifier: MIT
"""`harness stances` and `harness sync` read one resolver, layer by layer.

`posture.selection()` is the only place stance precedence is decided. The CLI hands it layers
and takes its answer whole; a sync hands it the user-default layers only, because a session or
project override never rewrites the user's global selection. So for every layer a sync applies,
the two commands agree exactly, and for every layer a session scopes to itself, a sync applies
what `harness stances` prints once that layer is withheld.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent

loader = importlib.machinery.SourceFileLoader("harness_stance_parity", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness_stance_parity", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

LINK = re.compile(r"harness-stances/([a-z0-9-]+)\.md\s+->\s+\S+/stances/\1/([a-z0-9-]+)\.md$")


class Resolver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / "config.json"
        self.config.write_text(json.dumps({"stances": {"voice": "answer-card", "testing": "off"}}),
                               encoding="utf-8")

    def test_load_config_takes_the_resolvers_stances_and_merges_no_layer_of_its_own(self):
        answer = {"stances": {"testing": "required", "custom": None}}
        with patch.object(harness, "config_path", return_value=self.config), \
                patch.object(harness, "load_selection", return_value=answer) as resolver:
            cfg = harness.load_config({})
        # The user file names voice and testing; only the resolver's answer survives.
        self.assertEqual(cfg["stances"], {"testing": "required"})
        resolver.assert_called_once()

    def test_user_defaults_env_withholds_every_session_scoped_layer(self):
        env = {"PATH": "/bin", "HARNESS_HOME": "/h", "HARNESS_STANCE_TESTING": "off",
               "HARNESS_IDENTITY_NAME": "x", "HARNESS_MANAGE_CODEX": "0"}
        env.update({name: "v" for name in harness.SESSION_SCOPED})
        self.assertEqual(harness.user_defaults_env(env),
                         {"PATH": "/bin", "HARNESS_HOME": "/h", "HARNESS_MANAGE_CODEX": "0"})


class Parity(unittest.TestCase):
    """Each layer set in turn, with `harness stances --json` beside `harness sync --dry-run`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / ".config" / "agent-harness").mkdir(parents=True)

    def user(self, data):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(json.dumps(data), encoding="utf-8")

    def file(self, name, data):
        path = self.home / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def run_cli(self, env, *args):
        merged = dict(without_harness_vars(), HOME=str(self.home), **env)
        out = subprocess.run([sys.executable, str(REPO / "bin" / "harness")] + list(args),
                             capture_output=True, text=True, env=merged)
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        return out.stdout

    def printed(self, env):
        data = json.loads(self.run_cli(env, "stances", "--json"))
        return {name: choice["variant"] for name, choice in data["stances"].items()}, data["sources"]

    def applied(self, env):
        """What a sync links into place, read from the dry run's own link lines."""
        out = self.run_cli(env, "sync", "--dry-run")
        links = dict(match.groups() for match in map(LINK.search, out.splitlines()) if match)
        self.assertTrue(links, out)
        return links, out

    def test_the_default_layer_agrees(self):
        printed, sources = self.printed({})
        self.assertEqual(set(sources.values()), {"default"})
        self.assertEqual(self.applied({})[0], printed)

    def test_the_user_layer_agrees(self):
        self.user({"stances": {"testing": "off", "voice": "answer-card"}})
        printed, sources = self.printed({})
        self.assertEqual((printed["testing"], sources["testing"]), ("off", "user"))
        self.assertEqual(self.applied({})[0], printed)

    def test_a_user_selected_mode_agrees(self):
        roots = self.home / "roots"
        (roots / "modes").mkdir(parents=True)
        mode = {"schema_version": 1, "description": "a test mode", "stances": {"testing": "off"}}
        (roots / "modes" / "focus.json").write_text(json.dumps(mode), encoding="utf-8")
        self.user({"mode": "focus", "primitive_roots": [str(roots)]})
        printed, sources = self.printed({})
        self.assertEqual((printed["testing"], sources["testing"]), ("off", "mode:focus"))
        self.assertEqual(self.applied({})[0], printed)

    def test_each_session_scoped_layer_stays_in_the_session(self):
        self.user({"stances": {"voice": "answer-card"}})
        defaults = self.printed({})[0]
        chosen = {"stances": {"testing": "off"}}
        for name, env in (("project", {"HARNESS_PROJECT_CONFIG": self.file("project.json", chosen)}),
                          ("session", {"HARNESS_SESSION_CONFIG": self.file("session.json", chosen)}),
                          ("session", {"HARNESS_STANCE_TESTING": "off"})):
            with self.subTest(layer=sorted(env)):
                printed, sources = self.printed(env)
                # The layer bites in the session...
                self.assertEqual((printed["testing"], sources["testing"]), ("off", name))
                self.assertEqual(printed, dict(defaults, testing="off"))
                # ...and a sync applies the user defaults, and says why.
                links, out = self.applied(env)
                self.assertEqual(links, defaults)
                self.assertIn("project/session overrides stay in the session", out)


if __name__ == "__main__":
    unittest.main()
