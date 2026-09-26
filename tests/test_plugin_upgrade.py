# SPDX-License-Identifier: MIT
"""`citizen upgrade`, and the doctor and sync lines that point a pre-rename plugin install at it.

Claude Code keeps an install on `agent-harness@agent-harness` after the rename, and ignores a
second `marketplace add` while the old marketplace is registered, so the order of the four
`claude plugin` steps is the behaviour under test. No test runs the real `claude` CLI.
"""
import io
import json
import os
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

from isolation import isolate_home
from test_harness import harness

OLD = "agent-harness@agent-harness"
NEW = "model-citizen@model-citizen"


class PluginUpgradeCase(unittest.TestCase):
    def setUp(self):
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        isolate_home(self.home, quiet=False)

    def write(self, relative, data):
        path = self.home / ".claude" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def old_install(self, source=None, scope="user", project=None):
        self.write("settings.json", {"enabledPlugins": {OLD: True}})
        record = {"scope": scope, "version": "0.13.1"}
        if project:
            record["projectPath"] = project
        self.write("plugins/installed_plugins.json", {"version": 2, "plugins": {OLD: [record]}})
        self.write("plugins/known_marketplaces.json", {"agent-harness": {
            "source": source or {"source": "github", "repo": "JakeSelby/agent-harness"}}})

    def upgrade(self, dry_run=False, which="/usr/local/bin/claude", statuses=()):
        calls = []
        replies = list(statuses)

        def fake(argv, cwd=None):
            calls.append((list(argv), cwd))
            return replies.pop(0) if replies else 0

        out = io.StringIO()
        with unittest.mock.patch.object(harness, "_run_claude", side_effect=fake), \
                unittest.mock.patch.object(harness.shutil, "which", return_value=which), \
                redirect_stdout(out):
            rc = harness.cmd_upgrade(harness.argparse.Namespace(dry_run=dry_run))
        return rc, out.getvalue(), calls


