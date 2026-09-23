"""The model a qualification target runs on is the model its records declare.

A round that was not given `--model` used to launch the runner without one, so the cases ran on
the runner's own default while the round and evidence records named the routed execution model.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import MODULE
from test_qualification_worker_class import CLAUDE, FAKE_ROUTING, ROUND, passing

UNMAPPED = dict(FAKE_ROUTING, execution_class="standard", execution_model=None)


def argv_model(argv):
    return argv[argv.index("--model") + 1] if "--model" in argv else None


def routed(model=None, client=CLAUDE):
    """The round's routing for one target on the shipped adapters, restated for `model`."""
    return ROUND.with_models(ROUND.routing([client], None, None), model)[client]


class RoundArgvTests(unittest.TestCase):
    def test_without_model_the_runner_is_passed_the_routed_execution_model(self):
        plain = ROUND.routing([CLAUDE], None, None)[CLAUDE]
        self.assertTrue(plain["execution_model"])
        stated = routed()
        argv = ROUND.target_argv("/clone", CLAUDE, None, "/tmp/out.json", [], stated)
        self.assertEqual(argv_model(argv), plain["execution_model"])
        self.assertEqual(stated["execution_model"], plain["execution_model"])
        self.assertEqual(stated["model_source"], "routing")
        self.assertNotIn("routed_model", stated)

    def test_an_operator_model_wins_and_the_routing_says_so(self):
        plain = ROUND.routing([CLAUDE], None, None)[CLAUDE]
        stated = routed("operator-pick")
        argv = ROUND.target_argv("/clone", CLAUDE, "operator-pick", "/tmp/out.json", [], stated)
        self.assertEqual(argv_model(argv), "operator-pick")
        self.assertEqual(stated["execution_model"], "operator-pick")
        self.assertEqual(stated["model_source"], "operator")
        self.assertEqual(stated["routed_model"], plain["execution_model"])

    def test_an_unmapped_execution_class_leaves_the_runner_on_its_default_and_says_so(self):
        stated = ROUND.with_models({CLAUDE: UNMAPPED}, None)[CLAUDE]
        argv = ROUND.target_argv("/clone", CLAUDE, None, "/tmp/out.json", [], stated)
        self.assertIsNone(argv_model(argv))
        self.assertEqual(stated["execution_model"], MODULE.DEFAULT_MODEL)
        self.assertEqual(stated["model_source"], "runner default")
        self.assertIsNone(stated["routed_model"])

    def test_the_round_and_the_runner_restate_one_routing_identically(self):
        for model in (None, "operator-pick"):
            stated = routed(model)
            argv = ROUND.target_argv("/clone", CLAUDE, model, "/tmp/out.json", [], stated)
            fresh = MODULE.routing(CLAUDE, stated["execution_class"], stated["assessment_class"])
            self.assertEqual(MODULE.executed_by(fresh, argv_model(argv)), (argv_model(argv),
                                                                             stated))


class RoundRecordTests(unittest.TestCase):
    def run_round(self, model):
        launched = []
        with tempfile.TemporaryDirectory() as temp:
            round_dir = Path(temp)
            (round_dir / "provision.json").write_text(json.dumps(
                {"clone": str(round_dir / "clone"), "records": str(round_dir / "records"),
                 "source_commit": "a" * 40}))

            def fake_run(argv, **kwargs):
                launched.append(argv)
                Path(argv[argv.index("--out") + 1]).write_text(json.dumps(
                    {"cases": {"installation": "passed"}, "observations": []}))
                return type("Done", (), {"returncode": 0})()

            with patch.object(ROUND.subprocess, "run", side_effect=fake_run):
                ROUND.run_round(round_dir, [CLAUDE], model, [], skip_smoke=True)
            written = json.loads((round_dir / "round.json").read_text())
        return launched[0], written["tier_routing"][CLAUDE]

    def test_a_round_without_model_runs_and_records_the_routed_model(self):
        argv, stated = self.run_round(None)
        self.assertEqual(argv_model(argv), stated["execution_model"])
        self.assertEqual(stated["model_source"], "routing")

    def test_a_round_with_model_runs_it_and_records_the_operator(self):
        argv, stated = self.run_round("operator-pick")
        self.assertEqual(argv_model(argv), "operator-pick")
        self.assertEqual(stated["execution_model"], "operator-pick")
        self.assertEqual(stated["model_source"], "operator")

    def test_the_round_driver_passes_the_routed_model_when_none_is_given(self):
        launched = []
        with tempfile.TemporaryDirectory() as temp:
            round_dir = Path(temp)
            (round_dir / "provision.json").write_text(json.dumps(
                {"clone": str(round_dir / "clone"), "records": str(round_dir / "records"),
                 "source_commit": "a" * 40}))
            done = type("Done", (), {"returncode": 0})()
            with patch("platform.system", return_value="Darwin"), \
                    patch.object(ROUND.subprocess, "run",
                                 side_effect=lambda argv, **k: launched.append(argv) or done):
                with redirect_stdout(io.StringIO()):
                    ROUND.main(["--round", str(round_dir), "--targets", CLAUDE, "--skip-smoke"])
        self.assertEqual(argv_model(launched[0]), routed()["execution_model"])


class RunnerModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.progress = Path(self.tmp.name) / "round.partial.jsonl"

    def record(self, model, names=("cost-posture", "installation")):
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else "a" * 40), \
                patch.dict(MODULE.CASES, dict((name, (None, "stub")) for name in names),
                           clear=True):
            return MODULE.record(CLAUDE, list(names), model, False, runner=passing,
                                 progress=self.progress, tier_routing=FAKE_ROUTING)

    def test_every_case_row_and_the_header_carry_the_model_run(self):
        data = self.record("small")
        rows = [json.loads(line) for line in self.progress.read_text().splitlines()]
        self.assertEqual([row["model_run"] for row in rows], ["small"] * 3)
        self.assertEqual(data["model_run"], "small")

    def test_a_resumed_log_never_unions_cases_run_on_another_model(self):
        self.record("small", names=("cost-posture",))
        header = dict((key, None) for key in MODULE.HEADER_KEYS)
        header.update(json.loads(self.progress.read_text().splitlines()[-1]))
        self.assertEqual(len(MODULE.progress_lines(self.progress, header)), 1)
        self.assertEqual(MODULE.progress_lines(self.progress, dict(header, model_run="big")), [])

    def test_a_rebuild_under_another_model_is_refused_rather_than_relabelled(self):
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else "a" * 40), \
                patch.dict(MODULE.CASES, {"cost-posture": (None, "stub")}, clear=True):
            MODULE.record(CLAUDE, ["cost-posture"], "small", False, runner=passing,
                          progress=self.progress)
        with redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(SystemExit, "another class routing"):
            MODULE.main(["--client", CLAUDE, "--from-progress", "--model", "other",
                         "--progress", str(self.progress)])

    def main_with(self, *extra):
        seen = {}

        def fake_record(client, names, model, keep, **kwargs):
            seen.update(model=model, routing=kwargs["tier_routing"])
            return {"cases": {"cost-posture": "passed"}}

        with patch("platform.system", return_value="Darwin"), \
                patch.object(MODULE, "record", side_effect=fake_record):
            with redirect_stdout(io.StringIO()):
                MODULE.main(["--client", CLAUDE, "--cases", "cost-posture",
                             "--out", str(Path(self.tmp.name) / "record.json")] + list(extra))
        return seen

    def test_the_runner_alone_runs_its_default_and_records_that_it_did(self):
        seen = self.main_with()
        self.assertEqual(seen["model"], MODULE.DEFAULT_MODEL)
        self.assertEqual(seen["routing"]["execution_model"], MODULE.DEFAULT_MODEL)
        self.assertEqual(seen["routing"]["model_source"], "runner default")
        self.assertEqual(seen["routing"]["routed_model"],
                         MODULE.routing(CLAUDE)["execution_model"])

    def test_the_runner_passed_the_routed_model_records_the_routing_as_its_source(self):
        model = MODULE.routing(CLAUDE)["execution_model"]
        seen = self.main_with("--model", model)
        self.assertEqual(seen["model"], model)
        self.assertEqual(seen["routing"]["model_source"], "routing")


if __name__ == "__main__":
    unittest.main()
