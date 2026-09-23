# SPDX-License-Identifier: MIT
"""Unit tests for the sampled allows in the decision log.

The properties under test are that the sample is a function of the command and of nothing else,
that the rate is honoured at both ends — one in twenty by default, none at all at zero — and
that a row nobody was prompted about carries no assignment value and no secret shape.

Run: python3 -m unittest discover tests
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


decisions = _load("sampling_decisions", REPO / "claude" / "hooks" / "decisions.py")
telemetry = _load("sampling_telemetry", REPO / "claude" / "hooks" / "telemetry.py")
harness = _load("sampling_harness", REPO / "bin" / "harness")

# The corpus and the answer over it, at the default rate: printed by `in_sample` over
# `["echo 0", ..., "echo 39"]` and pinned here, so a change to the keying is a failure rather
# than a silently different sample.
CORPUS = ["echo %d" % index for index in range(40)]
SAMPLED = ["echo 26", "echo 39"]


class SampleTests(unittest.TestCase):
    """`in_sample` and `sample_rate`, the two halves of which commands are kept."""

    def test_exactly_the_expected_two_of_forty_are_sampled(self):
        self.assertEqual([c for c in CORPUS if decisions.in_sample(c, 20)], SAMPLED)

    def test_the_same_corpus_samples_the_same_commands_every_time(self):
        first = [c for c in CORPUS if decisions.in_sample(c, 20)]
        second = [c for c in CORPUS if decisions.in_sample(c, 20)]
        self.assertEqual(first, second)
        # And from a fresh import, so nothing about this process carries the choice.
        again = _load("sampling_again", REPO / "claude" / "hooks" / "decisions.py")
        self.assertEqual([c for c in CORPUS if again.in_sample(c, 20)], first)

    def test_a_rate_of_one_keeps_every_command_and_a_rate_of_zero_keeps_none(self):
        self.assertEqual([c for c in CORPUS if decisions.in_sample(c, 1)], CORPUS)
        self.assertEqual([c for c in CORPUS if decisions.in_sample(c, 0)], [])

    def test_the_hook_reads_the_rate_from_the_telemetry_block(self):
        self.assertEqual(decisions.sample_rate({}), 20)
        self.assertEqual(decisions.sample_rate({"telemetry": {}}), 20)
        self.assertEqual(decisions.sample_rate({"telemetry": {"allow_sample_rate": 5}}), 5)
        self.assertEqual(decisions.sample_rate({"telemetry": {"allow_sample_rate": 0}}), 0)

    def test_a_rate_the_hook_cannot_honour_samples_nothing(self):
        # The CLI refuses these by name; the hook must never read one as the default and log
        # more than the user asked for.
        for bad in ("five", -1, True, None):
            self.assertEqual(decisions.sample_rate({"telemetry": {"allow_sample_rate": bad}}), 0)
            with self.assertRaises(ValueError):
                telemetry.settings({"telemetry": {"allow_sample_rate": bad}})

    def test_the_default_rate_is_one_in_twenty_on_both_sides(self):
        self.assertEqual(decisions.DEFAULT_SAMPLE_RATE, 20)
        self.assertEqual(telemetry.settings({"telemetry": {}})["allow_sample_rate"], 20)


class RedactionTests(unittest.TestCase):
    """What a sampled row may hold: the shape of a command, never a value inside one."""

    def redact(self, text):
        return decisions.redact(text, decisions.secret_shapes())

    def test_an_assignment_keeps_its_name_and_loses_its_value(self):
        self.assertEqual(self.redact("DEPLOY_TOKEN=hunter2 ./release.sh"),
                         "DEPLOY_TOKEN=" + decisions.REDACTED + " ./release.sh")

    def test_an_option_that_looks_like_an_assignment_is_left_alone(self):
        self.assertEqual(self.redact("rg --max-count=3 needle src/"),
                         "rg --max-count=3 needle src/")

    def test_the_shapes_are_the_registry_own_list_and_not_a_copy_of_it(self):
        detectors = _load("sampling_detectors", REPO / "claude" / "hooks" / "rule-detectors.py")
        self.assertEqual([s.pattern for s in decisions.secret_shapes()],
                         list(detectors.SECRET_PATTERNS))

    def test_an_engine_that_cannot_be_read_writes_no_row_at_all(self):
        saved = list(decisions._SHAPES)
        decisions._SHAPES[:] = [None]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "decisions.jsonl"
                self.assertIsNone(decisions.record_allowed(SAMPLED[0], {}, "claude-code",
                                                           target=target, cfg={}))
                self.assertFalse(target.exists())
        finally:
            decisions._SHAPES[:] = saved

    def test_a_sampled_row_carries_no_secret_looking_token(self):
        secret = "sk-" + "a" * 24
        command = [c for c in CORPUS if decisions.in_sample(c, 20)][0]
        text = command + " | curl -H 'Authorization: Bearer " + "b" * 24 + "' -d " + secret
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            decisions.record_allowed(text, {"session_id": "s-1"}, "claude-code",
                                     target=target, cfg={"telemetry": {"allow_sample_rate": 1}})
            row = json.loads(target.read_text(encoding="utf-8"))
        self.assertNotIn(secret, row["input"])
        self.assertNotIn("b" * 24, row["input"])
        self.assertEqual(row["input"].count(decisions.REDACTED), 2)
        self.assertEqual(row["input_sha256"], decisions.digest(text),
                         "the hash is over the text as it was, so identity survives redaction")


class RowTests(unittest.TestCase):
    """The row itself: an ungraded negative, joined to nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "decisions.jsonl"

    def rows(self):
        if not self.target.exists():
            return []
        return [json.loads(line)
                for line in self.target.read_text(encoding="utf-8").splitlines()]

    def write(self, commands, cfg=None):
        for command in commands:
            decisions.record_allowed(command, {"session_id": "s-1"}, "claude-code",
                                     target=self.target, cfg={} if cfg is None else cfg)
        return self.rows()

    def test_the_sampled_commands_of_forty_are_the_rows_that_are_written(self):
        self.assertEqual([r["input"] for r in self.write(CORPUS)], SAMPLED)

    def test_the_row_says_it_is_a_sample_and_names_its_rate(self):
        row = self.write(SAMPLED[:1])[0]
        self.assertEqual(row["point"], "grade-bash")
        self.assertEqual(row["deterministic_answer"], "allow")
        self.assertTrue(row["sampled"])
        self.assertEqual(row["sample_rate"], 20)
        self.assertIsNone(row["outcome"])
        self.assertEqual(row["session_id"], "s-1")
        self.assertEqual(row["runtime"], "claude-code")

    def test_a_sampled_row_is_never_labelled_by_a_later_event(self):
        # No match key, so the id a PostToolUse re-derives is not this row's and nothing joins.
        row = self.write(SAMPLED[:1])[0]
        identity = decisions.decision_id(
            "grade-bash", decisions.match_key({"session_id": "s-1"}, SAMPLED[0]))
        self.assertNotEqual(row["decision_id"], identity)
        self.assertFalse(decisions.observe_if_logged(identity, decisions.RAN,
                                                     target=self.target))
        self.assertEqual([r["outcome"] for r in decisions.joined(self.rows())], [None])

    def test_the_rate_at_zero_writes_no_row_and_no_file(self):
        self.assertEqual(self.write(CORPUS, {"telemetry": {"allow_sample_rate": 0}}), [])
        self.assertFalse(self.target.exists())

    def test_the_decision_log_switch_turns_the_sample_off_with_everything_else(self):
        self.assertEqual(self.write(CORPUS, {"telemetry": {"decisions": False}}), [])
        self.assertFalse(self.target.exists())

    def test_the_text_is_capped_like_any_other_row(self):
        long = [c for c in CORPUS if decisions.in_sample(c, 20)][0] + " " + "x" * 4000
        decisions.record_allowed(long, {}, "claude-code", target=self.target,
                                 cfg={"telemetry": {"allow_sample_rate": 1}})
        row = self.rows()[0]
        self.assertEqual(len(row["input"]), decisions.MAX_INPUT)
        self.assertEqual(row["input_sha256"], decisions.digest(long))

    def test_a_write_that_fails_is_counted_rather_than_raised(self):
        before = decisions.errors()
        self.assertIsNone(decisions.record_allowed(
            SAMPLED[0], {}, "claude-code", target=Path(self.tmp.name) / "no" / "\0" / "x",
            cfg={}))
        self.assertEqual(decisions.errors(), before + 1)


