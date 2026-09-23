"""The permission-controls driver, run against recorded turns instead of a live client.

No test here launches a client. Three real results recorded on 2026-09-22 stand in for the turns
(`fixtures/permission-controls/README.md` says how each was produced), and the case is driven
over them in a home that serves them back: a refused write classifies as a block, a turn the
model declined classifies as a decline and never as a block, and the completed bypass turn is
reported as neither. The posture refusal and the mode each posture syncs come from `bin/harness`
itself rather than from a copy of its rules in this file.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO, harness
from test_native_acceptance import MODULE

FIXTURES = REPO / "tests" / "fixtures" / "permission-controls"


def turn(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


DENIED = turn("manual-denied")
DECLINED = turn("bypass-declined")
COMPLETED = turn("bypass-completed")


class FakeHome:
    """A disposable home's surface, serving recorded turns and the real posture rules.

    `harness.posture` decides whether a sync is refused and `harness.POSTURES` says which mode it
    writes, so the case is tested against the behaviour it will meet, not against a paraphrase.
    """

    def __init__(self, directory, turns):
        self.root = Path(directory)
        self.project = self.root / "project"
        self.project.mkdir()
        self.turns = list(turns)
        self.prompts = []
        self.mode = ""
        self.data = {"stances": {}, "permissions": "inherit"}

    def seed(self, stances=None, roots=(), **config):
        self.data["stances"] = dict(stances or {})
        self.data.update(config)

    def config(self):
        return json.loads(json.dumps(self.data))

    def write_config(self, data):
        self.data = data

    def harness(self, *args, **kwargs):
        expected = kwargs.pop("expected", 0)
        try:
            value = harness.posture(self.data)
        except SystemExit as error:
            code, output = 1, str(error)
        else:
            code, output = 0, "synced"
            if value != "inherit":
                self.mode = harness.POSTURES[value]["claude"]
        if expected is not None and code != expected:
            raise AssertionError("harness %s returned %s, expected %s: %s"
                                 % (" ".join(args), code, expected, output))
        return output

    def permission_mode(self):
        return self.mode

    def session(self, prompt, tools=(), **kwargs):
        self.prompts.append(prompt)
        data, writes = self.turns.pop(0)
        if writes:
            (self.project / MODULE.SENTINEL).write_text("")
        return data


def run_case(turns):
    """Run the driver over recorded turns; returns its observation or raises what it raises."""
    with tempfile.TemporaryDirectory() as directory:
        home = FakeHome(directory, turns)
        return MODULE.case_permission_controls(home)


HAPPY = [(DENIED, False), (COMPLETED, True), (DENIED, False)]


def stub_init(self, *args, **kwargs):
    """A Home that builds no disposable directory, so a probe runs with no client behind it."""
    self.root = Path("/somewhere/tmp/harness-native-permission-controls")
    self.launched = 0


class OutcomeTests(unittest.TestCase):
    """The three outcomes the case must tell apart, each read from a recorded turn."""

    def test_a_recorded_denial_is_a_block(self):
        self.assertEqual(MODULE.turn_outcome(False, DENIED), MODULE.BLOCKED)
        self.assertTrue(MODULE.permission_denials(DENIED))

    def test_a_recorded_decline_is_a_decline_and_never_a_block(self):
        self.assertEqual(MODULE.turn_outcome(False, DECLINED), MODULE.DECLINED)
        result, reason = MODULE.bypass_verdict(False, DECLINED, MODULE.BYPASS_MODE)
        self.assertEqual(result, "unverified")
        self.assertIn("declined", reason)

    def test_a_completed_bypass_turn_is_neither(self):
        self.assertEqual(MODULE.turn_outcome(True, COMPLETED), MODULE.COMPLETED)
        self.assertEqual(MODULE.bypass_verdict(True, COMPLETED, MODULE.BYPASS_MODE), ("passed", ""))


class PostureTests(unittest.TestCase):
    def test_the_modes_the_case_expects_are_the_ones_the_harness_writes(self):
        claude = dict((name, row["claude"]) for name, row in harness.POSTURES.items())
        self.assertEqual(claude["manual"], MODULE.MANUAL_MODE)
        self.assertEqual(claude["auto"], MODULE.AUTO_MODE)
        self.assertEqual(claude["bypass"], MODULE.BYPASS_MODE)

    def test_the_case_walks_every_posture_and_reports_what_each_one_did(self):
        observation = run_case(HAPPY)
        for needle in ("permissions=manual", MODULE.MANUAL_MODE, MODULE.ACK_KEY,
                       MODULE.BYPASS_MODE, "permissions=auto", MODULE.AUTO_MODE,
                       "1 permission denial(s)"):
            self.assertIn(needle, observation, msg=needle)

    def test_every_turn_asks_for_the_same_one_command_write(self):
        with tempfile.TemporaryDirectory() as directory:
            home = FakeHome(directory, HAPPY)
            MODULE.case_permission_controls(home)
        self.assertEqual(home.prompts, [MODULE.SENTINEL_PROMPT] * 3)
        self.assertEqual(home.data["stances"]["autonomy"], "execute")


class VerdictTests(unittest.TestCase):
    """What the case makes of each recorded turn, end to end through `probe`."""

    def probe(self, turns):
        def case(home):
            return run_case(turns)

        with patch.dict(MODULE.CASES, {"permission-controls": (case, "recorded")}), \
                patch.object(MODULE.Home, "__init__", stub_init), \
                patch.object(MODULE.Home, "discard", lambda self: None):
            return MODULE.probe("claude-code-cli-macos", "permission-controls", "cheapest", False)

    def test_the_recorded_postures_pass(self):
        self.assertEqual(self.probe(HAPPY)["result"], "passed")

    def test_a_declined_bypass_turn_is_unverified_and_never_failed(self):
        outcome = self.probe([(DENIED, False), (DECLINED, False), (DENIED, False)])
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("declined", outcome["observation"])

    def test_a_blocked_bypass_turn_is_the_failure(self):
        outcome = self.probe([(DENIED, False), (DENIED, False), (DENIED, False)])
        self.assertEqual(outcome["result"], "failed")
        self.assertIn("blocked", outcome["observation"])

    def test_a_manual_posture_that_wrote_the_file_is_the_failure(self):
        outcome = self.probe([(COMPLETED, True), (COMPLETED, True), (DENIED, False)])
        self.assertEqual(outcome["result"], "failed")
        self.assertIn(MODULE.SENTINEL, outcome["observation"])

    def test_a_manual_posture_the_model_declined_observed_no_restriction(self):
        outcome = self.probe([(DECLINED, False), (COMPLETED, True), (DENIED, False)])
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("declined", outcome["observation"])

    def test_an_auto_posture_that_completed_is_reported_rather_than_judged(self):
        observation = run_case([(DENIED, False), (COMPLETED, True), (COMPLETED, True)])
        self.assertIn("the write was completed", observation)


class RegistrationTests(unittest.TestCase):
    def test_the_case_is_registered_and_the_plan_no_longer_calls_it_unautomated(self):
        self.assertIn("permission-controls", MODULE.CASES)
        printed = MODULE.plan("claude-code-cli-macos", MODULE.catalog()["required_cases"],
                              "cheapest")
        line = [row for row in printed.splitlines() if "permission-controls" in row][0]
        self.assertNotIn(MODULE.NOT_AUTOMATED, line)

    def test_the_procedure_names_what_the_driver_reads(self):
        procedure = (REPO / "docs" / "compatibility.md").read_text()
        step = procedure[procedure.index("\n3. "):procedure.index("\n4. ")]
        step = " ".join(step.split())  # wrapping is not stable; the observables are.
        for needle in ("permission mode", "acknowledged", "declined", "denial"):
            self.assertIn(needle, step, msg=needle)

    def test_the_release_procedure_carries_the_comparison_the_first_round_owes(self):
        releasing = " ".join((REPO / "docs" / "releasing.md").read_text().split())
        self.assertIn("permission-controls", releasing)
        self.assertIn("hand", releasing)


if __name__ == "__main__":
    unittest.main()
