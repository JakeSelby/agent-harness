# SPDX-License-Identifier: MIT
"""Unit tests for the output style the `voice` stance projects into Claude settings.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from harness_core import reconcile  # noqa: E402  the journal these tests read ownership from

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
VOICE = REPO / "primitives" / "stances" / "voice"
# What each shipped variant must produce; `None` is "install no style at all".
EXPECTED = {"scannable": "Scannable", "answer-card": None, "off": None}
USER_STYLE = "My Own Style"


def cfg_with(voice):
    cfg = json.loads((REPO / "config.example.json").read_text())
    cfg["stances"]["voice"] = voice
    return cfg


class VariantsTests(unittest.TestCase):
    def test_every_shipped_variant_is_covered_here(self):
        self.assertEqual(sorted(p.stem for p in VOICE.glob("*.md")), sorted(EXPECTED))

    def test_each_variant_produces_its_own_style_and_off_produces_none(self):
        for variant, style in EXPECTED.items():
            with self.subTest(variant=variant):
                merged = harness.merge_claude_settings({}, TEMPLATE, cfg_with(variant))
                self.assertEqual(merged.get("outputStyle"), style)
                if style is None:
                    self.assertNotIn("outputStyle", merged)

    def test_the_style_name_is_read_from_the_style_file(self):
        styles = harness.harness_output_styles()
        self.assertEqual(styles["scannable"], "Scannable")
        for stem, name in styles.items():
            with self.subTest(style=stem):
                text = (REPO / "claude" / "output-styles" / (stem + ".md")).read_text()
                self.assertIn("name: " + name, text)

    def test_the_template_no_longer_hard_codes_a_style(self):
        self.assertNotIn("outputStyle", TEMPLATE)


class PreservationTests(unittest.TestCase):
    def test_a_user_chosen_style_survives_a_merge_wherever_voice_installs_none(self):
        for variant in [v for v, style in EXPECTED.items() if style is None]:
            with self.subTest(variant=variant):
                merged = harness.merge_claude_settings(
                    {"outputStyle": USER_STYLE}, TEMPLATE, cfg_with(variant))
                self.assertEqual(merged["outputStyle"], USER_STYLE)

    def test_switching_away_from_scannable_removes_the_style_the_harness_installed(self):
        live = harness.merge_claude_settings({}, TEMPLATE, cfg_with("scannable"))
        merged = harness.merge_claude_settings(live, TEMPLATE, cfg_with("off"), installed="Scannable")
        self.assertNotIn("outputStyle", merged)

    def test_a_style_the_user_chose_first_survives_even_when_we_ship_that_name(self):
        """Ownership is what the journal recorded, not what the style is called."""
        live = {"outputStyle": "Scannable"}
        for variant in [v for v, style in EXPECTED.items() if style is None]:
            with self.subTest(variant=variant):
                merged = harness.merge_claude_settings(live, TEMPLATE, cfg_with(variant), installed=None)
                self.assertEqual(merged["outputStyle"], "Scannable")
        self.assertEqual(harness.strip_claude_settings(live, TEMPLATE, None)["outputStyle"], "Scannable")

    def test_uninstall_strips_our_style_and_keeps_the_user_s(self):
        ours = harness.merge_claude_settings({"model": "m"}, TEMPLATE, cfg_with("scannable"))
        self.assertNotIn("outputStyle", harness.strip_claude_settings(ours, TEMPLATE, "Scannable"))
        theirs = {"model": "m", "outputStyle": USER_STYLE}
        self.assertEqual(harness.strip_claude_settings(theirs, TEMPLATE, None)["outputStyle"], USER_STYLE)

    def test_a_user_chosen_style_is_not_in_the_projection_that_reports_drift(self):
        proj = harness.claude_projection({"outputStyle": USER_STYLE}, TEMPLATE, installed=None)
        self.assertIsNone(proj["keys"]["outputStyle"])
        ours = harness.merge_claude_settings({}, TEMPLATE, cfg_with("scannable"))
        self.assertEqual(
            harness.claude_projection(ours, TEMPLATE, installed="Scannable")["keys"]["outputStyle"],
            "Scannable")


class RuntimeAgreementTests(unittest.TestCase):
    """Whatever a variant means, it means the same on both runtimes."""

    def test_codex_appends_its_presentation_exactly_where_claude_installs_a_style(self):
        marker = str(REPO / "primitives" / "presentation" / "scannable.md")
        for variant in EXPECTED:
            with self.subTest(variant=variant):
                cfg = cfg_with(variant)
                stances = harness.resolve_stances(cfg)
                codex_has = marker in harness.render_codex_agents(stances, None)
                claude_has = harness.voice_output_style(cfg) is not None
                self.assertEqual(codex_has, claude_has)


class SyncTests(unittest.TestCase):
    """End to end through `harness sync`, in a throwaway home."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old = dict(os.environ)
        os.environ["HOME"] = str(self.home)
        for key in list(os.environ):
            if key.startswith("HARNESS_"):
                del os.environ[key]
        os.environ["HARNESS_QUIET"] = "1"
        self.settings = self.home / ".claude" / "settings.json"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def select(self, variant):
        """A sync projects the user's configuration; a session's `HARNESS_STANCE_*` is ignored."""
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"stances": {"voice": variant}}))

    def sync(self):
        rc = harness.cmd_sync(harness.argparse.Namespace(
            dry_run=False, adopt=True, adopt_codex=False, print_only=False))
        self.assertEqual(rc, 0)
        return json.loads(self.settings.read_text())

    def test_each_variant_syncs_its_own_style(self):
        for variant, style in EXPECTED.items():
            with self.subTest(variant=variant):
                self.select(variant)
                settings = self.sync()
                self.assertEqual(settings.get("outputStyle"), style)

    def test_a_pre_existing_user_style_survives_a_sync_at_voice_off(self):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"outputStyle": USER_STYLE, "model": "m"}))
        self.select("off")
        settings = self.sync()
        self.assertEqual(settings["outputStyle"], USER_STYLE)
        self.assertEqual(settings["model"], "m")
        self.assertEqual(self.sync()["outputStyle"], USER_STYLE)
        self.assertEqual([l for l in harness._diff_lines() if "outputStyle" in l], [])

    def test_a_style_the_user_chose_before_installing_survives_a_sync_and_an_uninstall(self):
        """Our own style name, chosen by the user first: the journal has never recorded it."""
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"outputStyle": "Scannable"}))
        self.select("off")
        self.assertEqual(self.sync()["outputStyle"], "Scannable")
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertEqual(json.loads(self.settings.read_text())["outputStyle"], "Scannable")

    def test_an_unowned_style_is_not_recorded_as_owned_and_a_hand_edit_is_not_drift(self):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"outputStyle": USER_STYLE}))
        self.select("off")
        self.sync()
        store = reconcile.Store(self.home / ".local/state/agent-harness", dry=True)
        keys = store.data["files"].get(str(self.settings), {}).get("keys", {})
        self.assertNotIn(harness.OUTPUT_STYLE_PATH, keys)
        settings = json.loads(self.settings.read_text())
        settings["outputStyle"] = "Something Else"
        self.settings.write_text(json.dumps(settings))
        drift = harness._diff_lines() + reconcile.Store(self.home / ".local/state/agent-harness",
                                                        dry=True).drift()
        self.assertEqual([l for l in drift if "outputStyle" in l], [])
        self.assertEqual(self.sync()["outputStyle"], "Something Else")

    def test_uninstall_restores_what_was_there_before_our_style(self):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"outputStyle": USER_STYLE}))
        self.select("scannable")
        self.assertEqual(self.sync()["outputStyle"], "Scannable")
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertEqual(json.loads(self.settings.read_text())["outputStyle"], USER_STYLE)

    def test_uninstall_leaves_no_style_where_there_was_none(self):
        self.select("scannable")
        self.assertEqual(self.sync()["outputStyle"], "Scannable")
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertNotIn("outputStyle", json.loads(self.settings.read_text()))

    def test_drift_on_our_own_style_names_the_live_value(self):
        self.select("scannable")
        self.sync()
        settings = json.loads(self.settings.read_text())
        settings["outputStyle"] = "Hand Edited"
        self.settings.write_text(json.dumps(settings))
        lines = [l for l in harness._diff_lines() if "outputStyle" in l]
        self.assertTrue(lines, "a hand-edited harness style is drift")
        self.assertIn("Hand Edited", lines[0])
        self.assertNotIn("None", lines[0])


if __name__ == "__main__":
    unittest.main()