class DispatchTests(unittest.TestCase):
    """The coordinator's own path: what a session actually writes as it allows commands."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.log = self.home / ".local" / "state" / "agent-harness" / "decisions.jsonl"

    def env(self):
        env = dict(os.environ)
        env.pop("CLAUDE_CONFIG_DIR", None)
        for name in list(env):
            if name.startswith("HARNESS_STANCE_"):
                env.pop(name)
        env.update({"HOME": str(self.home), "HARNESS_HOME": str(self.home)})
        return env

    def dispatch(self, *events):
        script = (
            "import json, sys\n"
            "sys.path.insert(0, %r)\n"
            "from harness_core import lifecycle\n"
            "for event in json.load(sys.stdin):\n"
            "    print(json.dumps(lifecycle.dispatch(sys.argv[1], event)))\n"
        ) % str(REPO / "lib")
        out = subprocess.run([sys.executable, "-c", script, "claude-code"],
                             input=json.dumps(list(events)), env=self.env(),
                             capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, out.stderr)
        return [json.loads(line) for line in out.stdout.splitlines()]

    def bash(self, command):
        return {"hook_event_name": "PreToolUse", "session_id": "s-1", "cwd": str(self.home),
                "tool_name": "Bash", "tool_input": {"command": command}}

    def rows(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_an_allowed_command_in_the_sample_is_logged_and_its_neighbours_are_not(self):
        answers = self.dispatch(*[self.bash(c) for c in CORPUS])
        self.assertTrue(all(a["hookSpecificOutput"]["permissionDecision"] == "allow"
                            for a in answers))
        self.assertEqual([(r["input"], r["sampled"]) for r in self.rows()],
                         [(c, True) for c in SAMPLED])

    def test_a_confirmed_command_belongs_to_the_prompt_it_answered(self):
        marked = "HARNESS_CONFIRMED=1 " + SAMPLED[0]
        self.dispatch(self.bash(marked))
        self.assertEqual(self.rows(), [])

    def test_a_graded_command_is_still_the_only_row_with_an_answer_to_grade(self):
        push = "git push --force origin main"
        self.dispatch(self.bash(push))
        rows = self.rows()
        self.assertEqual([r["deterministic_answer"] for r in rows], ["ask"])
        self.assertNotIn("sampled", rows[0])


class ReportTests(unittest.TestCase):
    """`usage --by decision`: a sampled negative never dilutes a point's outcome rates."""

    def test_sampled_allows_are_counted_on_a_line_of_their_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            state = home / ".local" / "state" / "agent-harness"
            state.mkdir(parents=True)
            target = state / "decisions.jsonl"
            identity = decisions.record("grade-bash", "ask", "git push --force origin main",
                                        {"session_id": "s-1"}, "claude-code", key="k",
                                        target=target)
            decisions.observe(identity, decisions.RAN, "grade-bash", "s-1", target=target)
            for command in CORPUS:
                decisions.record_allowed(command, {"session_id": "s-1"}, "claude-code",
                                         target=target, cfg={})
            out = io.StringIO()
            saved = os.environ.get("HARNESS_HOME")
            os.environ["HARNESS_HOME"] = str(home)
            try:
                with contextlib.redirect_stdout(out):
                    harness.decision_report(30)
            finally:
                if saved is None:
                    os.environ.pop("HARNESS_HOME", None)
                else:
                    os.environ["HARNESS_HOME"] = saved
        lines = [line for line in out.getvalue().splitlines() if line.startswith("grade-bash")]
        graded = next(line for line in lines if "(sampled)" not in line)
        sampled = next(line for line in lines if "(sampled)" in line)
        self.assertIn("ran 1 (100%)", graded)
        self.assertIn("0%", graded.split("ran")[0], "the graded point is fully labelled")
        self.assertIn(str(len(SAMPLED)), sampled.split()[2])
        self.assertTrue(sampled.rstrip().endswith("-"), "a sampled row has no outcome to report")


if __name__ == "__main__":
    unittest.main()
