# SPDX-License-Identifier: MIT
"""Which class executes a qualification target, which class reads it, and what is refused.

Nothing here launches a client or resolves against a live provider: every resolution runs over a
fixture `adapters/<runtime>/bindings.json` written into a temporary root, so a table that maps
two classes onto one model, or leaves a class unmapped, can be tested without touching the
adapters this repository ships.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from test_native_acceptance import MODULE
from harness_core import qualification


def load_round():
    path = REPO / "scripts" / "qualification_round.py"
    spec = importlib.util.spec_from_file_location("qualification_round", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUND = load_round()

CLAUDE = "claude-code-cli-macos"
CODEX = "codex-cli-macos"
TARGETS = [CLAUDE, CODEX]


def root_with(tiers, runtime="claude-code"):
    """A checkout root carrying one adapter's class table and nothing else."""
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "adapters" / runtime).mkdir(parents=True)
    (root / "adapters" / runtime / "bindings.json").write_text(
        json.dumps({"schema_version": 2, "tiers": tiers, "roles": {}}))
    return temp, root


class ResolutionTests(unittest.TestCase):
    def resolve(self, tiers, execution="standard", assessment="strong"):
        temp, root = root_with(tiers)
        try:
            return qualification.resolve(root, "claude-code", execution, assessment)
        finally:
            temp.cleanup()

    def test_the_defaults_execute_cheap_and_assess_strong(self):
        routing = self.resolve({"strong": "big", "standard": "small"})
        self.assertEqual(routing, {"execution_class": "standard", "execution_model": "small",
                                   "assessment_class": "strong", "assessment_model": "big"})

    def test_an_assessment_class_below_the_floor_is_refused(self):
        with self.assertRaisesRegex(ValueError, "weaker than strong"):
            self.resolve({"strong": "big", "standard": "small"}, assessment="standard")
        with self.assertRaisesRegex(ValueError, "weaker than strong"):
            self.resolve({"strong": "big", "light": "tiny"}, execution="light",
                         assessment="light")

    def test_a_stronger_assessment_class_than_the_floor_is_allowed(self):
        routing = self.resolve({"frontier": "huge", "strong": "big", "standard": "small"},
                               assessment="frontier")
        self.assertEqual(routing["assessment_model"], "huge")

    def test_a_table_mapping_both_classes_to_one_model_is_refused(self):
        with self.assertRaisesRegex(ValueError, "only reader"):
            self.resolve({"strong": "big", "standard": "big"})

    def test_an_unmapped_cheap_class_resolving_upward_is_refused(self):
        # `native_model` never resolves downward, so an unmapped `standard` lands on the strong
        # model: the saving is not bought and the executor would be its own reader.
        with self.assertRaisesRegex(ValueError, "only reader"):
            self.resolve({"frontier": "huge", "strong": "big"})

    def test_executing_at_the_floor_is_allowed_and_buys_nothing(self):
        routing = self.resolve({"frontier": "huge", "strong": "big"}, execution="strong")
        self.assertEqual(routing["execution_model"], routing["assessment_model"])

    def test_an_unmapped_assessment_class_is_disclosed_and_not_guessed_at(self):
        routing = self.resolve({"standard": "small"})
        self.assertIsNone(routing["assessment_model"])
        self.assertEqual(routing["execution_model"], "small")
        self.assertTrue(any("inherits the session model" in note
                            for note in routing["notes"]))

    def test_an_unknown_class_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "execution class must be one of"):
            self.resolve({"strong": "big"}, execution="cheapest")

    def test_both_shipped_adapters_resolve_the_defaults_to_two_models(self):
        for runtime in ("claude-code", "codex"):
            with self.subTest(runtime=runtime):
                routing = qualification.resolve(REPO, runtime)
                self.assertNotEqual(routing["execution_model"], routing["assessment_model"])
                self.assertNotIn("notes", routing)


