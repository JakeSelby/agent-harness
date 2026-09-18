# SPDX-License-Identifier: MIT
"""Unit tests for audience fit: how much the agent explains, and the preset for non-code work."""
import argparse
import contextlib
import io
import importlib.machinery
import importlib.util
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


def personal(expertise=None):
    identity = {"name": "A Name", "role": "Does a thing"}
    if expertise is not None:
        identity["expertise"] = expertise
    return harness.render_personal({"identity": identity}, None)


class GuidanceTests(unittest.TestCase):
    def test_the_expert_line_is_no_longer_hardcoded_in_the_template(self):
        template = (REPO / "claude" / "CLAUDE.personal.template.md").read_text()
        self.assertIn("{guidance}", template)
        self.assertNotIn("skip basics and fundamentals", template)

    def test_expert_gets_the_line_it_always_had(self):
        self.assertIn("skip basics and fundamentals", personal("expert"))

    def test_beginner_gets_the_opposite_and_never_the_expert_line(self):
        text = personal("beginner")
        self.assertIn("Define a term the first time you use it", text)
        self.assertNotIn("skip basics and fundamentals", text)

    def test_a_config_with_no_expertise_field_keeps_the_behaviour_it_had(self):
        self.assertIn("skip basics and fundamentals", personal(None))

    def test_an_unrecognised_value_falls_back_rather_than_raising(self):
        self.assertIn("skip basics and fundamentals", personal("wizard"))

    def test_the_example_config_carries_the_field(self):
        self.assertEqual(EXAMPLE["identity"]["expertise"], "expert")

    def test_the_marker_still_holds_hand_written_lines(self):
        first = personal("expert") + "my own note\n"
        again = harness.render_personal(
            {"identity": {"name": "A Name", "expertise": "beginner"}}, first)
        self.assertIn("my own note", again)
        self.assertIn("Define a term the first time you use it", again)


class ExpertiseValidationTests(unittest.TestCase):
    def test_a_known_value_passes(self):
        self.assertEqual(harness.coerce_config_value("identity.expertise", "beginner"), "beginner")

    def test_an_unknown_value_is_refused_with_the_options(self):
        with self.assertRaises(SystemExit) as cm:
            harness.coerce_config_value("identity.expertise", "wizard")
        self.assertIn("beginner", str(cm.exception))


class PresetTests(unittest.TestCase):
    def test_software_is_the_example_defaults_unchanged(self):
        self.assertEqual(harness.STANCE_PRESETS["software"], {})

    def test_general_turns_off_the_software_ceremony(self):
        general = harness.STANCE_PRESETS["general"]
        for stance, variant in (("commits", "off"), ("testing", "off"), ("licensing", "off"),
                                ("build-vs-buy", "off"), ("plan-ceremony", "light")):
            self.assertEqual(general[stance], variant, msg=stance)

    def test_every_preset_resolves_to_real_variants(self):
        for name, overlay in harness.STANCE_PRESETS.items():
            stances = dict(EXAMPLE["stances"], **overlay)
            with self.subTest(preset=name):
                harness.resolve_stances({"stances": stances})

    def test_the_general_preset_leaves_delegation_and_cost_alone(self):
        """They are about how work is spread and what it costs, not about shipping software."""
        general = harness.STANCE_PRESETS["general"]
        self.assertNotIn("delegation", general)
        self.assertNotIn("cost", general)


class InitPresetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp.name
        os.environ["HARNESS_QUIET"] = "1"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def _run(self, expertise, preset):
        answers = iter(["A Name", "", "Does a thing", "", "UTC", expertise, preset]
                       + [""] * len(harness.STANCE_NAMES))
        with unittest.mock.patch("builtins.input", lambda _p: next(answers)), \
             unittest.mock.patch.object(harness.sys.stdin, "isatty", return_value=True), \
             unittest.mock.patch.object(harness, "_detect_github", return_value=""):
            with loud():
                harness.cmd_init(argparse.Namespace(force=False))
        return json.loads(harness.config_path().read_text())

    def test_the_general_preset_becomes_the_stance_defaults(self):
        cfg = self._run("beginner", "general")
        self.assertEqual(cfg["identity"]["expertise"], "beginner")
        self.assertEqual(cfg["stances"]["testing"], "off")
        self.assertEqual(cfg["stances"]["commits"], "off")
        self.assertEqual(cfg["stances"]["plan-ceremony"], "light")
        harness.resolve_stances(cfg)

    def test_the_software_preset_keeps_the_shipped_defaults(self):
        cfg = self._run("expert", "software")
        self.assertEqual(cfg["stances"], EXAMPLE["stances"])
        self.assertEqual(cfg["identity"]["expertise"], "expert")

    def test_a_general_config_renders_the_beginner_guidance(self):
        cfg = self._run("beginner", "general")
        self.assertIn("Define a term the first time you use it",
                      harness.render_personal(cfg, None))


class RuleScopeTests(unittest.TestCase):
    def test_the_code_only_rules_say_so_in_their_heading(self):
        for name, scope in (("verification.md", "in a code repository"),
                            ("secrets.md", "wherever files are tracked"),
                            ("conciseness.md", "in code and docs")):
            head = (REPO / "claude" / "rules" / name).read_text().splitlines()[0]
            self.assertTrue(head.startswith("# "), name)
            self.assertIn(scope, head, msg=name)

    def test_the_always_loaded_preamble_says_code_rules_do_not_apply_off_code(self):
        text = (REPO / "claude" / "CLAUDE.md").read_text()
        self.assertIn("is about code work; elsewhere it does not apply", text)

    def test_the_scoping_did_not_break_the_detector_registry(self):
        self.assertEqual(harness.check_detectors(REPO), [])


if __name__ == "__main__":
    unittest.main()
