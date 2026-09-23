# SPDX-License-Identifier: MIT
"""Unit tests for the decision-provider seam: the two providers, the policy file and the CLI.

The properties under test are that the default provider governs nothing, that the local
provider's resolution order is pair before default before stance with caps above all of it, and
that a policy nobody can honour is an error naming the file rather than an empty policy quietly
allowing everything. Nothing here touches the network, and nothing here asserts that a hook
consults a provider, because none does yet.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision


class Base(unittest.TestCase):
    def env(self):
        """A disposable HOME, and no inherited `HARNESS_*` to speak for the real one."""
        env = without_harness_vars()
        env.update({"HOME": str(self.root), "HARNESS_HOME": str(self.root)})
        return env

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.ledger = self.root / "decisions.jsonl"

    def policy(self, data):
        path = self.root / "governance.json"
        path.write_text(json.dumps(data) if not isinstance(data, str) else data,
                        encoding="utf-8")
        return path

    def local(self, data=None, variant="execute"):
        path = self.policy(data) if data is not None else self.root / "missing.json"
        return decision.LocalProvider(root=str(self.root), policy_path=str(path),
                                      variant=variant, target=str(self.ledger))

    def rows(self):
        text = self.ledger.read_text(encoding="utf-8") if self.ledger.exists() else ""
        return [json.loads(line) for line in text.splitlines() if line.strip()]


class NullProviderTests(Base):
    def test_every_action_and_grade_is_allowed_at_level_three(self):
        provider = decision.NullProvider(target=str(self.ledger))
        for action_class in decision.ACTION_CLASSES:
            for grade in (0, 1, 2, 3, None):
                answer = provider.decide(decision.Action(action_class, grade), "repo:a/main")
                self.assertEqual(answer.outcome, "allow")
                self.assertEqual(answer.autonomy_level, 3)
                self.assertEqual(answer.provider, "none")
                self.assertEqual(answer.reason, "governance: none")
                self.assertEqual(answer.injected_cognition,
                                 {"rule_matches": [], "agent_message": None,
                                  "user_message": None})

    def test_record_appends_one_row_to_the_shared_ledger(self):
        provider = decision.NullProvider(target=str(self.ledger))
        provider.record(decision.ActionOutcome("coding.git_push", "repo:a/main", "completed",
                                               {"remote": "origin"}))
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "decision")
        self.assertEqual(rows[0]["point"], "decision-provider")
        self.assertEqual(rows[0]["deterministic_answer"], "completed")
        payload = json.loads(rows[0]["input"])
        self.assertEqual(payload["action"], "coding.git_push")
        self.assertEqual(payload["counterparty"], "repo:a/main")
        self.assertEqual(payload["metadata"], {"remote": "origin"})

    def test_learn_is_a_no_op_that_writes_nothing(self):
        provider = decision.NullProvider(target=str(self.ledger))
        self.assertIsNone(provider.learn([{"action": "coding.git_push",
                                           "counterparty": "repo:a/main", "approved": True,
                                           "at": "2026-09-21T18:04:05Z"}]))
        self.assertEqual(self.rows(), [])

    def test_the_ledger_holds_one_file_for_both_providers(self):
        decision.NullProvider(target=str(self.ledger)).record(
            decision.ActionOutcome("coding.git_commit", "repo:a/main", "completed"))
        self.local({}).record(
            decision.ActionOutcome("coding.git_commit", "repo:a/main", "failed"))
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if p.suffix == ".jsonl"),
                         ["decisions.jsonl"])
        self.assertEqual([row["deterministic_answer"] for row in self.rows()],
                         ["completed", "failed"])


class ResolutionTests(Base):
    def test_a_pair_beats_a_class_default_which_beats_the_stance(self):
        provider = self.local({"defaults": {"coding.git_push": 2},
                               "pairs": {"repo:a/main": {"coding.git_push": 1}}},
                              variant="execute")
        pair = provider.decide(decision.Action("coding.git_push", 1), "repo:a/main")
        self.assertEqual(pair.autonomy_level, 1)
        self.assertIn("pairs.repo:a/main.coding.git_push = 1",
                      pair.injected_cognition["rule_matches"])
        default = provider.decide(decision.Action("coding.git_push", 1), "repo:b/main")
        self.assertEqual(default.autonomy_level, 2)
        self.assertIn("defaults.coding.git_push = 2",
                      default.injected_cognition["rule_matches"])
        stance = provider.decide(decision.Action("coding.file_write", 1), "repo:b/main")
        self.assertEqual(stance.autonomy_level, 3)
        self.assertIn("autonomy stance = 3", stance.injected_cognition["rule_matches"])

    def test_a_missing_policy_file_resolves_every_class_to_the_stance(self):
        for variant, level in (("execute", 3), ("confirm-writes", 2), ("ask", 1)):
            provider = self.local(variant=variant)
            answer = provider.decide(decision.Action("coding.git_push", 0), "repo:a/main")
            self.assertEqual(answer.autonomy_level, level, variant)
            self.assertEqual(answer.injected_cognition["rule_matches"],
                             ["autonomy stance = " + str(level)])

    def test_an_unresolvable_stance_is_the_strictest_level(self):
        provider = decision.LocalProvider(root=str(self.root),
                                          policy_path=str(self.root / "none.json"),
                                          variant="no-such-variant", target=str(self.ledger))
        answer = provider.decide(decision.Action("coding.file_write", 1), "repo:a/main")
        self.assertEqual(answer.autonomy_level, 1)
        self.assertEqual(answer.outcome, "ask")

    def test_a_cap_lowers_a_level_and_is_named_in_the_rule_matches(self):
        provider = self.local({"defaults": {"coding.git_push": 3},
                               "caps": {"coding.git_push": 1}})
        answer = provider.decide(decision.Action("coding.git_push", 1), "repo:a/main")
        self.assertEqual(answer.autonomy_level, 1)
        self.assertEqual(answer.outcome, "ask")
        self.assertEqual(answer.injected_cognition["rule_matches"],
                         ["defaults.coding.git_push = 3", "caps.coding.git_push = 1"])

    def test_a_cap_never_raises_a_level_a_pair_set_lower(self):
        provider = self.local({"pairs": {"repo:a/main": {"coding.git_push": 1}},
                               "caps": {"coding.git_push": 3}})
        answer = provider.decide(decision.Action("coding.git_push", 1), "repo:a/main")
        self.assertEqual(answer.autonomy_level, 1)

    def test_deploy_is_capped_at_ask_however_the_policy_reads(self):
        for data in ({}, {"defaults": {"coding.deploy": 3}},
                     {"pairs": {"repo:a/main": {"coding.deploy": 3}}},
                     {"caps": {"coding.deploy": 3}}):
            provider = self.local(data, variant="execute")
            answer = provider.decide(decision.Action("coding.deploy", 3), "repo:a/main")
            self.assertEqual(answer.autonomy_level, 2, data)
            self.assertEqual(answer.outcome, "ask", data)

    def test_a_deploy_below_the_asking_grade_still_allows(self):
        answer = self.local({}).decide(decision.Action("coding.deploy", 1), "repo:a/main")
        self.assertEqual(answer.outcome, "allow")
        self.assertEqual(answer.autonomy_level, 2)


class GradeTests(Base):
    def test_each_level_asks_at_the_grade_the_command_gate_gates(self):
        expected = {3: ["allow", "allow", "allow", "allow"],
                    2: ["allow", "allow", "ask", "ask"],
                    1: ["allow", "ask", "ask", "ask"]}
        for level, outcomes in expected.items():
            provider = self.local({"defaults": {"coding.shell_exec": level}})
            got = [provider.decide(decision.Action("coding.shell_exec", grade),
                                   "repo:a/main").outcome for grade in (0, 1, 2, 3)]
            self.assertEqual(got, outcomes, level)

    def test_an_unknown_grade_is_judged_as_one_and_says_so(self):
        provider = self.local({"defaults": {"coding.shell_exec": 1}})
        answer = provider.decide(decision.Action("coding.shell_exec"), "repo:a/main")
        self.assertEqual(answer.outcome, "ask")
        self.assertIn("grade unknown", answer.reason)

    def test_an_ask_carries_an_agent_message_and_an_allow_does_not(self):
        provider = self.local({"defaults": {"coding.git_push": 1}})
        ask = provider.decide(decision.Action("coding.git_push", 3), "repo:a/main")
        self.assertIn("wait for an explicit yes", ask.injected_cognition["agent_message"])
        self.assertIsNone(ask.injected_cognition["user_message"])
        allow = provider.decide(decision.Action("coding.git_push", 0), "repo:a/main")
        self.assertIsNone(allow.injected_cognition["agent_message"])


class PolicyErrorTests(Base):
    def malformed(self, data):
        with self.assertRaises(decision.PolicyError) as caught:
            self.local(data).decide(decision.Action("coding.git_push", 1), "repo:a/main")
        return str(caught.exception)

    def test_unreadable_json_names_the_file_and_the_fault(self):
        message = self.malformed("{not json")
        self.assertIn("governance.json", message)
        self.assertIn("cannot be read", message)

    def test_a_policy_that_is_not_an_object_is_refused(self):
        self.assertIn("must be a JSON object", self.malformed("[1, 2]"))

    def test_an_unknown_top_level_key_is_refused(self):
        message = self.malformed({"defaults": {}, "rules": {}})
        self.assertIn("unknown key(s) rules", message)

    def test_an_unknown_action_class_is_refused_rather_than_ignored(self):
        message = self.malformed({"defaults": {"coding.git_pushh": 2}})
        self.assertIn("unknown action class", message)
        self.assertIn("coding.git_push", message)

    def test_a_level_outside_one_to_three_is_refused(self):
        for value in (0, 4, "2", True, None):
            with self.subTest(value=value):
                self.assertIn("autonomy level",
                              self.malformed({"defaults": {"coding.git_push": value}}))

    def test_pairs_must_be_an_object_of_objects(self):
        self.assertIn("pairs must be an object", self.malformed({"pairs": []}))
        self.assertIn("pairs.repo:a/main", self.malformed({"pairs": {"repo:a/main": 3}}))

    def test_the_cli_prints_the_error_without_a_traceback(self):
        config = self.root / ".config" / "agent-harness"
        config.mkdir(parents=True)
        (config / "config.json").write_text(json.dumps({"governance": {"provider": "local"}}),
                                            encoding="utf-8")
        policy = self.root / ".agent-harness"
        policy.mkdir()
        (policy / "governance.json").write_text("{not json", encoding="utf-8")
        done = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "decide",
                               "--action", "coding.git_push"],
                              capture_output=True, text=True, cwd=str(self.root),
                              env=self.env())
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("cannot be read", done.stderr)


class LearnTests(Base):
    def record(self, **kwargs):
        base = {"action": "coding.git_push", "counterparty": "repo:a/main", "approved": True,
                "at": "2026-09-21T18:04:05Z"}
        base.update(kwargs)
        return base

    def test_a_well_formed_stream_writes_exactly_one_event_row(self):
        provider = self.local({})
        provider.learn([self.record(), self.record(approved=False)])
        events = decision.read_events(str(self.ledger))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "learn")
        self.assertEqual(events[0]["detail"], {"records": 2, "provider": "local"})

    def test_an_event_row_is_not_counted_as_an_unlabelled_decision(self):
        """`read_rows` skips a row with no `decision_id`, so the report never sees these."""
        self.local({}).learn([self.record()])
        module = decision._hook_module("decisions")
        self.assertEqual(module.read_rows(self.ledger), [])

    def test_a_malformed_record_is_rejected_and_writes_nothing(self):
        cases = [("not a list", "iterable"),
                 ([["pair"]], "not an object"),
                 ([self.record(action="")], "`action`"),
                 ([self.record(counterparty=None)], "`counterparty`"),
                 ([self.record(approved="yes")], "`approved`"),
                 ([self.record(at="last tuesday")], "ISO 8601")]
        for stream, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(decision.PolicyError) as caught:
                    self.local({}).learn(stream)
                self.assertIn(expected, str(caught.exception))
        self.assertEqual(decision.read_events(str(self.ledger)), [])


class RegistryTests(Base):
    def test_the_default_is_the_provider_that_governs_nothing(self):
        for config in ({}, {"governance": {}}, {"governance": {"provider": ""}},
                       {"governance": "nonsense"}):
            with self.subTest(config=config):
                self.assertIsInstance(decision.select_provider(config), decision.NullProvider)

    def test_an_explicit_name_selects_its_provider(self):
        self.assertIsInstance(decision.select_provider({"governance": {"provider": "local"}},
                                                       root=str(self.root)),
                              decision.LocalProvider)
        self.assertIsInstance(decision.select_provider({"governance": {"provider": "none"}}),
                              decision.NullProvider)

    def test_an_unknown_provider_is_refused_rather_than_defaulted(self):
        with self.assertRaises(decision.PolicyError) as caught:
            decision.select_provider({"governance": {"provider": "hosted"}})
        self.assertIn("hosted", str(caught.exception))
        self.assertIn("known providers are jev, local, none", str(caught.exception))

    def test_the_example_config_ships_the_default_the_code_assumes(self):
        example = json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(example["governance"], {"provider": "none"})

    def test_both_providers_answer_the_whole_contract(self):
        for provider in (decision.NullProvider(), decision.LocalProvider(root=str(self.root))):
            self.assertIsInstance(provider, decision.DecisionProvider)
            for name in ("decide", "record", "learn"):
                self.assertTrue(callable(getattr(provider, name)), name)


class CounterpartyTests(Base):
    def test_a_directory_outside_a_repository_is_named_unknown(self):
        self.assertEqual(decision.counterparty(str(self.root)), "repo:unknown/local")

    def test_this_checkout_resolves_to_its_repository_and_branch(self):
        slug = decision.counterparty(str(REPO))
        self.assertTrue(slug.startswith("repo:"), slug)
        self.assertEqual(len(slug.split("/", 1)), 2, slug)


class CommandTests(Base):
    def run_decide(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "decide", *args],
                              capture_output=True, text=True, cwd=cwd or str(self.root),
                              env=self.env())

    def test_the_json_shape_carries_the_action_counterparty_and_decision(self):
        done = self.run_decide("--action", "coding.git_push", "--grade", "3", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["action"], {"action_class": "coding.git_push", "grade": 3})
        self.assertEqual(data["counterparty"], "repo:unknown/local")
        self.assertEqual(sorted(data["decision"]),
                         ["autonomy_level", "injected_cognition", "outcome", "provider",
                          "reason"])
        self.assertEqual(data["decision"]["provider"], "none")
        self.assertEqual(data["decision"]["outcome"], "allow")
        self.assertEqual(sorted(data["decision"]["injected_cognition"]),
                         ["agent_message", "rule_matches", "user_message"])

    def test_an_explicit_counterparty_is_used_as_given(self):
        done = self.run_decide("--action", "coding.deploy", "--counterparty", "repo:a/main",
                               "--json")
        self.assertEqual(json.loads(done.stdout)["counterparty"], "repo:a/main")

    def test_the_text_output_says_no_hook_consults_it_yet(self):
        done = self.run_decide("--action", "coding.shell_exec", "--grade", "0")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("coding.shell_exec on repo:unknown/local: allow", done.stdout)
        self.assertIn("No hook consults this yet", done.stdout)

    def test_the_configured_local_provider_reads_this_repository_policy(self):
        config = self.root / ".config" / "agent-harness"
        config.mkdir(parents=True)
        (config / "config.json").write_text(json.dumps({"governance": {"provider": "local"}}),
                                            encoding="utf-8")
        policy = self.root / ".agent-harness"
        policy.mkdir()
        (policy / "governance.json").write_text(
            json.dumps({"pairs": {"repo:unknown/local": {"coding.git_push": 1}}}),
            encoding="utf-8")
        done = self.run_decide("--action", "coding.git_push", "--grade", "2", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)["decision"]
        self.assertEqual(data["provider"], "local")
        self.assertEqual(data["outcome"], "ask")
        self.assertEqual(data["autonomy_level"], 1)
        self.assertEqual(data["injected_cognition"]["rule_matches"],
                         ["pairs.repo:unknown/local.coding.git_push = 1"])

    def test_an_unknown_action_class_is_refused_by_the_parser(self):
        done = self.run_decide("--action", "coding.rm_rf")
        self.assertEqual(done.returncode, 2)
        self.assertNotIn("Traceback", done.stderr)


if __name__ == "__main__":
    unittest.main()
