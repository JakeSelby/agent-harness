# SPDX-License-Identifier: MIT
"""Unit tests for bin/harness. Run: python3 -m unittest discover tests

Fixture strings that must trip the lint are assembled at run time, so this file itself
carries no identifier-shaped literal; the lint scans it like every other file.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
CFG = json.loads((REPO / "config.example.json").read_text())
NO_TERMS = ([], [])


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        for k in list(os.environ):
            if k.startswith("HARNESS_"):
                del os.environ[k]
        os.environ["HARNESS_QUIET"] = "1"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()


class SettingsMergeTests(unittest.TestCase):
    def test_merge_is_idempotent(self):
        once = harness.merge_claude_settings({}, TEMPLATE, CFG)
        twice = harness.merge_claude_settings(once, TEMPLATE, CFG)
        self.assertEqual(once, twice)

    def test_allow_rules_are_a_union_and_user_rules_survive(self):
        live = {"permissions": {"allow": ["Bash(my-tool *)", "Read(~/**)"]}}
        merged = harness.merge_claude_settings(live, TEMPLATE, CFG)
        allow = merged["permissions"]["allow"]
        self.assertIn("Bash(my-tool *)", allow)
        self.assertEqual(allow.count("Read(~/**)"), 1)
        for rule in TEMPLATE["permissions"]["allow"]:
            self.assertIn(rule, allow)

    def test_retired_template_rules_are_dropped_and_user_rules_kept(self):
        live = {"permissions": {"allow": ["Bash(awk *)", "Bash(my-tool *)"]}}
        applied = {"template": {"allow": ["Bash(awk *)", "Read(~/**)"]}}
        retired = harness.retired_allow_rules(applied, TEMPLATE)
        self.assertEqual(retired, ["Bash(awk *)"])
        merged = harness.merge_claude_settings(live, TEMPLATE, CFG, retired=retired)
        allow = merged["permissions"]["allow"]
        self.assertNotIn("Bash(awk *)", allow)
        self.assertIn("Bash(my-tool *)", allow)
        self.assertEqual(harness.retired_allow_rules({}, TEMPLATE), [])

    def test_never_touched_keys_survive(self):
        live = {"model": "some-model", "theme": "dark", "permissions": {"defaultMode": "bypassPermissions"}}
        merged = harness.merge_claude_settings(live, TEMPLATE, CFG)
        self.assertEqual(merged["model"], "some-model")
        self.assertEqual(merged["theme"], "dark")
        self.assertEqual(merged["permissions"]["defaultMode"], "bypassPermissions")  # inherit

    def test_posture_sets_default_mode(self):
        cfg = dict(CFG, permissions="manual")
        merged = harness.merge_claude_settings({}, TEMPLATE, cfg)
        self.assertEqual(merged["permissions"]["defaultMode"], "default")

    def test_bypass_requires_acknowledgement(self):
        with self.assertRaises(SystemExit):
            harness.posture(dict(CFG, permissions="bypass"))
        self.assertEqual(harness.posture(dict(CFG, permissions="bypass", permissions_bypass_acknowledged=True)), "bypass")

    def test_hook_entries_replace_by_id_and_legacy_basename(self):
        legacy = {"hooks": {"PostToolUse": [
            {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "python3 /somewhere/validate-plan-card.py"}]},
            {"matcher": "Write", "hooks": [{"type": "command", "command": "echo mine"}]},
        ]}}
        merged = harness.merge_claude_settings(legacy, TEMPLATE, CFG)
        post = merged["hooks"]["PostToolUse"]
        commands = [h["command"] for e in post for h in e["hooks"]]
        self.assertEqual(len([c for c in commands if "validate-plan-card" in c]), 1)
        self.assertIn("echo mine", commands)
        self.assertTrue(any("# harness:plan-card" in c for c in commands))

    def test_plan_card_hook_follows_stance(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["stances"]["plan-ceremony"] = "light"
        merged = harness.merge_claude_settings({}, TEMPLATE, cfg)
        commands = [h["command"] for entries in merged["hooks"].values() for e in entries for h in e["hooks"]]
        self.assertFalse(any("plan-card" in c for c in commands))
        self.assertTrue(any("readonly-bash" in c for c in commands))

    def test_strip_removes_only_harness_material(self):
        merged = harness.merge_claude_settings({"model": "m", "permissions": {"allow": ["Bash(mine)"]}}, TEMPLATE, CFG)
        stripped = harness.strip_claude_settings(merged, TEMPLATE)
        self.assertEqual(stripped["model"], "m")
        self.assertEqual(stripped["permissions"]["allow"], ["Bash(mine)"])
        self.assertNotIn("hooks", stripped)
        self.assertNotIn("outputStyle", stripped)


class ConfigTests(TempHome):
    def test_env_overrides_config(self):
        cfg = harness.load_config(env={"HARNESS_STANCE_TESTING": "off", "HARNESS_PERMISSIONS": "auto", "HARNESS_IDENTITY_NAME": "Ada"})
        self.assertEqual(cfg["stances"]["testing"], "off")
        self.assertEqual(cfg["permissions"], "auto")
        self.assertEqual(cfg["identity"]["name"], "Ada")

    def test_every_default_stance_resolves(self):
        stances = harness.resolve_stances(harness.load_config(env={}))
        self.assertEqual(set(stances), set(harness.STANCE_NAMES))
        for p in stances.values():
            self.assertTrue(p.exists())

    def test_unknown_variant_fails_loudly(self):
        with self.assertRaises(SystemExit):
            harness.resolve_stances(harness.load_config(env={"HARNESS_STANCE_TESTING": "nope"}))


class PersonalRenderTests(unittest.TestCase):
    def test_render_keeps_below_marker(self):
        cfg = {"identity": {"name": "Ada", "pronouns": "she/her", "role": "x", "github": "ada", "timezone": "UTC"}}
        first = harness.render_personal(cfg, None)
        self.assertIn("Ada", first)
        edited = first + "\n- I like tabs.\n"
        cfg["identity"]["name"] = "Grace"
        second = harness.render_personal(cfg, edited)
        self.assertIn("Grace", second)
        self.assertNotIn("Ada", second)
        self.assertIn("- I like tabs.", second)


class CodexTests(unittest.TestCase):
    def test_config_update_adds_owned_keys_before_tables(self):
        text = 'model = "x"\n\n[projects."/a"]\ntrust_level = "trusted"\n'
        cfg = dict(CFG, permissions="bypass", permissions_bypass_acknowledged=True)
        out = harness.update_codex_config(text, cfg)
        self.assertIn('project_doc_fallback_filenames = ["CLAUDE.md"]', out)
        self.assertLess(out.index("project_doc_fallback_filenames"), out.index("[projects"))
        self.assertIn('approval_policy = "never"', out)
        self.assertIn('model = "x"', out)
        self.assertEqual(out, harness.update_codex_config(out, cfg))

    def test_agents_render_has_banner_and_stances(self):
        stances = harness.resolve_stances(harness.load_config(env={}))
        text = harness.render_codex_agents(stances, "personal bit")
        self.assertTrue(text.startswith(harness.CODEX_BANNER))
        self.assertIn("<!-- stance testing: required -->", text)
        self.assertIn("personal bit", text)
        self.assertNotIn("@~/.claude/CLAUDE.personal.md", text)


class SyncTests(TempHome):
    def test_sync_links_and_manifest_round_trip(self):
        rc = harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=True, adopt_codex=False, print_only=False))
        self.assertEqual(rc, 0)
        cd = self.home / ".claude"
        self.assertTrue((cd / "rules" / "harness").is_symlink())
        self.assertTrue((cd / "rules" / "harness-stances" / "testing.md").is_symlink())
        self.assertTrue((cd / "skills" / "plan-authoring").is_symlink())
        self.assertTrue((cd / "CLAUDE.md").is_symlink())
        self.assertTrue((cd / "CLAUDE.personal.md").exists())
        settings = json.loads((cd / "settings.json").read_text())
        self.assertEqual(settings["outputStyle"], "Scannable")
        manifest = json.loads((self.home / ".local/state/agent-harness/manifest.json").read_text())
        self.assertEqual(manifest["repo"], str(REPO))
        self.assertGreater(len(manifest["links"]), 10)
        rc = harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=False, adopt_codex=False, print_only=False))
        self.assertEqual(rc, 0)
        self.assertEqual(harness._diff_lines(), [])
        settings["permissions"]["allow"].append("Bash(something-new *)")
        (cd / "settings.json").write_text(json.dumps(settings))
        self.assertTrue(any("live-only allow rule" in l for l in harness._diff_lines()))
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse((cd / "rules" / "harness").exists())
        self.assertFalse((cd / "CLAUDE.md").exists())

    def test_unmanaged_file_is_never_replaced_without_adopt(self):
        cd = self.home / ".claude"
        cd.mkdir()
        (cd / "CLAUDE.md").write_text("mine")
        rc = harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=False, adopt_codex=False, print_only=False))
        self.assertEqual(rc, 2)
        self.assertEqual((cd / "CLAUDE.md").read_text(), "mine")
        rc = harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=True, adopt_codex=False, print_only=False))
        self.assertEqual(rc, 0)
        self.assertTrue((cd / "CLAUDE.md").is_symlink())
        moved = list((self.home / ".local/state/agent-harness/pre-harness").rglob("CLAUDE.md"))
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].read_text(), "mine")


class LintTests(TempHome):
    def _fixture(self):
        root = Path(self.tmp.name) / "repo"
        (root / "claude").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / ".github").mkdir()
        (root / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026 Ada Lovelace\n")
        (root / ".github" / "CODEOWNERS").write_text("* @adalovelace\n")
        return root

    def test_shapes_are_caught_without_any_configured_terms(self):
        root = self._fixture()
        account = str(10 ** 11 + 4242)                     # a 12-digit number, built at run time
        email = "someone" + "@" + "example" + ".com"
        home = "/" + "Users" + "/someone/" + "secret.txt"
        key = "AKIA" + "Q" * 16
        zone = "Z" + "0" * 13 + "ABCDEFG"
        tenant = "dev-" + "a1b2c3d4e5f6g7h8" + ".us.auth0.com"
        (root / "claude" / "leak.md").write_text("\n".join([account, email, home, key, zone, tenant]) + "\n")
        hits = harness.lint_tree(root, NO_TERMS)
        labels = " ".join(hits)
        for want in ("12-digit account id", "email address", "home-directory path", "secret pattern", "hosted-zone id", "identity-provider tenant"):
            self.assertIn(want, labels, msg=want)

    def test_terms_file_and_maintainer_name_rules(self):
        root = self._fixture()
        (root / "claude" / "bad.md").write_text("Hand this to Ada; ship to Example Corp; see Widgetron docs.\n")
        (root / "docs" / "ok.md").write_text("Grew out of Widgetron.\n")
        (root / "README.md").write_text("Maintained by Ada Lovelace (@adalovelace).\n")
        terms = (["example corp"], ["widgetron"])
        hits = harness.lint_tree(root, terms)
        self.assertTrue(any("bad.md" in h and "maintainer name" in h for h in hits))
        self.assertTrue(any("bad.md" in h and "lint-terms" in h for h in hits))
        self.assertTrue(any("bad.md" in h and "project name" in h for h in hits))
        self.assertFalse(any("docs/ok.md" in h for h in hits))
        self.assertFalse(any("README.md" in h for h in hits))
        self.assertFalse(any("LICENSE" in h for h in hits))

    def test_repo_carries_no_identifier_shapes_anywhere(self):
        """The regression test for the first release: no file, not even the lint or these
        tests, may contain an identifier-shaped literal."""
        self.assertEqual(harness.lint_tree(REPO, NO_TERMS), [])

    def test_repo_is_clean_under_the_local_terms_file_if_present(self):
        os.environ["HOME"] = self._old_home or ""
        try:
            self.assertEqual(harness.lint_tree(REPO), [])
        finally:
            os.environ["HOME"] = str(self.home)


class ContextCapTests(TempHome):
    """The always-loaded set is CLAUDE.md + every rule + the longest variant of each stance."""

    def _tree(self, rule_lines, stance_variants):
        root = Path(self.tmp.name) / "tree"
        (root / "claude" / "rules").mkdir(parents=True)
        (root / "claude" / "CLAUDE.md").write_text("# Global instructions\n\nshort.\n")
        (root / "claude" / "rules" / "a.md").write_text("\n".join(["line"] * rule_lines) + "\n")
        d = root / "claude" / "stances" / "testing"
        d.mkdir(parents=True)
        for name, n in stance_variants.items():
            (d / f"{name}.md").write_text("\n".join(["line"] * n) + "\n")
        return root

    def test_repo_is_under_the_cap(self):
        total, groups = harness.always_loaded_lines(REPO)
        self.assertLessEqual(total, harness.ALWAYS_LOADED_CAP, msg=f"{total} lines: {groups}")
        self.assertEqual(harness.check_context_cap(REPO), [])

    def test_breakdown_covers_claude_md_rules_and_one_variant_per_stance(self):
        total, groups = harness.always_loaded_lines(REPO)
        names = [g[0] for g in groups]
        self.assertIn("claude/CLAUDE.md", names)
        self.assertTrue(any(n.startswith("claude/rules/") for n in names))
        dims = sorted(p.name for p in (REPO / "claude" / "stances").iterdir() if p.is_dir())
        for dim in dims:
            self.assertEqual(len([n for n in names if n.startswith(f"claude/stances/{dim}/")]), 1)
        self.assertEqual(total, sum(g[1] for g in groups))

    def test_the_longest_stance_variant_is_the_one_counted(self):
        root = self._tree(3, {"off": 2, "required": 9, "pragmatic": 5})
        total, groups = harness.always_loaded_lines(root)
        stance = [g for g in groups if g[0].startswith("claude/stances/testing/")][0]
        self.assertIn("required.md", stance[0])
        self.assertEqual(stance[1], 9)
        self.assertEqual(total, 3 + 3 + 9)  # CLAUDE.md, the rule, the worst variant

    def test_over_cap_tree_fails_and_the_breakdown_names_the_offender(self):
        root = self._tree(harness.ALWAYS_LOADED_CAP + 20, {"off": 2})
        hits = harness.check_context_cap(root)
        self.assertTrue(hits)
        self.assertIn(f"over the {harness.ALWAYS_LOADED_CAP}-line cap", hits[0])
        self.assertTrue(any("claude/rules/" in h for h in hits[1:]), msg=str(hits))
        biggest = hits[1]
        self.assertIn("claude/rules/", biggest)
        self.assertIn(str(harness.ALWAYS_LOADED_CAP + 20), biggest)

    def test_cap_is_reported_by_the_lint_command(self):
        root = self._tree(harness.ALWAYS_LOADED_CAP + 20, {"off": 2})
        rc = harness.cmd_lint(harness.argparse.Namespace(path=str(root), staged=False))
        self.assertEqual(rc, 1)
        self.assertEqual(harness.cmd_lint(harness.argparse.Namespace(path=str(REPO), staged=False)), 0)

    def test_a_tree_without_harness_content_is_not_flagged(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        self.assertEqual(harness.check_context_cap(empty), [])


class CliTests(unittest.TestCase):
    def test_version_and_help(self):
        out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "--version"], capture_output=True, text=True)
        self.assertIn("agent-harness", out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
