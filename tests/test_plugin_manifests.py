# SPDX-License-Identifier: MIT
"""The two plugin manifests, the marketplace listing they describe, and its catalog surface.

A green run says a Claude Code user who adds this repository as a marketplace would be pointed
at real files. It is not native qualification: the marketplace surface is `unqualified` in
`compatibility/catalog.json` and stays there until an acceptance round records evidence.
"""
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test_harness import harness, REPO

PLUGIN = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
MARKETPLACE = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
SURFACE = "claude-code-plugin-marketplace"


def entry():
    return next(row for row in MARKETPLACE["plugins"] if row["name"] == PLUGIN["name"])


class MarketplaceManifestTests(unittest.TestCase):
    def test_the_listing_carries_the_fields_claude_code_requires(self):
        self.assertTrue(MARKETPLACE["name"])
        self.assertTrue(MARKETPLACE["owner"]["name"])
        self.assertEqual(len(MARKETPLACE["plugins"]), 1)
        self.assertTrue(entry()["description"])

    def test_the_entry_resolves_to_the_plugin_manifest_rather_than_copying_it(self):
        source = (REPO / entry()["source"]).resolve()
        self.assertTrue((source / ".claude-plugin" / "plugin.json").is_file())
        for key in ("skills", "agents", "commands", "outputStyles"):
            self.assertNotIn(key, entry(), msg=key)

    def test_every_path_the_plugin_manifest_names_exists(self):
        targets = [PLUGIN["skills"], PLUGIN["commands"], PLUGIN["outputStyles"], *PLUGIN["agents"]]
        for target in targets:
            self.assertTrue((REPO / target).exists(), msg=target)

    def test_the_plugin_ships_no_hooks_because_a_synced_home_already_registers_them(self):
        # Plugin hooks merge with user hooks rather than replacing them, so a machine running
        # both would fire every hook twice. See docs/runtime-installation.md.
        self.assertNotIn("hooks", PLUGIN)


class CatalogSurfaceTests(unittest.TestCase):
    def test_the_marketplace_install_is_its_own_unqualified_client_surface(self):
        data = json.loads((REPO / "compatibility" / "catalog.json").read_text())
        rows = [row for row in data["clients"] if row["id"] == SURFACE]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "unqualified")
        self.assertFalse(rows[0]["required_for_release"])
        self.assertEqual(rows[0]["evidence"], [])
        self.assertEqual(rows[0]["runtime"], "claude-code")

    def test_the_install_doc_names_what_the_marketplace_path_leaves_out(self):
        text = (REPO / "docs" / "runtime-installation.md").read_text()
        self.assertIn("## Install from the plugin marketplace", text)
        self.assertIn("/plugin marketplace add JakeSelby/agent-harness", text)
        self.assertIn("/plugin install %s@%s" % (PLUGIN["name"], MARKETPLACE["name"]), text)
        for missing in ("ownership journal", "Stance selection", "Codex projection", "hooks"):
            self.assertIn(missing.lower(), text.lower(), msg=missing)


class DoctorInstallPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.home = Path(self.tmp.name)

    def write(self, relative, data):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_an_untouched_home_reports_neither_path_and_names_both_commands(self):
        line = harness._plugin_install_line()
        self.assertIn("neither", line)
        self.assertIn("bin/harness install", line)
        self.assertIn("/plugin install agent-harness@agent-harness", line)

    def test_an_ownership_manifest_reports_the_synced_home(self):
        self.write(".local/state/agent-harness/manifest.json", {})
        self.assertIn("synced home", harness._plugin_install_line())

    def test_an_enabled_plugin_reports_the_marketplace_install(self):
        self.write(".claude/settings.json", {"enabledPlugins": {"agent-harness@agent-harness": True}})
        line = harness._plugin_install_line()
        self.assertIn("marketplace plugin agent-harness@agent-harness", line)
        self.assertNotIn("synced home", line)

    def test_both_paths_are_reported_rather_than_one_hiding_the_other(self):
        self.write(".local/state/agent-harness/manifest.json", {})
        self.write(".claude/settings.json", {"enabledPlugins": {"agent-harness@agent-harness": True}})
        line = harness._plugin_install_line()
        self.assertIn("marketplace plugin", line)
        self.assertIn("synced home", line)

    def test_a_registered_marketplace_with_no_install_says_so(self):
        self.write(".claude/plugins/known_marketplaces.json",
                   {"agent-harness": {"source": {"source": "github", "repo": "JakeSelby/agent-harness"}}})
        line = harness._plugin_install_line()
        self.assertIn("marketplace registered, plugin not installed", line)

    def test_another_projects_marketplace_is_not_mistaken_for_this_one(self):
        self.write(".claude/plugins/known_marketplaces.json",
                   {"official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"}}})
        self.assertNotIn("marketplace registered", harness._plugin_install_line())

    def test_a_disabled_plugin_is_not_counted_as_installed(self):
        self.write(".claude/settings.json", {"enabledPlugins": {"agent-harness@agent-harness": False}})
        self.assertIn("neither", harness._plugin_install_line())

    def test_the_cache_directory_alone_is_enough_to_report_the_marketplace_install(self):
        (self.home / ".claude" / "plugins" / "cache" / "agent-harness" / "agent-harness").mkdir(parents=True)
        self.assertIn("marketplace plugin agent-harness/agent-harness", harness._plugin_install_line())


if __name__ == "__main__":
    unittest.main()
