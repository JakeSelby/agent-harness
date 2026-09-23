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
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import isolate_home, without_harness_vars

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


def fake(label=None, judgment=None, confidence=None, answer="ask", point="grade-bash",
         status="ok", error=None, seed=0):
    """One judged result, for the metric arithmetic. Shaped as `judge` returns them."""
    return {"point": point, "label": label, "judgment": judgment, "confidence": confidence,
            "deterministic_answer": answer, "status": status, "error": error,
            "content_hash": hashlib.sha256(str(seed).encode()).hexdigest(),
            "split": evaluation.DEV, "request_hash": "%064x" % seed}


class IsolatedHome(unittest.TestCase):
    """A temporary HOME for every test, so nothing reads the developer's state directory.

    The kill switch, the config and the decision ledger all resolve from `HOME`, and a
    developer with the sentinel in place would otherwise see different results from CI.
    """

    def setUp(self):
        self.saved = dict(os.environ)
        self.tmp = tempfile.mkdtemp()
        isolate_home(self.tmp)
        os.environ["HARNESS_HOME"] = self.tmp

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ledger(self):
        return Path(self.tmp) / ".local" / "state" / "agent-harness" / "decisions.jsonl"


class PackTests(IsolatedHome):
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


class SplitTests(IsolatedHome):
    def test_the_split_is_a_function_of_the_content_and_nothing_else(self):
        seen = set(evaluation.split_for("a" * 64) for _ in range(20))
        self.assertEqual(len(seen), 1)
        self.assertIn(seen.pop(), evaluation.SPLITS)

    def test_both_sides_are_reached_and_the_share_is_honoured(self):
        hashes = [hashlib.sha256(str(n).encode()).hexdigest() for n in range(400)]
        sides = [evaluation.split_for(h) for h in hashes]
        self.assertIn(evaluation.DEV, sides)
        self.assertIn(evaluation.HELDOUT, sides)
        mostly = [evaluation.split_for(h, 0.99) for h in hashes]
        self.assertGreater(mostly.count(evaluation.DEV), 380)

    def test_a_share_that_is_not_a_fraction_is_refused(self):
        for share in (0, 1, 50, -0.5, True):
            with self.assertRaises(evaluation.EvalError):
                evaluation.split_for("a" * 64, share)

    def test_two_rows_that_differ_only_past_the_cap_share_a_side(self):
        """The split keys on the text the request carries, so one request is never in both."""
        capped = "rm -rf " + "x" * 64
        rows = [{"kind": "decision", "decision_id": "a", "point": "grade-bash",
                 "input": capped, "input_sha256": "a" * 64,
                 "deterministic_answer": "ask", "outcome": "ran"},
                {"kind": "decision", "decision_id": "b", "point": "grade-bash",
                 "input": capped, "input_sha256": "f" * 64,
                 "deterministic_answer": "ask", "outcome": "not_run"}]
        cases = evaluation.cases_from_rows(rows)
        self.assertEqual(cases[0]["split"], cases[1]["split"])
        self.assertEqual(cases[0]["content_hash"], cases[1]["content_hash"])

    def test_one_request_on_both_sides_is_refused_rather_than_measured(self):
        leaked = [fake(seed=1), dict(fake(seed=1), split=evaluation.HELDOUT)]
        with self.assertRaises(evaluation.EvalError):
            evaluation.check_no_leak(leaked)

    def test_a_case_keeps_its_side_when_the_log_grows(self):
        first = dict((c["content_hash"], c["split"])
                     for c in evaluation.cases_from_rows(joined()))
        again = dict((c["content_hash"], c["split"])
                     for c in evaluation.cases_from_rows(joined()[:6]))
        for content, side in again.items():
            self.assertEqual(first[content], side)

    def test_the_row_hash_is_ignored_and_the_request_text_is_keyed_instead(self):
        row = {"kind": "decision", "decision_id": "x", "point": "grade-bash",
               "input": "rm -rf /tmp/x", "input_sha256": "0" * 64,
               "deterministic_answer": "ask", "outcome": "ran"}
        case = evaluation.cases_from_rows([row])[0]
        self.assertEqual(case["content_hash"],
                         evaluation.content_key("grade-bash", "rm -rf /tmp/x"))
        self.assertEqual(case["split"], evaluation.split_for(case["content_hash"]))

    def test_the_report_is_written_without_a_clock_so_two_runs_are_identical(self):
        self.assertEqual(json.dumps(report(), sort_keys=True),
                         json.dumps(report(), sort_keys=True))


