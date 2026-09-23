# SPDX-License-Identifier: MIT
"""Unit tests for the Jev decision provider: packs, typed answers, budget and failing open.

The properties under test are that a choice question without an explicit `unknown` option is
refused before anything is sent, that a malformed, incomplete or surprising response is an
error and never a judgment with the bad parts dropped, that a judgment may tighten an `allow`
into an `ask` and may never widen anything, and that every path with no usable answer returns
the deterministic provider's decision unchanged.

No test here reaches the network. The live client is inert unless it is constructed with
`live=True`, and every answered call goes through `ReplayClient` over
`tests/fixtures/jev/decisions.json`, which `tests/fixtures/jev/record.py` writes.

Run: python3 -m unittest discover tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision  # noqa: E402
from harness_core.decisions import jev  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jev" / "decisions.json"
RECORDED = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = dict((entry["name"], entry) for entry in RECORDED["entries"])


def pack(**questions):
    base = {"verdict": {"type": "choice", "instructions": "Decide.",
                        "options": {"yes": "It holds.", "no": "It does not.",
                                    "unknown": "Not enough to say."}}}
    base.update(questions)
    return base


def answer(choice="yes", top=0.9):
    rest = round((1 - top) / 2, 4)
    return {"type": "choice", "choice": choice,
            "probabilities": {"yes": rest, "no": rest, "unknown": rest, choice: top}}


def response(answers=None, model=jev.DEFAULT_MODEL):
    return {"model": model,
            "answers": {"verdict": answer()} if answers is None else answers,
            "usage": {"input_tokens": 10, "output_tokens": 2}}


class PackTests(unittest.TestCase):
    def refused(self, bad):
        with self.assertRaises(jev.PackError) as caught:
            jev.validate_pack(bad)
        return str(caught.exception)

    def test_a_choice_question_without_an_unknown_option_is_refused(self):
        message = self.refused({"verdict": {
            "type": "choice", "instructions": "Decide.",
            "options": {"yes": "It holds.", "no": "It does not."}}})
        self.assertIn("`unknown` option", message)
        self.assertIn("cannot abstain", message)

    def test_the_shipped_decision_pack_offers_one(self):
        self.assertIn(jev.UNKNOWN, jev.DECISION_PACK["judgment"]["options"])
        self.assertEqual(jev.validate_pack(jev.DECISION_PACK), jev.DECISION_PACK)

    def test_a_score_takes_an_ordered_array_of_two_to_ten_levels(self):
        for levels in (["low", "high"], ["a", "b", "c", "d", "e"]):
            jev.validate_pack(pack(score={"type": "score", "instructions": "How bad?",
                                          "levels": levels}))
        for levels in (["only"], [str(i) for i in range(11)], {"low": "x", "high": "y"},
                       ["same", "same"]):
            with self.subTest(levels=levels):
                message = self.refused(pack(score={"type": "score", "instructions": "How bad?",
                                                   "levels": levels}))
                self.assertIn("levels", message)

    def test_a_boolean_question_carries_nothing_but_its_instructions(self):
        jev.validate_pack(pack(flag={"type": "boolean", "instructions": "Yes or no?"}))
        message = self.refused(pack(flag={"type": "boolean", "instructions": "Yes or no?",
                                          "options": {}}))
        self.assertIn("exactly instructions, type", message)

    def test_an_unknown_answer_type_is_refused_rather_than_ignored(self):
        message = self.refused({"q": {"type": "ranking", "instructions": "Order them."}})
        self.assertIn("known types are choice, boolean, score", message)

    def test_an_empty_or_oversized_pack_is_refused(self):
        self.assertIn("1 to 16", self.refused({}))
        self.assertIn("1 to 16", self.refused(dict(("q%d" % i, pack()["verdict"])
                                                   for i in range(17))))

    def test_the_pack_hash_is_the_one_the_fixtures_were_recorded_against(self):
        """A pack edit moves this; rerun `python3 tests/fixtures/jev/record.py`."""
        self.assertEqual(jev.pack_hash(jev.DECISION_PACK), RECORDED["pack_hash"])


class RequestTests(unittest.TestCase):
    def test_state_plus_the_longest_question_is_bounded(self):
        with self.assertRaises(jev.PackError) as caught:
            jev.build_request(pack(), {"blob": "x" * (jev.MAX_STATE_TOKENS * 4)})
        self.assertIn("longest question", str(caught.exception))

    def test_the_whole_request_is_bounded_too(self):
        original = jev.MAX_REQUEST_TOKENS
        jev.MAX_REQUEST_TOKENS = 10
        try:
            with self.assertRaises(jev.PackError) as caught:
                jev.build_request(pack(), {"action_class": "coding.git_push"})
        finally:
            jev.MAX_REQUEST_TOKENS = original
        self.assertIn("request exceeds", str(caught.exception))

    def test_a_state_that_is_not_an_object_or_is_empty_is_refused(self):
        for state in ({}, [], "text", None):
            with self.subTest(state=state):
                with self.assertRaises(jev.PackError):
                    jev.build_request(pack(), state)

    def test_state_that_cannot_be_serialised_is_refused_rather_than_sent(self):
        with self.assertRaises(jev.PackError):
            jev.build_request(pack(), {"when": object()})

    def test_a_model_that_is_not_an_id_is_refused(self):
        with self.assertRaises(jev.PackError) as caught:
            jev.build_request(pack(), {"a": "b"}, model="jev 1.13/../etc")
        self.assertIn("model", str(caught.exception))

    def test_the_request_hash_is_the_one_each_fixture_was_recorded_against(self):
        for name, entry in sorted(CASES.items()):
            with self.subTest(case=name):
                action = decision.Action(action_class=entry["action_class"],
                                         grade=entry["grade"])
                state = jev.decision_state(action, entry["counterparty"], entry["context"])
                request = jev.build_request(jev.DECISION_PACK, state)
                self.assertEqual(jev.digest(request), entry["request_hash"])

    def test_the_state_carries_the_action_and_nothing_the_caller_smuggled_in(self):
        action = decision.Action(action_class="coding.git_push", grade=3)
        state = jev.decision_state(action, "repo:a/main",
                                   {"command": "git push", "transcript": "secret prose"})
        self.assertEqual(set(state), {"action_class", "counterparty", "grade", "grade_scale",
                                      "command"})
        self.assertNotIn("secret prose", jev.canonical(state).decode("utf-8"))


class ClientTests(unittest.TestCase):
    def test_the_live_client_is_inert_until_a_caller_turns_it_on(self):
        with self.assertRaises(jev.Unavailable) as caught:
            jev.JevClient()({"model": jev.DEFAULT_MODEL})
        self.assertEqual(caught.exception.code, "live_not_enabled")

    def test_a_live_client_with_no_key_in_the_environment_never_opens_a_socket(self):
        import os

        saved = dict((name, os.environ.pop(name)) for name in jev.KEY_VARIABLES
                     if name in os.environ)
        try:
            with self.assertRaises(jev.Unavailable) as caught:
                jev.JevClient(live=True, endpoint="http://127.0.0.1:1/never")(
                    {"model": jev.DEFAULT_MODEL})
        finally:
            os.environ.update(saved)
        self.assertEqual(caught.exception.code, "missing_key")

    def test_transport_options_are_validated(self):
        for kwargs in ({"live": "yes"}, {"timeout": 0}, {"timeout": 61}, {"timeout": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(jev.PackError):
                    jev.JevClient(**kwargs)

    def test_replay_answers_only_the_request_it_recorded(self):
        client = jev.ReplayClient.from_file(FIXTURE)
        entry = CASES["proceed"]
        self.assertEqual(client.responses[entry["request_hash"]], entry["response"])
        with self.assertRaises(jev.Unavailable) as caught:
            client({"model": jev.DEFAULT_MODEL, "state": {"a": 1}, "questions": pack()})
        self.assertEqual(caught.exception.code, "replay_missing")

    def test_a_replay_fixture_without_entries_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"responses": []}), encoding="utf-8")
            with self.assertRaises(jev.PackError):
                jev.ReplayClient.from_file(path)


class AnswerTests(unittest.TestCase):
    def parsed(self, questions, answers, **kwargs):
        return jev.parse_response(questions, response(answers, **kwargs))

    def refused(self, questions, answers, **kwargs):
        with self.assertRaises(jev.PackError) as caught:
            self.parsed(questions, answers)
        return str(caught.exception)

    def test_a_choice_answer_takes_its_confidence_from_its_own_probability(self):
        answers, usage = self.parsed(pack(), {"verdict": answer("no", 0.72)})
        self.assertEqual(answers["verdict"]["choice"], "no")
        self.assertAlmostEqual(answers["verdict"]["confidence"], 0.72)
        self.assertEqual(usage, {"input_tokens": 10, "output_tokens": 2})

    def test_a_stated_confidence_can_only_lower_it(self):
        value = dict(answer("yes", 0.9), confidence=0.4)
        answers, _ = self.parsed(pack(), {"verdict": value})
        self.assertAlmostEqual(answers["verdict"]["confidence"], 0.4)

    def test_a_yes_no_answer_is_a_probability_with_no_confidence_field(self):
        questions = pack(flag={"type": "boolean", "instructions": "Yes or no?"})
        answers, _ = self.parsed(questions, {"verdict": answer(),
                                             "flag": {"type": "boolean", "probability": 0.2}})
        self.assertEqual(answers["flag"]["value"], False)
        self.assertAlmostEqual(answers["flag"]["confidence"], 0.8)
        message = self.refused(questions, {"verdict": answer(),
                                           "flag": {"type": "boolean", "probability": 0.2,
                                                    "confidence": 0.9}})
        self.assertIn("exactly probability, type", message)

    def test_a_score_answer_names_its_level_and_where_it_sits(self):
        levels = ["none", "low", "high"]
        questions = pack(score={"type": "score", "instructions": "How bad?", "levels": levels})
        answers, _ = self.parsed(questions, {
            "verdict": answer(),
            "score": {"type": "score", "level": "high",
                      "probabilities": {"none": 0.05, "low": 0.05, "high": 0.9}}})
        self.assertEqual(answers["score"]["level"], "high")
        self.assertEqual(answers["score"]["index"], 2)

    def test_a_malformed_or_surprising_response_is_refused(self):
        cases = [
            ({"verdict": answer(), "extra": answer()}, "exactly the questions asked"),
            ({}, "exactly the questions asked"),
            ({"verdict": dict(answer(), note="why")}, "must carry exactly"),
            ({"verdict": {"type": "boolean", "probability": 0.9}}, "type 'choice'"),
            ({"verdict": dict(answer(), choice="maybe")}, "not one this question offered"),
            ({"verdict": {"type": "choice", "choice": "yes",
                          "probabilities": {"yes": 0.2, "no": 0.2, "unknown": 0.2}}},
             "sum to one"),
            ({"verdict": {"type": "choice", "choice": "yes",
                          "probabilities": {"yes": 0.1, "no": 0.8, "unknown": 0.1}}},
             "most likely label"),
            ({"verdict": {"type": "choice", "choice": "yes",
                          "probabilities": {"yes": 1.0, "no": 0.0}}},
             "one probability per label"),
        ]
        for answers, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, self.refused(pack(), answers))

    def test_the_envelope_is_checked_before_the_answers(self):
        for body, expected in (({"answers": {"verdict": answer()}}, "exactly answers"),
                               (dict(response(), id="req_1"), "exactly answers"),
                               (dict(response(), model="not a model id"), "not a model id"),
                               (dict(response(), usage={"input_tokens": 1}), "exactly "
                                "input_tokens"),
                               (dict(response(), usage={"input_tokens": -1,
                                                        "output_tokens": 0}),
                                "not a token count")):
            with self.subTest(expected=expected):
                with self.assertRaises(jev.PackError) as caught:
                    jev.parse_response(pack(), body)
                self.assertIn(expected, str(caught.exception))

    def test_unknown_and_low_confidence_both_read_as_no_answer(self):
        for answers in ({"verdict": answer("unknown", 0.99)}, {"verdict": answer("yes", 0.6)}):
            with self.subTest(answers=answers):
                parsed, _ = self.parsed(pack(), answers)
                self.assertTrue(jev.uncertain(parsed))
        parsed, _ = self.parsed(pack(), {"verdict": answer("yes", 0.95)})
        self.assertFalse(jev.uncertain(parsed))


class BudgetTests(unittest.TestCase):
    def test_a_ceiling_refuses_the_call_that_would_reach_it(self):
        budget = jev.Budget(max_requests=1)
        budget.check()
        budget.spend({"input_tokens": 5, "output_tokens": 5})
        with self.assertRaises(jev.Unavailable) as caught:
            budget.check()
        self.assertEqual(caught.exception.code, "over_budget")

    def test_tokens_are_charged_from_the_usage_the_response_reported(self):
        budget = jev.Budget(max_tokens=100)
        budget.spend({"input_tokens": 60, "output_tokens": 40})
        self.assertEqual(budget.as_dict()["tokens"], 100)
        self.assertRaises(jev.Unavailable, budget.check)

    def test_a_response_nobody_could_parse_is_still_charged(self):
        budget = jev.Budget(max_requests=4)
        client = _Fixed({"model": jev.DEFAULT_MODEL, "answers": {}, "usage": {}})
        result = jev.ask(pack(), {"a": "b"}, client, budget=budget)
        self.assertEqual(result["status"], "error")
        self.assertEqual(budget.requests, 1)
        self.assertGreater(budget.tokens, 0)

    def test_an_exhausted_budget_is_unavailable_and_makes_no_call(self):
        client = _Fixed(response())
        result = jev.ask(pack(), {"a": "b"}, client, budget=jev.Budget(max_requests=0))
        self.assertEqual((result["status"], result["error"]), ("unavailable", "over_budget"))
        self.assertEqual(client.calls, 0)

    def test_a_ceiling_must_be_a_non_negative_integer(self):
        for kwargs in ({"max_requests": -1}, {"max_tokens": "many"}, {"max_requests": True}):
            with self.subTest(kwargs=kwargs):
                self.assertRaises(jev.PackError, jev.Budget, **kwargs)


class _Fixed(object):
    """A client that answers with one recorded body, or raises one recorded failure."""

    name = "replay"

    def __init__(self, body=None, failure=None):
        self.body = body
        self.failure = failure
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.body


class AskTests(unittest.TestCase):
    def setUp(self):
        self.client = jev.ReplayClient.from_file(FIXTURE)

    def result(self, name):
        entry = CASES[name]
        action = decision.Action(action_class=entry["action_class"], grade=entry["grade"])
        return jev.ask(jev.DECISION_PACK,
                       jev.decision_state(action, entry["counterparty"], entry["context"]),
                       self.client)

    def test_a_confident_answer_is_ok_and_an_abstention_or_a_hesitation_is_unknown(self):
        self.assertEqual(self.result("proceed")["status"], "ok")
        self.assertEqual(self.result("confirm")["status"], "ok")
        self.assertEqual(self.result("unknown")["status"], "unknown")
        self.assertEqual(self.result("hesitant")["status"], "unknown")

    def test_an_unparseable_response_is_an_error_and_never_a_judgment(self):
        result = self.result("malformed")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["answers"], {})
        self.assertIn("exactly the questions asked", result["error"])

    def test_every_result_names_what_was_asked_and_who_answered(self):
        for name in ("proceed", "unknown", "malformed"):
            with self.subTest(case=name):
                result = self.result(name)
                self.assertEqual(result["requested_model"], jev.DEFAULT_MODEL)
                self.assertEqual(result["pack_hash"], RECORDED["pack_hash"])
                self.assertEqual(result["request_hash"], CASES[name]["request_hash"])
                self.assertIn(result["status"], jev.STATUSES)
        self.assertEqual(self.result("proceed")["model"], RECORDED["model"])

    def test_a_transport_failure_is_unavailable_with_its_local_code(self):
        result = jev.ask(pack(), {"a": "b"}, _Fixed(failure=jev.Unavailable("timeout")))
        self.assertEqual((result["status"], result["error"]), ("unavailable", "timeout"))

    def test_an_unexpected_exception_never_reaches_the_caller(self):
        result = jev.ask(pack(), {"a": "b"}, _Fixed(failure=RuntimeError("bearer sk-live-x")))
        self.assertEqual((result["status"], result["error"]), ("unavailable", "provider_error"))
        self.assertNotIn("sk-live", json.dumps(result))

    def test_a_pack_that_cannot_be_asked_is_an_error_before_any_call(self):
        client = _Fixed(response())
        result = jev.ask({"q": {"type": "ranking", "instructions": "Order."}}, {"a": "b"},
                         client)
        self.assertEqual(result["status"], "error")
        self.assertEqual(client.calls, 0)
        self.assertIsNone(result["request_hash"])


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "decisions.jsonl"
        self.client = jev.ReplayClient.from_file(FIXTURE)

    def provider(self, client=None, variant="execute", **kwargs):
        base = decision.LocalProvider(root=str(self.root),
                                      policy_path=str(self.root / "missing.json"),
                                      variant=variant, target=str(self.ledger))
        return jev.JevProvider(base=base, client=self.client if client is None else client,
                               target=str(self.ledger), **kwargs)

    def decide(self, name, provider=None, **kwargs):
        entry = CASES[name]
        action = decision.Action(action_class=entry["action_class"], grade=entry["grade"])
        provider = provider or self.provider(**kwargs)
        return provider.decide(action, entry["counterparty"], entry["context"])

    def test_a_judgment_to_confirm_turns_an_allow_into_an_ask(self):
        answer = self.decide("confirm")
        self.assertEqual((answer.outcome, answer.autonomy_level, answer.provider),
                         ("ask", 2, "jev"))
        self.assertIn("severity severe", answer.injected_cognition["agent_message"])
        self.assertTrue(any("jev: confirm" in match
                            for match in answer.injected_cognition["rule_matches"]))

    def test_a_judgment_to_proceed_leaves_the_deterministic_decision_alone(self):
        answer = self.decide("proceed")
        self.assertEqual((answer.outcome, answer.autonomy_level), ("allow", 3))
        self.assertIsNone(answer.injected_cognition["agent_message"])

    def test_a_judgment_never_widens_a_decision_that_already_asks(self):
        answer = self.decide("proceed", variant="ask")
        self.assertEqual(answer.outcome, "ask")

    def test_every_status_but_ok_leaves_the_deterministic_decision_unchanged(self):
        for name in ("unknown", "hesitant", "malformed"):
            with self.subTest(case=name):
                entry = CASES[name]
                action = decision.Action(action_class=entry["action_class"],
                                         grade=entry["grade"])
                provider = self.provider()
                deterministic = provider.base.decide(action, entry["counterparty"])
                answer = provider.decide(action, entry["counterparty"], entry["context"])
                self.assertEqual((answer.outcome, answer.autonomy_level),
                                 (deterministic.outcome, deterministic.autonomy_level))
                self.assertEqual(answer.injected_cognition["agent_message"],
                                 deterministic.injected_cognition["agent_message"])
                self.assertTrue(any("jev: no judgment" in match
                                    for match in answer.injected_cognition["rule_matches"]))

    def test_a_provider_with_no_client_configured_calls_nothing_and_fails_open(self):
        answer = self.decide("confirm", provider=self.provider(client=jev.JevClient()))
        self.assertEqual(answer.outcome, "allow")
        self.assertIn("live_not_enabled",
                      " ".join(answer.injected_cognition["rule_matches"]))

    def test_each_call_leaves_one_event_row_naming_what_was_asked_and_no_state(self):
        self.decide("confirm")
        events = decision.read_events(str(self.ledger))
        self.assertEqual(len(events), 1)
        detail = events[0]["detail"]
        self.assertEqual(events[0]["event"], "jev")
        self.assertEqual(detail["status"], "ok")
        self.assertEqual(detail["request_hash"], CASES["confirm"]["request_hash"])
        self.assertEqual(detail["pack_hash"], RECORDED["pack_hash"])
        self.assertEqual(detail["model"], RECORDED["model"])
        self.assertNotIn("git push --force", json.dumps(events[0]))

    def test_record_and_learn_go_through_to_the_deterministic_provider(self):
        provider = self.provider()
        provider.record(decision.ActionOutcome(action_class="coding.git_push",
                                               counterparty="repo:a/main",
                                               outcome="completed"))
        provider.learn([{"action": "coding.git_push", "counterparty": "repo:a/main",
                         "approved": True, "at": "2026-09-21T18:04:05Z"}])
        events = [row["event"] for row in decision.read_events(str(self.ledger))]
        self.assertEqual(events, ["learn"])
        self.assertRaises(decision.PolicyError, provider.learn, "not a stream")

    def test_a_malformed_policy_is_still_an_error_and_not_a_judgment(self):
        (self.root / "governance.json").write_text("{not json", encoding="utf-8")
        base = decision.LocalProvider(root=str(self.root),
                                      policy_path=str(self.root / "governance.json"),
                                      variant="execute", target=str(self.ledger))
        provider = jev.JevProvider(base=base, client=self.client, target=str(self.ledger))
        with self.assertRaises(decision.PolicyError):
            provider.decide(decision.Action("coding.git_push", 3), "repo:a/main")


class RegistryTests(unittest.TestCase):
    def test_the_configuration_name_selects_the_provider_without_importing_it_first(self):
        provider = decision.select_provider({"governance": {"provider": "jev"}},
                                            root=str(REPO))
        self.assertIsInstance(provider, jev.JevProvider)
        self.assertIsInstance(provider.base, decision.LocalProvider)
        self.assertFalse(provider.client.live)

    def test_the_name_appears_in_the_message_an_unknown_provider_gets(self):
        with self.assertRaises(decision.PolicyError) as caught:
            decision.provider_class("hosted")
        self.assertIn("known providers are jev, local, none", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
