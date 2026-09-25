"""A resumed qualification round skips the cases its durable log already settled.

FR-52: "a resumed round skips completed cases". No client runs: the runner is a stub that
records which cases it was asked to run, and the progress log is the one `record()` appends to.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import CLIENT, MODULE

CASES = ["cost-posture", "installation", "migration-uninstall"]


def verdict(result):
    def runner(client, name, model, keep, confirmed=False):
        return {"case": name, "result": result, "observation": "%s was %s." % (name, result),
                "seconds": 0.1, "sessions": 1}
    return runner


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.progress = Path(self.tmp.name) / "round.partial.jsonl"
        self.ran = []

    def counting(self, runner):
        def run(client, name, model, keep, confirmed=False):
            self.ran.append(name)
            return runner(client, name, model, keep, confirmed)
        return run

    def run_round(self, runner, names=None, commit="a" * 40):
        self.ran = []
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else commit), \
                patch.dict(MODULE.CASES, {name: (None, "stub") for name in CASES}, clear=True), \
                redirect_stderr(io.StringIO()) as err:
            data = MODULE.record(CLIENT, names or CASES, "cheapest", False,
                                 runner=self.counting(runner), progress=self.progress)
        return data, err.getvalue()

    def lines(self):
        items = [json.loads(line) for line in self.progress.read_text().splitlines()]
        return [item for item in items if "case" in item]

    def test_a_resumed_round_does_not_rerun_a_case_that_passed_at_the_same_commit(self):
        self.run_round(verdict("passed"), names=[CASES[0]])
        data, err = self.run_round(verdict("passed"))
        self.assertEqual(self.ran, CASES[1:])
        self.assertEqual(data["cases"], {name: "passed" for name in CASES})
        self.assertEqual([item["case"] for item in self.lines()], CASES)
        self.assertIn("resume: %s already passed" % CASES[0], err)

    def test_a_pass_at_another_commit_skips_nothing(self):
        self.run_round(verdict("passed"), commit="b" * 40)
        data, err = self.run_round(verdict("passed"), commit="c" * 40)
        self.assertEqual(self.ran, CASES)
        self.assertEqual(err, "")
        self.assertEqual(data["source_commit"], "c" * 40)

    def test_a_failed_case_keeps_its_verdict_and_is_not_rerun(self):
        self.run_round(verdict("failed"), names=[CASES[0]])
        data, err = self.run_round(verdict("passed"))
        self.assertEqual(self.ran, CASES[1:])
        self.assertEqual(data["cases"][CASES[0]], "failed")
        self.assertIn(CASES[0] + ": " + CASES[0] + " was failed.", data["observations"])
        self.assertIn("resume: %s already failed" % CASES[0], err)

    def test_an_unverified_case_runs_again_and_its_new_result_wins(self):
        self.run_round(verdict("unverified"), names=[CASES[0]])
        data, _ = self.run_round(verdict("passed"))
        self.assertEqual(self.ran, CASES)
        self.assertEqual(data["cases"], {name: "passed" for name in CASES})

    def test_the_latest_line_for_a_case_decides_whether_it_is_settled(self):
        head = {"case": CASES[0], "source_commit": "a" * 40}
        items = [dict(head, result="passed"), dict(head, result="unverified"),
                 {"case": CASES[1], "result": "unverified"}, {"case": CASES[1], "result": "failed"}]
        self.assertEqual(MODULE.settled(items), {CASES[1]: "failed"})


if __name__ == "__main__":
    unittest.main()