class CaseTests(IsolatedHome):
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


class JudgingTests(IsolatedHome):
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
        """The ledger resolves from the isolated HOME, so its absence is the assertion."""
        self.assertEqual(decision.ledger_path(), self.ledger())
        evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                         packs.get(packs.DECISION_ID))
        self.assertFalse(self.ledger().exists())

    def test_a_replay_opens_no_socket_even_with_a_key_in_the_environment(self):
        os.environ["JEV_API_KEY"] = "not-a-key"
        opened = []

        def refuse(*args, **kwargs):
            opened.append(args)
            raise AssertionError("a replay opened a socket")

        saved = socket.socket
        socket.socket = refuse
        try:
            results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                       packs.get(packs.DECISION_ID))
        finally:
            socket.socket = saved
        self.assertEqual(opened, [])
        self.assertTrue(any(r["judgment"] for r in results))

    def test_a_kill_switch_does_not_stop_a_replay(self):
        """It gates requests, and a replay makes none; the modes are what `judge` checks."""
        sentinel = Path(self.tmp) / ".local" / "state" / "agent-harness" / "jev-disabled"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("", encoding="utf-8")
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID))
        self.assertTrue(any(r["judgment"] for r in results))

    def test_a_budget_ceiling_stops_the_run_rather_than_the_machine(self):
        budget = jev.Budget(max_requests=2)
        results = evaluation.judge(evaluation.cases_from_rows(joined()), client(),
                                   packs.get(packs.DECISION_ID), budget=budget)
        self.assertEqual(sum(1 for r in results if r["error"] == "over_budget"),
                         len(results) - 2)