class ClassMapTests(unittest.TestCase):
    def test_no_argument_leaves_every_target_on_the_default(self):
        self.assertEqual(qualification.parse_class_map(None, TARGETS, "standard"),
                         {CLAUDE: "standard", CODEX: "standard"})

    def test_a_bare_class_moves_every_target(self):
        self.assertEqual(qualification.parse_class_map(["light"], TARGETS, "standard"),
                         {CLAUDE: "light", CODEX: "light"})

    def test_a_qualified_class_moves_only_the_target_it_names(self):
        self.assertEqual(qualification.parse_class_map([CODEX + "=light"], TARGETS, "standard"),
                         {CLAUDE: "standard", CODEX: "light"})

    def test_later_arguments_win(self):
        chosen = qualification.parse_class_map(["light", CODEX + "=standard"], TARGETS, "strong")
        self.assertEqual(chosen, {CLAUDE: "light", CODEX: "standard"})

    def test_an_unknown_target_or_class_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown qualification target"):
            qualification.parse_class_map(["codex-cli-solaris=light"], TARGETS, "standard")
        with self.assertRaisesRegex(ValueError, "worker class must be one of"):
            qualification.parse_class_map([CODEX + "=cheap"], TARGETS, "standard")


class RunnerTests(unittest.TestCase):
    """What the acceptance runner does with the routing, without running a case."""

    def test_the_plan_names_both_classes_and_their_models(self):
        text = MODULE.plan(CLAUDE, ["cost-posture"], "cheapest")
        self.assertIn("tiers: execution standard (", text)
        self.assertIn("assessment strong (", text)

    def test_a_refused_pair_stops_the_runner_before_any_case(self):
        with self.assertRaises(SystemExit):
            MODULE.routing(CLAUDE, "standard", "light")

    def test_the_record_header_carries_the_routing(self):
        self.assertIn("tier_routing", MODULE.HEADER_KEYS)
        routing = MODULE.routing(CODEX)
        self.assertEqual(routing["assessment_class"], "strong")
        self.assertEqual(routing["execution_class"], "standard")


class RoundTests(unittest.TestCase):
    """What the round driver hands each target, and what the round record says about it."""

    def test_each_target_gets_its_own_pair(self):
        chosen = ROUND.routing(TARGETS, [CODEX + "=light"], None)
        self.assertEqual(chosen[CODEX]["execution_class"], "light")
        self.assertEqual(chosen[CLAUDE]["execution_class"], "standard")
        self.assertEqual(chosen[CODEX]["assessment_class"], "strong")

    def test_a_refused_pair_stops_the_round_before_the_smoke_tier(self):
        with self.assertRaises(SystemExit):
            ROUND.routing(TARGETS, None, [CLAUDE + "=light"])

    def test_the_target_invocation_names_both_classes(self):
        argv = ROUND.target_argv("/clone", CLAUDE, "cheapest", "/tmp/out.json", False,
                                 {"execution_class": "light", "assessment_class": "strong"})
        self.assertEqual(argv[argv.index("--execution-class") + 1], "light")
        self.assertEqual(argv[argv.index("--assessment-class") + 1], "strong")

    def test_the_round_record_says_which_class_executed_and_which_assessed(self):
        with tempfile.TemporaryDirectory() as temp:
            round_dir = Path(temp)
            records = round_dir / "records"
            (round_dir / "provision.json").write_text(json.dumps(
                {"clone": str(round_dir / "clone"), "records": str(records),
                 "source_commit": "a" * 40}))

            def fake_run(argv, **kwargs):
                out = argv[argv.index("--out") + 1] if "--out" in argv else None
                if out:
                    Path(out).write_text(json.dumps({"cases": {"installation": "passed"},
                                                     "observations": ["it happened"]}))
                return type("Done", (), {"returncode": 0})()

            with patch.object(ROUND.subprocess, "run", side_effect=fake_run):
                result = ROUND.run_round(round_dir, [CLAUDE], "cheapest", True)
        self.assertEqual(result["tier_routing"][CLAUDE]["execution_class"], "standard")
        self.assertEqual(result["tier_routing"][CLAUDE]["assessment_class"], "strong")


if __name__ == "__main__":
    unittest.main()
