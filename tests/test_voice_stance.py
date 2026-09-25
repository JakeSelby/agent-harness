# SPDX-License-Identifier: MIT
"""Unit tests for the voice stance and what the voice-and-format rule keeps.

Run: python3 -m unittest discover tests
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

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

VOICE = REPO / "primitives" / "stances" / "voice"
RULE = REPO / "claude" / "rules" / "voice-and-format.md"
# The longest variant is what the always-loaded cap charges, so it is what the budget bounds.
LONGEST_VARIANT = 33


class TempHome(unittest.TestCase):
    """A home with no real config, so a machine's own stance selection cannot mask the defaults."""

    config = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp.name
        if self.config is not None:
            d = Path(self.tmp.name) / ".config" / "agent-harness"
            d.mkdir(parents=True)
            (d / "config.json").write_text(json.dumps(self.config))

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def scrubbed_env(self):
        env = without_harness_vars()
        env["HOME"] = self.tmp.name
        return env


class VoiceStanceTests(TempHome):
    def test_dimension_is_registered_with_four_variants(self):
        self.assertIn("voice", harness.STANCE_NAMES)
        self.assertEqual(sorted(p.stem for p in VOICE.glob("*.md")),
                         ["answer-card", "concise", "off", "scannable"])

    def test_default_is_scannable(self):
        cfg = harness.load_config(env={})
        self.assertEqual(cfg["stances"]["voice"], "scannable")
        self.assertEqual(harness.resolve_stances(cfg)["voice"], VOICE / "scannable.md")

    def test_env_override_selects_a_variant(self):
        cfg = harness.load_config(env={"HARNESS_STANCE_VOICE": "answer-card"})
        self.assertEqual(harness.resolve_stances(cfg)["voice"], VOICE / "answer-card.md")

    def test_unknown_variant_fails_loudly(self):
        with self.assertRaises(SystemExit):
            harness.resolve_stances(harness.load_config(env={"HARNESS_STANCE_VOICE": "terse"}))


class VoiceConfigFileTests(TempHome):
    config = {"stances": {"voice": "off"}}

    def test_config_get_resolves_the_dimension(self):
        out = subprocess.run(
            [sys.executable, str(REPO / "bin" / "harness"), "config", "get", "stances.voice"],
            capture_output=True, text=True, env=self.scrubbed_env(),
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "off", out.stderr)


class VoiceBudgetTests(unittest.TestCase):
    def test_every_variant_stays_within_what_the_budget_assumed(self):
        for path in sorted(VOICE.glob("*.md")):
            with self.subTest(variant=path.stem):
                self.assertLessEqual(len(path.read_text().splitlines()), LONGEST_VARIANT)

    def test_the_rule_keeps_only_what_no_variant_changes(self):
        text = RULE.read_text()
        self.assertLessEqual(len(text.splitlines()), 6)
        # The one instruction no variant can carry: a subagent inherits no voice.
        self.assertIn("subagent brief", text)
        self.assertNotIn("Scannable", text)

    def test_each_variant_names_the_shape_it_imposes(self):
        """Native acceptance reads "no tables" or "at most one table" from the resolved voice."""
        def flat(name):
            return " ".join((VOICE / name).read_text().split())
        self.assertIn("at most one table", flat("scannable.md"))
        self.assertIn("no tables", flat("answer-card.md"))
        self.assertIn("no tables", flat("concise.md"))
        self.assertIn("the Concise style wins", flat("concise.md"))
        self.assertIn("No imposed voice", flat("off.md"))
