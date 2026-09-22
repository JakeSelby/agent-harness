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


class PointerTests(unittest.TestCase):
    def test_slug_matches_claude_code_project_key(self):
        self.assertEqual(remote_control.project_slug("/u/dev/repos/app"),
                         "-u-dev-repos-app")
        self.assertEqual(
            remote_control.project_slug("/u/dev/repos/app/.claude/worktrees/bridge-cse_01A"),
            "-u-dev-repos-app--claude-worktrees-bridge-cse-01A")

    def test_payload_carries_only_validated_keys(self):
        previous = {"sessionId": "cse_01A", "environmentId": "env_01NEW", "source": "standalone",
                    "pid": 1, "procStart": "old", "activeSessionIds": ["cse_01B"],
                    "activeSessionIdsPersistedAt": 42, "somethingElse": "drop me"}
        out = remote_control.pointer_payload("env_01NEW", 77, "Tue Sep 22 13:36:19 2026", previous)
        self.assertEqual(out["environmentId"], "env_01NEW")
        self.assertEqual(out["pid"], 77)
        self.assertEqual(out["procStart"], "Tue Sep 22 13:36:19 2026")
        self.assertEqual(out["source"], "standalone")
        self.assertEqual(out["sessionId"], "cse_01A")
        self.assertEqual(out["activeSessionIds"], ["cse_01B"])
        self.assertNotIn("somethingElse", out)
        self.assertLessEqual(set(out), set(remote_control.POINTER_KEYS))

    def test_ids_from_another_environment_are_dropped(self):
        previous = {"sessionId": "cse_01A", "environmentId": "env_01OLD", "source": "standalone",
                    "activeSessionIds": ["cse_01B"], "activeSessionIdsPersistedAt": 42}
        out = remote_control.pointer_payload("env_01NEW", 77, "now", previous)
        self.assertEqual(out["sessionId"], "")
        self.assertNotIn("activeSessionIds", out)

    def test_payload_without_a_previous_file(self):
        out = remote_control.pointer_payload("env_01NEW", 5, "now")
        self.assertEqual(out["sessionId"], "")
        self.assertNotIn("activeSessionIds", out)

    def test_environment_id_takes_the_last_one_named(self):
        log = "registered env_01AAA\nlater\nregistered env_01BBB\ntail\n"
        self.assertEqual(remote_control.environment_id(log), "env_01BBB")
        self.assertIsNone(remote_control.environment_id("nothing here"))

    def test_pointer_is_current_only_while_young(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge-pointer.json"
            wanted = remote_control.pointer_payload("env_01A", 1, "now")
            path.write_text(json.dumps(wanted))
            self.assertTrue(remote_control.pointer_is_current(wanted, wanted, path))
            self.assertFalse(remote_control.pointer_is_current({"environmentId": "env_01B"}, wanted, path))
            old = os.stat(path).st_mtime - remote_control.POINTER_TTL_SECONDS
            os.utime(path, (old, old))
            self.assertFalse(remote_control.pointer_is_current(wanted, wanted, path))

    def test_read_pointer_tolerates_junk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bridge-pointer.json"
            self.assertIsNone(remote_control.read_pointer(path))
            path.write_text("not json")
            self.assertIsNone(remote_control.read_pointer(path))
            path.write_text("[1]")
            self.assertIsNone(remote_control.read_pointer(path))


class RetryRunTests(unittest.TestCase):
    def test_trailing_run_is_measured(self):
        log = ("[01:30:00] Connected\n"
               "[01:40:00] Connection error, retrying in 2s (0s elapsed): fetch failed\n"
               "[01:47:30] Connection error, retrying in 2m (450s elapsed): fetch failed\n")
        self.assertEqual(remote_control.retry_run_seconds(log), 450)

    def test_a_later_line_resets_the_run(self):
        log = ("[01:40:00] Connection error, retrying in 2s\n"
               "[01:47:30] Connection error, retrying in 2m\n"
               "[01:48:00] Connected\n")
        self.assertEqual(remote_control.retry_run_seconds(log), 0)

    def test_a_run_crossing_midnight_does_not_go_negative(self):
        log = "[23:56:00] Connection error, retrying\n[00:04:00] Connection error, retrying\n"
        self.assertEqual(remote_control.retry_run_seconds(log), 480)

    def test_a_single_line_is_not_yet_a_run(self):
        self.assertEqual(remote_control.retry_run_seconds("[01:40:00] Connection error, retrying\n"), 0)


class HealPlistTests(unittest.TestCase):
    def test_interval_and_command(self):
        body = plistlib.loads(remote_control.render_heal("/bin/harness", "/u/dev", "/tmp/logs"))
        self.assertEqual(body["StartInterval"], 60)
        self.assertEqual(body["ProgramArguments"],
                         ["/bin/harness", "remote-control", "heal", "--once"])
        self.assertEqual(body["Label"], "com.agent-harness.remote-control-heal")

    def test_label_is_outside_the_folder_agent_glob(self):
        # `installed()` globs the folder labels; the heal agent must not look stale to `install`.
        self.assertFalse(remote_control.HEAL_LABEL.startswith(remote_control.LABEL_PREFIX))


class HealRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.folder = self.home / "repos" / "app"
        (self.folder / ".claude" / "worktrees").mkdir(parents=True)
        # `settings()` resolves every folder, and /var is a symlink to /private/var on macOS.
        self.folder = self.folder.resolve()
        (self.home / ".config" / "agent-harness").mkdir(parents=True)
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"remote_control": {"folders": [str(self.folder)]}}))
        (self.home / ".claude").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude" / "projects").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude.json").write_text(json.dumps(
            {"projects": {str(self.folder): {"hasTrustDialogAccepted": True}}}))
        self.log_dir = self.home / ".local" / "state" / "agent-harness" / "remote-control"
        self.log_dir.mkdir(parents=True)
        self.label = remote_control.label(self.folder)
        (self.log_dir / (self.label + ".log")).write_text("bridge up on env_01LIVE\n")
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_STATE_HOME": ""}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_heal(self, **flags):
        fields = dict(action="heal", once=True, dry_run=False, preserve_worktrees=False)
        fields.update(flags)
        args = argparse.Namespace(**fields)
        lines = []
        with mock.patch.object(harness, "say", lines.append), \
             mock.patch.object(harness, "home", lambda: self.home), \
             mock.patch.object(harness, "remote_control_log_dir", lambda: self.log_dir), \
             mock.patch.object(harness, "claude_state_file", lambda: self.home / ".claude.json"), \
             mock.patch.object(harness, "host_pid", lambda name: 4242), \
             mock.patch.object(harness, "proc_start", lambda pid: "Tue Sep 22 13:36:19 2026"), \
             mock.patch.object(harness.platform, "system", lambda: "Darwin"):
            code = harness.cmd_remote_control_heal(args)
        return code, "\n".join(lines)

    def pointer(self):
        return remote_control.pointer_path(self.home / ".claude" / "projects", self.folder)

    def test_writes_the_live_environment(self):
        code, _ = self.run_heal()
        self.assertEqual(code, 0)
        written = json.loads(self.pointer().read_text())
        self.assertEqual(written["environmentId"], "env_01LIVE")
        self.assertEqual(written["pid"], 4242)
        self.assertEqual(written["source"], "standalone")
        self.assertIn("pointer", (self.log_dir / "heal.log").read_text())

    def test_dry_run_writes_nothing(self):
        code, out = self.run_heal(dry_run=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.pointer().exists())
        self.assertFalse((self.log_dir / "heal.log").exists())
        self.assertIn("would", out)

    def test_a_stopped_host_is_skipped_without_writing(self):
        args = argparse.Namespace(action="heal", once=True, dry_run=False, preserve_worktrees=False)
        with mock.patch.object(harness, "home", lambda: self.home), \
             mock.patch.object(harness, "remote_control_log_dir", lambda: self.log_dir), \
             mock.patch.object(harness, "claude_state_file", lambda: self.home / ".claude.json"), \
             mock.patch.object(harness, "host_pid", lambda name: None), \
             mock.patch.object(harness, "say", lambda line: None), \
             mock.patch.object(harness.platform, "system", lambda: "Darwin"):
            self.assertEqual(harness.cmd_remote_control_heal(args), 0)
        self.assertFalse(self.pointer().exists())

    def test_give_up_risk_is_logged_but_not_acted_on(self):
        (self.log_dir / (self.label + ".log")).write_text(
            "bridge up on env_01LIVE\n"
            "[01:39:00] Connection error, retrying in 2s (0s elapsed)\n"
            "[01:47:00] Connection error, retrying in 2m (480s elapsed)\n")
        code, out = self.run_heal()
        self.assertEqual(code, 0)
        self.assertIn("give-up at 10m", out)

    def test_wip_guard_commits_a_dirty_session_worktree(self):
        tree = self.folder / ".claude" / "worktrees" / "bridge-cse_01A"
        tree.mkdir()
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", "init", "-q", str(tree)], check=True)
        subprocess.run(["git", "-C", str(tree), "commit", "-q", "--allow-empty", "-m", "init"],
                       check=True, env=env)
        (tree / "work.txt").write_text("unpushed")
        self.assertEqual([p.name for p in harness.dirty_bridge_worktrees(self.folder)],
                         ["bridge-cse_01A"])
        with mock.patch.dict(os.environ, env):
            self.assertTrue(harness.wip_commit(tree, dry=False))
        self.assertEqual(harness.dirty_bridge_worktrees(self.folder), [])
        subject = subprocess.run(["git", "-C", str(tree), "log", "-1", "--format=%s"],
                                 capture_output=True, text=True).stdout.strip()
        self.assertEqual(subject, "chore(wip): preserve work before reconnect")


if __name__ == "__main__":
    unittest.main()
