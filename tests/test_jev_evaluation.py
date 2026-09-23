# SPDX-License-Identifier: MIT
"""Unit tests for versioned question packs and the decision-log evaluation runner.

The properties under test are that a pack cannot be rewritten by whatever holds it, that the
split is a function of the content and of nothing else, that a threshold is fitted per decision
point and never defaulted, that an error is never counted as a pass, and that a run without
`--live` opens no socket and writes no ledger row.

No test here reaches the network: every answer comes from `jev.ReplayClient` over
`tests/fixtures/jev/eval/responses.json`, which `tests/fixtures/jev/eval/record.py` writes
beside the `decisions.jsonl` it is keyed to.

Run: python3 -m unittest discover tests
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision  # noqa: E402
from harness_core.decisions import controls, evaluation, jev, packs  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jev" / "eval"
LOG = FIXTURES / "decisions.jsonl"
RESPONSES = FIXTURES / "responses.json"


def rows():
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def joined():
    """The decision rows with their outcomes filled in, the join the hook module does."""
    outcomes = {}
    for row in rows():
        if row.get("kind") == "outcome":
            outcomes.setdefault(row["decision_id"], row.get("outcome"))
    return [dict(row, outcome=outcomes.get(row["decision_id"]))
            for row in rows() if row.get("kind") != "outcome"]


def client():
    return jev.ReplayClient.from_file(RESPONSES)


def report(**kwargs):
    return evaluation.report(joined(), client(), **kwargs)


class PackTests(unittest.TestCase):
    def test_a_pack_carries_an_id_a_version_and_the_hash_of_its_content(self):
        pack = packs.get(packs.DECISION_ID)
        self.assertEqual(pack.pack_id, "decision")
        self.assertEqual(pack.version, "1.0.0")
        self.assertEqual(pack.content_hash, jev.pack_hash(jev.DECISION_PACK))
        self.assertEqual(pack.identity(), {"pack_id": "decision", "pack_version": "1.0.0",
                                           "pack_hash": pack.content_hash})

    def test_the_criteria_cannot_be_rewritten_through_what_a_reader_was_handed(self):
        """The protection the acceptance criterion asks for: a pack is frozen at construction."""
        pack = packs.get(packs.DECISION_ID)
        held = pack.questions
        held[jev.JUDGMENT]["options"]["proceed"] = "anything the task asked for is fine"
        held["severity"]["levels"].append("trivial")
        self.assertNotEqual(pack.questions[jev.JUDGMENT]["options"]["proceed"],
                            "anything the task asked for is fine")
        self.assertEqual(pack.content_hash, jev.pack_hash(pack.questions))

    def test_a_pack_that_would_be_read_blind_is_refused(self):
        with self.assertRaises(jev.PackError):
            packs.Pack("probe", "1.0.0", {"severity": jev.DECISION_PACK["severity"]})

    def test_an_id_or_a_version_that_is_not_one_is_refused(self):
        for pack_id, version in (("Probe", "1.0.0"), ("probe", "1.0"), ("probe", "v1.0.0")):
            with self.assertRaises(jev.PackError):
                packs.Pack(pack_id, version, jev.DECISION_PACK)

    def test_a_registered_version_is_never_re_pointed(self):
        with self.assertRaises(jev.PackError):
            packs.register(packs.Pack(packs.DECISION_ID, "1.0.0", jev.DECISION_PACK))

    def test_resolving_names_the_registered_versions_when_there_is_no_match(self):
        with self.assertRaises(jev.PackError) as caught:
            packs.resolve("decision:9.9.9")
        self.assertIn("1.0.0", str(caught.exception))

    def test_a_threshold_does_not_carry_across_a_pack_edit(self):
        pack = packs.get(packs.DECISION_ID)
        pack.verify(pack.content_hash)
        with self.assertRaises(jev.PackError):
            pack.verify("0" * 64)

    def test_the_provider_records_which_pack_it_used(self):
        provider = jev.JevProvider(base=decision.NullProvider(), client=client(),
                                   controls=evaluation.shadow_controls())
        self.assertEqual(provider.pack_identity["pack_version"], "1.0.0")
        self.assertEqual(provider.pack_identity["pack_id"], "decision")


class SplitTests(unittest.TestCase):
    def test_the_split_is_a_function_of_the_content_and_nothing_else(self):
        seen = set(evaluation.split_for("a" * 64) for _ in range(20))
        self.assertEqual(len(seen), 1)
        self.assertIn(seen.pop(), evaluation.SPLITS)

    def test_both_sides_are_reached_and_the_share_is_honoured(self):
        hashes = [hashlib.sha256(str(n).encode()).hexdigest() for n in range(400)]
        sides = [evaluation.split_for(h) for h in hashes]
        self.assertIn(evaluation.DEV, sides)
        self.assertIn(evaluation.HELDOUT, sides)
        everything = [evaluation.split_for(h, 100) for h in hashes]
        self.assertEqual(set(everything), set([evaluation.DEV]))

    def test_a_case_keeps_its_side_when_the_log_grows(self):
        first = dict((c["content_hash"], c["split"])
                     for c in evaluation.cases_from_rows(joined()))
        again = dict((c["content_hash"], c["split"])
                     for c in evaluation.cases_from_rows(joined()[:6]))
        for content, side in again.items():
            self.assertEqual(first[content], side)

    def test_a_row_with_no_content_hash_is_split_by_its_text(self):
        row = {"kind": "decision", "decision_id": "x", "point": "grade-bash",
               "input": "rm -rf /tmp/x", "deterministic_answer": "ask", "outcome": "ran"}
        case = evaluation.cases_from_rows([row])[0]
        self.assertEqual(case["split"], evaluation.split_for(case["content_hash"]))

    def test_the_report_is_written_without_a_clock_so_two_runs_are_identical(self):
        self.assertEqual(json.dumps(report(), sort_keys=True),
                         json.dumps(report(), sort_keys=True))


class CaseTests(unittest.TestCase):
    def test_the_recorded_set_is_at_least_a_dozen_rows(self):
        cases = evaluation.cases_from_rows(joined())
        self.assertGreaterEqual(len(cases), 12)
        self.assertGreaterEqual(sum(1 for c in cases if c["label"]), 12)

    def test_an_outcome_this_module_cannot_read_is_unlabelled_and_never_invented(self):
        row = {"kind": "decision", "decision_id": "x", "point": "grade-bash",
               "input": "make release", "deterministic_answer": "ask",
               "input_sha256": "b" * 64, "outcome": "wedged"}
        self.assertIsNone(evaluation.cases_from_rows([row])[0]["label"])

    def test_a_row_with_no_input_cannot_be_replayed_and_is_dropped(self):
        row = {"kind": "decision", "decision_id": "x", "point": "grade-bash", "input": "",
               "deterministic_answer": "ask", "outcome": "ran"}
        self.assertEqual(evaluation.cases_from_rows([row]), [])

    def test_a_point_filter_keeps_only_that_point(self):
        cases = evaluation.cases_from_rows(joined(), "stop-gate")
        self.assertTrue(cases)
        self.assertEqual(set(c["point"] for c in cases), set(["stop-gate"]))

    def test_the_replayed_state_carries_only_what_the_allowlist_allows(self):
        case = evaluation.cases_from_rows(joined())[0]
        allowed = evaluation.shadow_controls(state_fields=())
        state = evaluation.case_state(case, allowed, "repo:eval/replay")
        self.assertEqual(set(state), set(controls.BASE_FIELDS))
        wide = evaluation.case_state(case, evaluation.shadow_controls(), "repo:eval/replay")
        self.assertIn("command", wide)


class JudgingTests(unittest.TestCase):
    def test_an_evaluation_will_not_run_outside_shadow_mode(self):
        acting = controls.Controls.acting()
        with self.assertRaises(evaluation.EvalError):
            evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                             packs.get(packs.DECISION_ID), acting)

    def test_a_judgment_is_asked_at_threshold_zero_so_one_replay_fits_many(self):
        """The confidence survives the call; a thresholded `unknown` status would lose it."""
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID))
        confident = [r for r in results if r["confidence"] is not None]
        self.assertTrue(confident)
        self.assertTrue(any(r["confidence"] < jev.DEFAULT_THRESHOLD for r in confident))

    def test_replaying_writes_no_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                             packs.get(packs.DECISION_ID))
            self.assertFalse(target.exists())

    def test_a_budget_ceiling_stops_the_run_rather_than_the_machine(self):
        budget = jev.Budget(max_requests=2)
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID), budget=budget)
        self.assertEqual(sum(1 for r in results if r["error"] == "over_budget"),
                         len(results) - 2)


class MetricTests(unittest.TestCase):
    def test_a_threshold_is_fitted_per_point_and_never_defaulted(self):
        data = report()
        self.assertEqual(set(data["points"]), set(["grade-bash", "stop-gate"]))
        thresholds = set(block["threshold"] for block in data["points"].values())
        self.assertNotIn(jev.DEFAULT_THRESHOLD, thresholds)
        for block in data["points"].values():
            self.assertEqual(block["threshold_fitted_on"], evaluation.DEV)

    def test_a_point_with_no_labelled_dev_case_is_reported_unfitted(self):
        self.assertIsNone(evaluation.fit_threshold([]))
        self.assertIsNone(evaluation.fit_threshold([{"label": "confirm", "confidence": None}]))

    def test_an_error_and_an_abstention_are_never_passes(self):
        results = [{"label": "confirm", "judgment": None, "confidence": None,
                    "status": "error", "error": "bad", "content_hash": "a" * 64,
                    "deterministic_answer": "ask"},
                   {"label": "confirm", "judgment": jev.UNKNOWN, "confidence": 0.99,
                    "status": "ok", "error": None, "content_hash": "b" * 64,
                    "deterministic_answer": "ask"}]
        block = evaluation.metrics(results, 0.5)
        self.assertEqual(block["accuracy"], 0.0)
        self.assertEqual(block["unusable"]["error"], 1)
        self.assertEqual(block["unusable"]["abstained"], 1)
        self.assertEqual(evaluation.predict(results[1], 0.5), evaluation.ABSTAIN)

    def test_a_confident_wrong_answer_lowers_the_accuracy_it_should(self):
        block = evaluation.metrics(
            [{"label": "proceed", "judgment": "confirm", "confidence": 0.99, "status": "ok",
              "content_hash": "c" * 64, "deterministic_answer": "ask", "error": None}], 0.5)
        self.assertEqual(block["accuracy"], 0.0)
        self.assertEqual(block["confusion"], {"proceed": {"confirm": 1}})

    def test_agreement_with_the_deterministic_answer_is_its_own_number(self):
        results = [{"label": "proceed", "judgment": "confirm", "confidence": 0.99,
                    "status": "ok", "content_hash": "d" * 64, "deterministic_answer": "ask",
                    "error": None}]
        block = evaluation.metrics(results, 0.5)
        self.assertEqual(block["agreement_deterministic"], 1.0)
        self.assertEqual(block["accuracy"], 0.0)

    def test_the_calibration_figure_is_zero_when_confidence_tracks_accuracy(self):
        results = [{"label": "confirm" if n < 9 else "proceed", "judgment": "confirm",
                    "confidence": 0.9, "status": "ok", "content_hash": hashlib.sha256(str(n).encode()).hexdigest(),
                    "deterministic_answer": "ask", "error": None} for n in range(10)]
        figure = evaluation.calibration(results)
        self.assertEqual(figure["ece"], 0.0)
        self.assertEqual(figure["cases"], 10)

    def test_the_calibration_figure_finds_a_model_that_is_sure_and_wrong(self):
        results = [{"label": "proceed", "judgment": "confirm", "confidence": 0.95,
                    "status": "ok", "content_hash": hashlib.sha256(str(n).encode()).hexdigest(), "deterministic_answer": "ask",
                    "error": None} for n in range(10)]
        self.assertAlmostEqual(evaluation.calibration(results)["ece"], 0.95, places=2)

    def test_the_interval_is_seeded_by_the_cases_and_repeats(self):
        results = [{"label": "confirm" if n % 3 else "proceed", "judgment": "confirm",
                    "confidence": 0.7 + n / 100.0, "status": "ok", "content_hash": hashlib.sha256(str(n).encode()).hexdigest(),
                    "deterministic_answer": "ask", "error": None} for n in range(20)]
        first = evaluation.calibration(results)["ci95"]
        self.assertEqual(first, evaluation.calibration(list(reversed(results)))["ci95"])
        self.assertLessEqual(first[0], evaluation.calibration(results)["ece"])
        self.assertGreaterEqual(first[1], evaluation.calibration(results)["ece"])

    def test_one_pass_has_no_flip_rate_to_report(self):
        self.assertIsNone(evaluation.flip_rate([[]])["rate"])

    def test_a_replay_cannot_disagree_with_itself(self):
        data = report(repeats=3)
        self.assertEqual(data["flip"]["passes"], 3)
        self.assertEqual(data["flip"]["rate"], 0.0)

    def test_cost_is_reported_only_where_a_price_was_given(self):
        data = report()
        self.assertIsNone(data["points"]["grade-bash"]["heldout"]["usd_per_1000_decisions"])
        priced = report(usd_per_mtok=3.0)
        self.assertGreater(priced["points"]["grade-bash"]["heldout"]["usd_per_1000_decisions"],
                           0)

    def test_the_report_names_the_pack_the_split_and_the_caveats(self):
        data = report()
        self.assertEqual(data["pack"]["pack_version"], "1.0.0")
        self.assertEqual(data["split"]["seed"], "input_sha256")
        self.assertTrue(any("not_run" in line for line in data["caveats"]))
        held = data["points"]["grade-bash"]["heldout"]
        # A replay's latency is this runner's and is reported as unmeasured, not as a number
        # whose name claims it came from the service.
        self.assertFalse(held["latency_ms"]["measured"])
        self.assertIsNone(held["latency_ms"]["p50"])
        self.assertGreater(held["input_tokens"], 0)
        self.assertEqual(held["models"], [jev.DEFAULT_MODEL])

    def test_a_log_with_nothing_replayable_is_a_refusal_and_not_an_empty_report(self):
        with self.assertRaises(evaluation.EvalError):
            evaluation.report([], client())


class CommandTests(unittest.TestCase):
    def run_eval(self, *args, **kwargs):
        env = without_harness_vars()
        env.update({"HOME": kwargs["home"], "HARNESS_HOME": kwargs["home"]})
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "decisions",
                               "eval"] + list(args), capture_output=True, text=True,
                              cwd=kwargs["home"], env=env)

    def test_a_replay_run_writes_the_report_the_doc_describes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES),
                                 "--out", str(out), home=tmp)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("pack decision" + packs.SEPARATOR + "1.0.0", done.stdout)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(set(data["points"]), set(["grade-bash", "stop-gate"]))
            self.assertEqual(data["source"]["client"], "replay")
            for block in data["points"].values():
                self.assertIn(evaluation.DEV, block)
                self.assertIn(evaluation.HELDOUT, block)

    def test_the_printed_split_is_chosen_and_the_file_still_holds_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES), "--out",
                                 str(out), "--split", "dev", "--point", "grade-bash", home=tmp)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("rates on dev", done.stdout)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(set(data["points"]), set(["grade-bash"]))
            self.assertIsNotNone(data["points"]["grade-bash"]["heldout"]["cases"])

    def test_a_run_with_neither_a_replay_nor_live_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_eval("--log", str(LOG), home=tmp)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("--replay", done.stderr + done.stdout)

    def test_a_live_run_without_a_ceiling_is_refused_before_anything_is_sent(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_eval("--log", str(LOG), "--live", home=tmp)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("--max-requests", done.stderr + done.stdout)

    def test_a_dollar_budget_with_no_price_is_refused_rather_than_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_eval("--log", str(LOG), "--live", "--max-requests", "5",
                                 "--budget-usd", "1.0", home=tmp)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("--usd-per-mtok", done.stderr + done.stdout)

    def test_an_unknown_pack_version_names_the_ones_that_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES),
                                 "--pack", "decision:2.0.0", home=tmp)
            self.assertEqual(done.returncode, 1)
            self.assertIn("1.0.0", done.stderr)

    def test_a_replay_run_leaves_no_ledger_row_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_eval("--log", str(LOG), "--replay", str(RESPONSES),
                          "--out", str(Path(tmp) / "r.json"), home=tmp)
            ledger = Path(tmp) / ".local" / "state" / "agent-harness" / "decisions.jsonl"
            self.assertFalse(ledger.exists(), "an evaluation wrote to the ledger")


class FixtureTests(unittest.TestCase):
    def test_every_recorded_response_still_keys_to_a_request_this_code_builds(self):
        """The generator's output and the pack have not drifted apart."""
        recorded = json.loads(RESPONSES.read_text(encoding="utf-8"))
        keys = set(entry["request_hash"] for entry in recorded["entries"])
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID))
        self.assertEqual(set(r["request_hash"] for r in results), keys)
        self.assertEqual([r for r in results if r["error"] == "replay_missing"], [])

    def test_the_fixture_was_recorded_against_this_pack_version(self):
        recorded = json.loads(RESPONSES.read_text(encoding="utf-8"))
        self.assertEqual(recorded["pack"], packs.get(packs.DECISION_ID).identity())

    def test_the_recorded_set_holds_a_response_that_will_not_parse(self):
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID))
        self.assertTrue(any(r["status"] == "error" for r in results))
        self.assertTrue(any(r["judgment"] == jev.UNKNOWN for r in results))


if __name__ == "__main__":
    unittest.main()
