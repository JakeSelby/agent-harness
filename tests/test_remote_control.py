# SPDX-License-Identifier: MIT
"""Tests for the per-folder Remote Control launch agents."""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import remote_control  # noqa: E402

loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)


class SettingsTests(unittest.TestCase):
    def test_defaults_serve_nothing_in_worktree_mode(self):
        opts = remote_control.settings({})
        self.assertEqual(opts["folders"], [])
        self.assertEqual(opts["spawn"], "worktree")
        self.assertEqual(opts["permission_mode"], "default")

    def test_example_config_is_valid(self):
        example = json.loads((REPO / "config.example.json").read_text())
        self.assertEqual(remote_control.settings(example)["folders"], [])

    def test_folders_resolve_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            opts = remote_control.settings({"remote_control": {"folders": [tmp, tmp + "/"]}})
            self.assertEqual(opts["folders"], [Path(tmp).resolve()])

    def test_bad_values_are_rejected(self):
        for block in ({"spawn": "fork"}, {"permission_mode": "yolo"}, {"folders": "/x"},
                      {"folders": [""]}, {"folder": []}):
            with self.subTest(block=block), self.assertRaises(ValueError):
                remote_control.settings({"remote_control": block})


class PlistTests(unittest.TestCase):
    OPTS = {"spawn": "worktree", "permission_mode": "auto", "keep_awake": False}

    def test_labels_differ_for_same_named_folders(self):
        a, b = remote_control.label("/one/api"), remote_control.label("/two/api")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith(remote_control.LABEL_PREFIX + "api-"))

    def test_plist_runs_the_server_in_the_folder(self):
        body = remote_control.render("/work/My Repo", self.OPTS, "/opt/tools/claude", "/home/u", "/logs")
        data = plistlib.loads(body)
        self.assertEqual(data["ProgramArguments"], [
            "/opt/tools/claude", "remote-control", "--name", "My Repo", "--spawn", "worktree",
            "--permission-mode", "auto", "--no-create-session-in-dir"])
        self.assertEqual(data["WorkingDirectory"], "/work/My Repo")
        self.assertTrue(data["KeepAlive"] and data["RunAtLoad"])
        self.assertEqual(data["ThrottleInterval"], remote_control.THROTTLE_SECONDS)
        self.assertEqual(data["EnvironmentVariables"]["PATH"].split(":")[0], "/opt/tools")
        self.assertIn("/usr/bin", data["EnvironmentVariables"]["PATH"].split(":"))

    def test_keep_awake_wraps_the_server(self):
        argv = remote_control.command("/w/r", dict(self.OPTS, keep_awake=True), "/bin/claude")
        self.assertEqual(argv[:3], ["/usr/bin/caffeinate", "-is", "/bin/claude"])


class TrustAndPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.trusted = self.base / "trusted"
        self.nested = self.trusted / "pkg"
        self.untrusted = self.base / "untrusted"
        for d in (self.nested, self.untrusted):
            d.mkdir(parents=True)
        self.state = self.base / ".claude.json"
        self.state.write_text(json.dumps({"projects": {
            str(self.trusted): {"hasTrustDialogAccepted": True},
            str(self.untrusted): {"hasTrustDialogAccepted": False}}}))
        self.agents = self.base / "LaunchAgents"

    def tearDown(self):
        self.tmp.cleanup()

    def test_trust_is_read_from_the_folder_or_a_parent(self):
        self.assertTrue(remote_control.trusted(self.trusted, self.state))
        self.assertTrue(remote_control.trusted(self.nested, self.state))
        self.assertFalse(remote_control.trusted(self.untrusted, self.state))

    def test_missing_or_corrupt_state_is_untrusted(self):
        self.assertFalse(remote_control.trusted(self.trusted, self.base / "absent.json"))
        self.state.write_text("{")
        self.assertFalse(remote_control.trusted(self.trusted, self.state))

    def test_plan_skips_untrusted_and_missing_and_finds_stale(self):
        self.agents.mkdir()
        stale = remote_control.LABEL_PREFIX + "gone-00000000"
        (self.agents / (stale + ".plist")).write_bytes(b"")
        (self.agents / "com.other.thing.plist").write_bytes(b"")
        opts = {"folders": [self.trusted, self.untrusted, self.base / "absent"]}
        serve, skipped, found = remote_control.plan(opts, self.agents, self.state)
        self.assertEqual(serve, [self.trusted])
        self.assertEqual([f for f, _ in skipped], [self.untrusted, self.base / "absent"])
        self.assertIn("trust", skipped[0][1])
        self.assertEqual(found, [stale])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.folder = self.home / "repos" / "project"
        self.folder.mkdir(parents=True)
        self.other = self.home / "repos" / "untrusted"
        self.other.mkdir()
        (self.home / ".claude.json").write_text(json.dumps(
            {"projects": {str(self.folder): {"hasTrustDialogAccepted": True}}}))
        self.write_config([str(self.folder), str(self.other)])
        self.calls = []
        self.loaded = set()
        patches = [
            mock.patch.dict(os.environ, {"HARNESS_HOME": str(self.home)}),
            mock.patch.object(harness.platform, "system", return_value="Darwin"),
            mock.patch.object(harness.shutil, "which", return_value="/opt/tools/claude"),
            mock.patch.object(harness, "launchctl", side_effect=self.launchctl),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # patch.dict restores both on cleanup; other suites leave HARNESS_QUIET set, which mutes say().
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ.pop("HARNESS_QUIET", None)
        self.addCleanup(self.tmp.cleanup)

    def write_config(self, folders):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"remote_control": {"folders": folders, "permission_mode": "auto"}}))

    def launchctl(self, *args):
        self.calls.append(args)
        name = args[-1].split("/")[-1]
        if args[0] == "bootstrap":
            self.loaded.add(Path(args[-1]).stem)
        elif args[0] == "bootout":
            self.loaded.discard(name)
        code = 0 if args[0] != "print" or name in self.loaded else 113
        return subprocess.CompletedProcess(args, code, stdout="\tstate = running\n", stderr="")

    def run_action(self, action, dry_run=False):
        out = StringIO()
        with redirect_stdout(out):
            code = harness.cmd_remote_control(argparse.Namespace(action=action, dry_run=dry_run))
        return code, out.getvalue()

    def plist_path(self, folder):
        return self.home / "Library" / "LaunchAgents" / (remote_control.label(folder) + ".plist")

    def test_install_loads_trusted_folder_and_reports_untrusted(self):
        code, out = self.run_action("install")
        self.assertEqual(code, 0)
        data = plistlib.loads(self.plist_path(self.folder).read_bytes())
        self.assertEqual(data["WorkingDirectory"], str(self.folder))
        self.assertIn("auto", data["ProgramArguments"])
        self.assertFalse(self.plist_path(self.other).exists())
        self.assertIn(f"skipped {self.other}", out)
        self.assertIn("bootstrap", [c[0] for c in self.calls])

    def test_reinstall_leaves_a_loaded_unchanged_agent_alone(self):
        self.run_action("install")
        self.calls.clear()
        _, out = self.run_action("install")
        self.assertIn("unchanged", out)
        self.assertEqual({c[0] for c in self.calls}, {"print"})

    def test_dry_run_writes_nothing(self):
        _, out = self.run_action("install", dry_run=True)
        self.assertIn("would serve", out)
        self.assertFalse(self.plist_path(self.folder).exists())
        self.assertEqual({c[0] for c in self.calls}, {"print"})

    def test_dropping_a_folder_removes_its_agent(self):
        self.run_action("install")
        self.write_config([])
        self.run_action("install")
        self.assertFalse(self.plist_path(self.folder).exists())
        self.assertNotIn(remote_control.label(self.folder), self.loaded)

    def test_status_reports_state_and_skips(self):
        self.run_action("install")
        _, out = self.run_action("status")
        self.assertIn(f"{self.folder}: running", out)
        self.assertIn(f"{self.other}: skipped", out)

    def test_uninstall_removes_every_agent(self):
        self.run_action("install")
        code, _ = self.run_action("uninstall")
        self.assertEqual(code, 0)
        self.assertFalse(self.plist_path(self.folder).exists())
        self.assertEqual(self.loaded, set())

    def test_bootstrap_failure_is_a_nonzero_exit(self):
        def fail(*args):
            return subprocess.CompletedProcess(args, 5 if args[0] != "bootout" else 0, stdout="", stderr="Input/output error")
        with mock.patch.object(harness, "launchctl", side_effect=fail):
            code, out = self.run_action("install")
        self.assertEqual(code, 1)
        self.assertIn("Input/output error", out)

    def test_other_platforms_do_nothing(self):
        with mock.patch.object(harness.platform, "system", return_value="Linux"):
            code, _ = self.run_action("install")
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])

    def test_invalid_config_exits(self):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.write_text(json.dumps({"remote_control": {"spawn": "fork"}}))
        with self.assertRaises(SystemExit):
            self.run_action("status")


if __name__ == "__main__":
    unittest.main()