class UpgradeCommandTests(PluginUpgradeCase):
    def test_a_dry_run_prints_the_four_steps_in_order_from_the_recorded_source_and_scope(self):
        self.old_install(source={"source": "git", "url": "https://git.example/me/fork.git"},
                         scope="local", project="/work/app")
        rc, out, calls = self.upgrade(dry_run=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(calls, [])
        expected = [
            "cd /work/app && claude plugin uninstall %s --scope local" % OLD,
            "claude plugin marketplace remove agent-harness",
            "claude plugin marketplace add https://git.example/me/fork.git",
            "cd /work/app && claude plugin install %s --scope local" % NEW,
        ]
        positions = [out.index(line) for line in expected]
        self.assertEqual(positions, sorted(positions), out)

    def test_a_run_calls_the_steps_in_order_with_a_github_source(self):
        self.old_install()
        rc, out, calls = self.upgrade()
        self.assertEqual(rc, 0, out)
        self.assertEqual(calls, [
            (["claude", "plugin", "uninstall", OLD, "--scope", "user"], None),
            (["claude", "plugin", "marketplace", "remove", "agent-harness"], None),
            (["claude", "plugin", "marketplace", "add", "JakeSelby/agent-harness"], None),
            (["claude", "plugin", "install", NEW, "--scope", "user"], None),
        ])
        self.assertIn("done", out)

    def test_a_directory_source_is_added_by_its_path(self):
        self.old_install(source={"source": "directory", "path": "/src/agent-harness"})
        _, _, calls = self.upgrade()
        self.assertIn((["claude", "plugin", "marketplace", "add", "/src/agent-harness"], None), calls)

    def test_nothing_old_found_says_so_and_exits_zero(self):
        self.write("settings.json", {"enabledPlugins": {NEW: True}})
        rc, out, calls = self.upgrade()
        self.assertEqual(rc, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(calls, [])

    def test_a_failed_step_stops_the_run_and_prints_the_rest(self):
        self.old_install()
        rc, out, calls = self.upgrade(statuses=[0, 1])
        self.assertEqual(rc, 1)
        self.assertEqual(len(calls), 2)
        rest = out.split("did not run", 1)[1]
        self.assertIn("claude plugin marketplace add JakeSelby/agent-harness", rest)
        self.assertIn("claude plugin install %s --scope user" % NEW, rest)
        self.assertNotIn("marketplace remove", rest)
        self.assertNotIn("done", out)

    def test_without_the_claude_cli_it_prints_the_session_steps_and_exits_one(self):
        self.old_install()
        rc, out, calls = self.upgrade(which=None)
        self.assertEqual(rc, 1)
        self.assertEqual(calls, [])
        expected = ["/plugin uninstall " + OLD, "/plugin marketplace remove agent-harness",
                    "/plugin marketplace add JakeSelby/agent-harness", "/plugin install " + NEW]
        positions = [out.index(line) for line in expected]
        self.assertEqual(positions, sorted(positions), out)

    def test_with_both_ids_enabled_only_the_old_one_is_removed(self):
        self.old_install()
        self.write("settings.json", {"enabledPlugins": {OLD: True, NEW: True}})
        self.write("plugins/known_marketplaces.json", {
            "agent-harness": {"source": {"source": "github", "repo": "JakeSelby/agent-harness"}},
            "model-citizen": {"source": {"source": "github", "repo": "JakeSelby/model-citizen"}}})
        rc, _, calls = self.upgrade()
        self.assertEqual(rc, 0)
        self.assertEqual([argv for argv, _ in calls], [
            ["claude", "plugin", "uninstall", OLD, "--scope", "user"],
            ["claude", "plugin", "marketplace", "remove", "agent-harness"]])

    def test_an_unrecorded_marketplace_source_runs_nothing(self):
        self.old_install()
        self.write("plugins/known_marketplaces.json", {})
        rc, out, calls = self.upgrade()
        self.assertEqual(rc, 1)
        self.assertEqual(calls, [])
        self.assertIn("no recorded source", out)

    def test_the_command_is_registered_and_documented(self):
        self.assertIn("    citizen upgrade [--dry-run]", harness.__doc__)


class DoctorAndSyncHintTests(PluginUpgradeCase):
    def sync_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = harness.cmd_sync(harness.argparse.Namespace(
                dry_run=True, adopt=False, adopt_codex=False, print_only=True))
        self.assertEqual(rc, 0, out.getvalue())
        return out.getvalue()

    def test_doctor_names_the_pre_rename_id_and_the_upgrade_command(self):
        self.write("settings.json", {"enabledPlugins": {OLD: True}})
        line = harness._plugin_install_line()
        self.assertIn(OLD + " is the pre-rename plugin ID", line)
        self.assertIn("fails to load once its marketplace updates", line)
        self.assertIn("`citizen upgrade`", line)

    def test_doctor_points_the_both_enabled_warning_at_the_upgrade_command(self):
        self.write("settings.json", {"enabledPlugins": {OLD: True, NEW: True}})
        line = harness._plugin_install_line()
        self.assertIn("loads twice", line)
        self.assertIn("`citizen upgrade`", line)
        self.assertEqual(line.count("citizen upgrade"), 1)

    def test_doctor_says_nothing_about_upgrading_the_new_id(self):
        self.write("settings.json", {"enabledPlugins": {NEW: True}})
        self.assertNotIn("citizen upgrade", harness._plugin_install_line())

    def test_sync_prints_one_notice_when_the_old_id_is_enabled(self):
        self.write("settings.json", {"enabledPlugins": {OLD: True}})
        out = self.sync_output()
        notices = [line for line in out.splitlines() if "citizen upgrade" in line]
        self.assertEqual(len(notices), 1, out)
        self.assertIn(OLD, notices[0])

    def test_sync_is_silent_about_the_plugin_otherwise(self):
        self.write("settings.json", {"enabledPlugins": {NEW: True}})
        self.assertNotIn("citizen upgrade", self.sync_output())


if __name__ == "__main__":
    unittest.main()