class MetricTests(IsolatedHome):
    def test_a_threshold_is_fitted_per_point_and_never_defaulted(self):
        data = report()
        self.assertEqual(set(data["points"]), set(["grade-bash", "stop-gate"]))
        thresholds = set(block["threshold"] for block in data["points"].values())
        self.assertNotIn(jev.DEFAULT_THRESHOLD, thresholds)
        for block in data["points"].values():
            self.assertEqual(block["threshold_fitted_on"], evaluation.DEV)
            self.assertEqual(block["evidence_split"], evaluation.HELDOUT)

    def test_a_higher_threshold_can_score_better_and_the_fit_finds_it(self):
        """Below the threshold the deterministic answer stands, so abstaining can be right.

        Four cases the deterministic hook got right and the judgment gets wrong, each at a low
        confidence, and one the judgment gets right at a high one. A fit that scored an
        abstention as a miss would sink to the lowest confidence in the set; the right answer
        is a cutoff above the four.
        """
        results = [fake(label="confirm", judgment="proceed", confidence=0.4 + n / 100.0,
                        answer="ask", seed=n) for n in range(4)]
        results.append(fake(label="proceed", judgment="proceed", confidence=0.95,
                            answer="ask", seed=9))
        threshold = evaluation.fit_threshold(results)
        self.assertGreater(threshold, 0.43)
        self.assertLessEqual(threshold, 0.95)
        self.assertEqual(evaluation.metrics(results, threshold)["accuracy"], 1.0)
        self.assertLess(evaluation.metrics(results, 0.0)["accuracy"], 1.0)

    def test_held_out_labels_cannot_move_the_fitted_threshold(self):
        dev = [fake(label="confirm", judgment="proceed", confidence=0.5, seed=n)
               for n in range(3)]
        dev.append(fake(label="proceed", judgment="proceed", confidence=0.9, seed=8))
        fitted = evaluation.fit_threshold(dev)
        held = [dict(fake(label="proceed", judgment="proceed", confidence=0.2, seed=50 + n),
                     split=evaluation.HELDOUT) for n in range(20)]
        self.assertEqual(evaluation.fit_threshold(dev), fitted)
        self.assertNotEqual(evaluation.fit_threshold(dev + held), fitted)

    def test_a_point_with_no_labelled_dev_case_is_reported_unfitted(self):
        self.assertIsNone(evaluation.fit_threshold([]))
        self.assertIsNone(evaluation.fit_threshold([{"label": "confirm", "confidence": None}]))

    def test_an_error_and_an_abstention_fall_back_and_are_counted_as_such(self):
        """Neither is a pass on its own: what is scored is the deterministic answer they leave."""
        results = [fake(label="proceed", status="error", error="bad", answer="ask", seed=1),
                   fake(label="proceed", judgment=jev.UNKNOWN, confidence=0.99, answer="ask",
                        seed=2)]
        block = evaluation.metrics(results, 0.5)
        self.assertEqual(block["accuracy"], 0.0)
        self.assertEqual(block["unusable"]["error"], 1)
        self.assertEqual(block["unusable"]["abstained"], 2)
        self.assertEqual(evaluation.predict(results[1], 0.5), evaluation.ABSTAIN)
        self.assertEqual(evaluation.effective_answer(results[1], 0.5), evaluation.CONFIRM)

    def test_a_confident_wrong_answer_lowers_the_accuracy_it_should(self):
        block = evaluation.metrics([fake(label="proceed", judgment="confirm", confidence=0.99,
                                         seed=3)], 0.5)
        self.assertEqual(block["accuracy"], 0.0)
        self.assertEqual(block["confusion"], {"proceed": {"confirm": 1}})

    def test_agreement_is_taken_over_the_labelled_cases_and_not_over_all_of_them(self):
        results = [fake(label="proceed", judgment="confirm", confidence=0.99, seed=4),
                   fake(judgment="confirm", confidence=0.99, seed=5)]
        block = evaluation.metrics(results, 0.5)
        self.assertEqual(block["labelled"], 1)
        self.assertEqual(block["agreement_deterministic"], 1.0)
        self.assertEqual(block["accuracy"], 0.0)
        self.assertEqual(block["deterministic_accuracy"], 0.0)

    def test_the_calibration_figure_is_zero_when_confidence_tracks_accuracy(self):
        results = [fake(label="confirm" if n < 9 else "proceed", judgment="confirm",
                        confidence=0.9, seed=n) for n in range(10)]
        figure = evaluation.calibration(results)
        self.assertEqual(figure["ece"], 0.0)
        self.assertEqual(figure["cases"], 10)

    def test_the_calibration_figure_finds_a_model_that_is_sure_and_wrong(self):
        results = [fake(label="proceed", judgment="confirm", confidence=0.95, seed=n)
                   for n in range(10)]
        self.assertAlmostEqual(evaluation.calibration(results)["ece"], 0.95, places=2)

    def test_the_interval_is_seeded_by_the_cases_and_repeats(self):
        results = [fake(label="confirm" if n % 3 else "proceed", judgment="confirm",
                        confidence=0.7 + n / 100.0, seed=n) for n in range(20)]
        first = evaluation.calibration(results)["ci95"]
        self.assertEqual(first, evaluation.calibration(list(reversed(results)))["ci95"])
        self.assertLessEqual(first[0], evaluation.calibration(results)["ece"])
        self.assertGreaterEqual(first[1], evaluation.calibration(results)["ece"])

    def test_the_resamples_are_draws_and_not_permutations_at_a_power_of_two(self):
        """An LCG modulo a power of two walks the indices in a cycle and resamples nothing."""
        stream = evaluation._Stream("seed")
        permutations = 0
        for _ in range(50):
            draw = [stream.below(16) for _ in range(16)]
            if len(set(draw)) == 16:
                permutations += 1
        self.assertLess(permutations, 5)

    def test_the_interval_over_sixteen_cases_is_not_degenerate(self):
        results = [fake(label="confirm" if n % 4 else "proceed", judgment="confirm",
                        confidence=0.6 + n / 50.0, seed=n) for n in range(16)]
        low, high = evaluation.calibration(results)["ci95"]
        self.assertLess(low, high)

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
        self.assertEqual(data["split"]["seed"], "point and capped input")
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

    def test_a_calibration_with_no_bins_is_a_refusal(self):
        with self.assertRaises(evaluation.EvalError):
            report(bins=0)

    def test_the_report_carries_no_input_text_and_no_absolute_path(self):
        """It is an artifact somebody sends on; a command and a home directory are not in it."""
        data = evaluation.report(joined(), client(),
                                 source={"log": str(LOG), "replay": str(RESPONSES),
                                         "client": "replay"})
        written = json.dumps(data, sort_keys=True)
        self.assertEqual(data["source"]["log"], "decisions.jsonl")
        self.assertEqual(data["source"]["replay"], "responses.json")
        self.assertNotIn(str(REPO), written)
        self.assertNotIn(os.sep + os.sep.join(["Users"]), written)
        for case in evaluation.cases_from_rows(joined()):
            self.assertNotIn(case["input"], written)


