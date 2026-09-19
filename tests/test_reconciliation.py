"""Regression coverage for owned configuration and clean Codex installation."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import harness, CFG, REPO, TempHome
from harness_core import reconcile


class ReconciliationTests(unittest.TestCase):
    def test_nested_toml_keys_and_comments_survive(self):
        text = '# keep\nmodel = "chosen"\n[nested]\napproval_policy = "nested" # untouched\n'
        result = harness.update_codex_config(text, dict(CFG, permissions="manual"))
        doc = reconcile.tomlkit.parse(result)
        self.assertEqual(doc["approval_policy"], "on-request")
        self.assertEqual(doc["nested"]["approval_policy"], "nested")
        self.assertIn('# untouched', result)
        self.assertEqual(result, harness.update_codex_config(result, dict(CFG, permissions="manual")))

    def test_toml_rollback_preserves_new_unowned_keys_and_user_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); config = root / "config.toml"
            config.write_text('model = "mine"\napproval_policy = "never"\n')
            store = reconcile.Store(root / "state")
            store.toml(config, {"approval_policy": "on-request", "sandbox_mode": "read-only"})
            stamp = config.stat().st_mtime_ns
            store.toml(config, {"approval_policy": "on-request", "sandbox_mode": "read-only"})
            self.assertEqual(config.stat().st_mtime_ns, stamp)
            config.write_text(config.read_text() + 'theme = "dark"\n')
            store.uninstall()
            doc = reconcile.tomlkit.parse(config.read_text())
            self.assertEqual(doc["approval_policy"], "never")
            self.assertEqual(doc["theme"], "dark")
            self.assertNotIn("sandbox_mode", doc)
            store.toml(config, {"approval_policy": "on-request"})
            config.write_text(config.read_text().replace('"on-request"', '"never"'))
            store.uninstall()
            self.assertTrue(store.conflicts)
            self.assertIn('approval_policy = "never"', config.read_text())

    def test_generated_file_adoption_and_modified_file_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root / "AGENTS.md"; target.write_text("personal")
            store = reconcile.Store(root / "state")
            store.generated(target, "generated")
            self.assertTrue(store.conflicts)
            self.assertEqual(target.read_text(), "personal")
            store.conflicts.clear()
            store.generated(target, "generated", adopt=True)
            self.assertEqual(store.drift(), [])
            target.write_text("edited")
            self.assertTrue(store.drift())
            store.generated(target, "next")
            store.uninstall()
            self.assertEqual(target.read_text(), "edited")
            self.assertIn(str(target), store.data["files"])
            target.write_text("generated")
            store.uninstall()
            self.assertEqual(target.read_text(), "personal")

    def test_json_restores_owned_fields_and_preserves_unrelated_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root / "settings.json"
            target.write_text(json.dumps({"model": "mine", "permissions": {"defaultMode": "default"}}))
            store = reconcile.Store(root / "state")
            store.json(target, {"permissions": {"defaultMode": "auto"}}, [["permissions", "defaultMode"]])
            current = json.loads(target.read_text());current["theme"] = "dark"
            target.write_text(json.dumps(current))
            store.uninstall()
            self.assertEqual(json.loads(target.read_text()), {"model": "mine", "theme": "dark", "permissions": {"defaultMode": "default"}})

    def test_interrupted_write_recovers_from_durable_intent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root / "AGENTS.md"
            store = reconcile.Store(root / "state")
            real = reconcile.atomic_text
            def failing(path, text):
                if path == target:
                    raise OSError("interrupted")
                real(path, text)
            with patch.object(reconcile, "atomic_text", side_effect=failing):
                with self.assertRaises(OSError):
                    store.generated(target, "generated")
            restored = reconcile.Store(root / "state")
            restored.generated(target, "generated")
            self.assertEqual(restored.conflicts, [])
            self.assertEqual(target.read_text(), "generated")

    def test_lock_refuses_a_second_writer(self):
        with tempfile.TemporaryDirectory() as temp:
            with reconcile.lock(Path(temp)):
                with self.assertRaisesRegex(ValueError, "another harness"):
                    with reconcile.lock(Path(temp)):
                        self.fail("second writer entered")

    def test_vendor_hash_and_notice_match_reviewed_artifact(self):
        component = json.loads((REPO / "third-party.json").read_text())["components"][0]
        self.assertEqual(hashlib.sha256((REPO / component["file"]).read_bytes()).hexdigest(), component["sha256"])
        self.assertIn("Permission is hereby granted", (REPO / component["notice"]).read_text())


class NativeInstallTests(TempHome):
    def sync(self, **options):
        return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=False,
                                adopt_codex=options.get("adopt_codex", False), print_only=False))

    def test_session_override_does_not_change_global_projections(self):
        with patch.dict(harness.os.environ, {"HARNESS_STANCE_DELEGATION": "off"}):
            self.assertEqual(self.sync(), 0)
            linked = self.home / ".claude" / "rules" / "harness-stances" / "delegation.md"
            self.assertEqual(linked.resolve().stem, CFG["stances"]["delegation"])
            self.assertIn("stance delegation: " + CFG["stances"]["delegation"],
                          (self.home / ".codex" / "AGENTS.md").read_text())

    def test_malformed_claude_json_is_rejected_before_links(self):
        folder = self.home / ".claude"
        folder.mkdir()
        (folder / "settings.json").write_text("{broken")
        with self.assertRaises(SystemExit):
            self.sync()
        self.assertFalse((folder / "CLAUDE.md").exists())

    def test_interrupted_adoption_keeps_recoverable_intent(self):
        source = self.home / "existing.md"
        source.write_text("personal")
        manifest = harness.InstallManifest({"version": 1})
        with patch.object(harness.shutil, "move", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                harness._adopt(source, manifest, False)
        persisted = json.loads(harness.manifest_path().read_text())
        self.assertEqual(persisted["adopted"][0]["path"], str(source))
        self.assertEqual(source.read_text(), "personal")

    def test_uninstall_preserves_redirected_link_and_its_recovery_record(self):
        self.assertEqual(self.sync(), 0)
        link = self.home / ".claude" / "rules" / "harness"
        link.unlink()
        link.symlink_to(self.home / "user-target")
        self.assertEqual(harness.cmd_uninstall(harness.argparse.Namespace()), 2)
        self.assertTrue(link.is_symlink())
        self.assertTrue(harness.manifest_path().exists())

    def test_codex_only_bootstraps_all_shared_artifacts_and_identity(self):
        harness.config_path().parent.mkdir(parents=True)
        harness.config_path().write_text(json.dumps({"claude": {"manage": False}, "identity": {"name": "Ada"}}))
        self.assertEqual(self.sync(), 0)
        self.assertFalse((self.home / ".claude").exists())
        self.assertIn("Ada", (self.home / ".codex/AGENTS.md").read_text())
        self.assertEqual(len(list((self.home / ".codex/agents").glob("*.toml"))), 7)
        self.assertEqual(len(list((self.home / ".agents/skills").glob("*/SKILL.md"))), 19)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(harness._diff_lines(), [])
        (self.home / ".codex/AGENTS.md").write_text("user change")
        self.assertTrue(any("generated file" in line for line in harness._diff_lines()))
        self.assertEqual(self.sync(), 2)
        self.assertEqual((self.home / ".codex/AGENTS.md").read_text(), "user change")

    def test_adopted_guidance_survives_resync_and_uninstall(self):
        agents = self.home / ".codex/AGENTS.md";agents.parent.mkdir()
        agents.write_text("Personal guidance")
        self.assertEqual(self.sync(adopt_codex=True), 0)
        self.assertIn("Personal guidance", agents.read_text())
        self.assertEqual(self.sync(), 0)
        self.assertIn("Personal guidance", agents.read_text())
        self.assertEqual(harness.cmd_uninstall(harness.argparse.Namespace()), 0)
        self.assertEqual(agents.read_text(), "Personal guidance")

    def test_dry_run_writes_nothing(self):
        self.assertEqual(harness.cmd_sync(harness.argparse.Namespace(dry_run=True, adopt=False,
                                                                  adopt_codex=False, print_only=False)), 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_custom_runtime_homes_are_respected(self):
        with patch.dict(harness.os.environ, {"CLAUDE_CONFIG_DIR": str(self.home / "cc"),
                                            "CODEX_HOME": str(self.home / "cx")}):
            self.assertEqual(self.sync(), 0)
            self.assertTrue((self.home / "cc/settings.json").exists())
            self.assertTrue((self.home / "cx/config.toml").exists())

    def test_custom_stance_can_be_selected_through_the_public_cli(self):
        source = self.home / "personal-primitives"
        (source / "stances/feedback").mkdir(parents=True)
        (source / "stances/feedback/direct.md").write_text("Be direct.\n")
        self.assertEqual(harness.config_set("primitive_roots", json.dumps([str(source)])), 0)
        self.assertEqual(harness.config_set("stances.feedback", "direct"), 0)
        self.assertEqual(self.sync(), 0)
        self.assertIn("Be direct.", (self.home / ".codex/AGENTS.md").read_text())
        self.assertEqual((self.home / ".claude/rules/harness-stances/feedback.md").read_text(), "Be direct.\n")

    def test_invalid_native_config_fails_before_installing_other_runtime(self):
        config = self.home / ".codex/config.toml"
        config.parent.mkdir();config.write_text("broken = [\n")
        with self.assertRaises(SystemExit):
            self.sync()
        self.assertFalse((self.home / ".claude").exists())
