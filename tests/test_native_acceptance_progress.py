"""A killed qualification round keeps the cases it had already finished.

No client runs here either: the runner is driven with a stub probe that dies part-way, and what
is tested is the durable per-case log — that it holds one line per finished case, that a record
rebuilt from it carries exactly those cases, and that a second round unions with the first
without letting evidence from another commit in.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import CLIENT, MODULE

CASES = ["cost-posture", "installation", "migration-uninstall"]


def passing(client, name, model, keep):
    return {"case": name, "result": "passed", "observation": "A native session did " + name + ".",
            "seconds": 0.1, "sessions": 1}


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.progress = Path(self.tmp.name) / "round.partial.jsonl"

    def run_round(self, runner, names=None, commit="a" * 40):
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else commit), \
                patch.dict(MODULE.CASES, {name: (None, "stub") for name in CASES}, clear=True):
            return MODULE.record(CLIENT, names or CASES, "cheapest", False, runner=runner,
                                 progress=self.progress)

    def lines(self):
        return [json.loads(line) for line in self.progress.read_text().splitlines()]

    def killed_after(self, count):
        """A runner that dies on the case after `count` finished ones, as a kill would."""
        def runner(client, name, model, keep):
            if len(self.lines() if self.progress.exists() else []) >= count:
                raise KeyboardInterrupt("the round was killed")
            return passing(client, name, model, keep)
        return runner

    def test_a_round_killed_after_two_cases_leaves_two_durable_results(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_round(self.killed_after(2))
        lines = self.lines()
        self.assertEqual([item["case"] for item in lines], CASES[:2])
        self.assertEqual([item["result"] for item in lines], ["passed", "passed"])
        for item in lines:
            self.assertEqual(item["source_commit"], "a" * 40)
            self.assertEqual(item["client"], CLIENT)

    def test_a_record_rebuilt_from_a_killed_round_carries_only_finished_cases(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_round(self.killed_after(1))
        data = MODULE.build_record(MODULE.progress_lines(self.progress))
        self.assertEqual(sorted(data), ["cases", "client", "client_version", "harness_version",
                                        "kind", "observations", "platform", "runtime_version",
                                        "source_commit"])
        self.assertEqual(data["cases"], {CASES[0]: "passed"})
        self.assertEqual(data["observations"], ["A native session did " + CASES[0] + "."])

    def test_a_resumed_round_unions_its_cases_with_the_surviving_ones(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_round(self.killed_after(1))
        data = self.run_round(passing, names=CASES[1:])
        self.assertEqual(data["cases"], {name: "passed" for name in CASES})
        self.assertEqual(len(data["observations"]), len(CASES))
        self.assertEqual([item["case"] for item in self.lines()], CASES)

    def test_a_rerun_case_supersedes_its_earlier_result(self):
        def failing(client, name, model, keep):
            return {"case": name, "result": "failed", "observation": "the spawn was not routed",
                    "seconds": 0.1, "sessions": 1}

        self.run_round(failing, names=[CASES[0]])
        data = self.run_round(passing, names=[CASES[0]])
        self.assertEqual(data["cases"], {CASES[0]: "passed"})
        self.assertEqual(data["observations"], ["A native session did " + CASES[0] + "."])

    def test_lines_from_another_commit_or_a_torn_write_are_ignored(self):
        self.run_round(passing, names=[CASES[0]], commit="b" * 40)
        with self.progress.open("a") as handle:
            handle.write('{"case": "installation", "result": "pass')  # killed mid-write
        data = self.run_round(passing, names=[CASES[1]], commit="c" * 40)
        self.assertEqual(data["cases"], {CASES[1]: "passed"})
        self.assertEqual(data["source_commit"], "c" * 40)

    def test_the_default_log_sits_outside_the_checkout(self):
        path = MODULE.progress_path(CLIENT, None)
        self.assertFalse(path.is_relative_to(MODULE.ROOT))
        self.assertEqual(MODULE.progress_path(CLIENT, Path("/tmp/native.json")),
                         Path("/tmp/native.json.partial.jsonl"))

    def test_from_progress_rebuilds_a_record_without_running_a_case(self):
        self.run_round(passing, names=CASES[:1])
        out = Path(self.tmp.name) / "record.json"
        with patch.object(MODULE, "probe", side_effect=AssertionError("a case ran")), \
                patch.object(MODULE, "client_version",
                             side_effect=AssertionError("a client ran")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main(["--client", CLIENT, "--from-progress",
                                          "--progress", str(self.progress),
                                          "--out", str(out)]), 0)
        self.assertEqual(json.loads(out.read_text())["cases"], {CASES[0]: "passed"})

    def test_an_empty_log_builds_no_record(self):
        with self.assertRaisesRegex(SystemExit, "no finished acceptance case"):
            MODULE.build_record(MODULE.progress_lines(self.progress))


if __name__ == "__main__":
    unittest.main()