class CommandTests(IsolatedHome):
    """`decisions eval` end to end. The isolated HOME is what the state directory resolves to."""

    def run_eval(self, *args):
        env = without_harness_vars()
        env.update({"HOME": self.tmp, "HARNESS_HOME": self.tmp})
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "decisions",
                               "eval"] + list(args), capture_output=True, text=True,
                              cwd=self.tmp, env=env)

    def test_a_replay_run_writes_the_report_the_doc_describes(self):
        out = Path(self.tmp) / "report.json"
        done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES), "--out", str(out))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("pack decision" + packs.SEPARATOR + "1.0.0", done.stdout)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(set(data["points"]), set(["grade-bash", "stop-gate"]))
        self.assertEqual(data["source"]["client"], "replay")
        for block in data["points"].values():
            self.assertIn(evaluation.DEV, block)
            self.assertIn(evaluation.HELDOUT, block)

    def test_the_default_report_lands_in_the_state_directory(self):
        done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES))
        self.assertEqual(done.returncode, 0, done.stderr)
        written = Path(self.tmp) / ".local" / "state" / "agent-harness" / "jev-eval.json"
        self.assertTrue(written.exists(), done.stdout)
        self.assertFalse(self.ledger().exists(), "an evaluation wrote to the ledger")

    def test_the_fitted_split_is_printed_only_with_a_warning(self):
        out = Path(self.tmp) / "report.json"
        done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES), "--out", str(out),
                             "--split", "dev", "--point", "grade-bash")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("rates on dev", done.stdout)
        self.assertIn("not evidence", done.stdout)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(set(data["points"]), set(["grade-bash"]))
        self.assertIsNotNone(data["points"]["grade-bash"]["heldout"]["cases"])

    def test_a_run_with_neither_a_replay_nor_live_is_refused(self):
        done = self.run_eval("--log", str(LOG))
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("--replay", done.stderr + done.stdout)

    def test_a_replay_and_a_live_run_together_are_refused(self):
        done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES), "--live",
                             "--max-requests", "5")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("name one", done.stderr + done.stdout)

    def test_a_live_run_without_a_ceiling_is_refused_before_anything_is_sent(self):
        done = self.run_eval("--log", str(LOG), "--live")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("--max-requests", done.stderr + done.stdout)

    def test_a_live_run_with_an_empty_allowlist_is_refused_as_pointless(self):
        """Every request would carry the same four base fields, so the run would measure one."""
        done = self.run_eval("--log", str(LOG), "--live", "--max-requests", "5")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("state_fields", done.stderr + done.stdout)

    def test_a_dollar_budget_with_no_price_is_refused_rather_than_guessed(self):
        done = self.run_eval("--log", str(LOG), "--live", "--max-requests", "5",
                             "--budget-usd", "1.0")
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("--usd-per-mtok", done.stderr + done.stdout)

    def test_a_bin_count_and_a_dev_share_that_cannot_be_honoured_are_refused(self):
        for args in (["--bins", "0"], ["--dev-share", "0"], ["--dev-share", "1"],
                     ["--dev-share", "50"]):
            done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES), *args)
            self.assertEqual(done.returncode, 1, done.stdout)

    def test_an_unknown_pack_version_names_the_ones_that_exist(self):
        done = self.run_eval("--log", str(LOG), "--replay", str(RESPONSES),
                             "--pack", "decision:2.0.0")
        self.assertEqual(done.returncode, 1)
        self.assertIn("1.0.0", done.stderr)


class FixtureTests(IsolatedHome):
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
