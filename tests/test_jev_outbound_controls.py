# SPDX-License-Identifier: MIT
"""Unit tests for the opt-in controls over a decision provider that leaves the machine.

The properties under test are that a configuration which has never heard of this provider makes
no request, that each mode does exactly what it says — `off` calls nothing, `shadow` reaches the
ledger alone, `advise` never changes an outcome, `act` may only tighten one — that the sentinel
file stops every call while it exists, and that nothing outside the configured allowlist reaches
the request body: no file path, no prompt text, no environment value, no tool output.

No test here reaches the network. Answered calls replay `tests/fixtures/jev/decisions.json`,
which `tests/fixtures/jev/record.py` writes, and the calls that must not happen are made against
a client that fails the test if it is called at all.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import isolate_home, without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision  # noqa: E402
from harness_core.decisions import controls  # noqa: E402
from harness_core.decisions import jev  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jev" / "decisions.json"
RECORDED = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = dict((entry["name"], entry) for entry in RECORDED["entries"])

# A context carrying exactly what must never travel: a path on this machine, the prose of a
# prompt, the value of an environment variable and the tail of a tool's output.
# The literals are split so the repository's own lint does not read its test data as a real
# home path or a real key; what travels to the request is the joined string all the same.
LEAKY = {"file_path": "/" + "Users/someone/repos/private/secrets.env",
         "prompt": "the user asked me to push straight to production",
         "env": "AWS_SECRET" + "_ACCESS_KEY=wJalrXUtnFEMI",
         "tool_output": "3 files changed, 218 insertions(+)"}


class _Refusing(object):
    """A client that fails the test if anything asks it for a judgment."""

    name = "refusing"

    def __call__(self, request):
        raise AssertionError("a call was made when the configuration allowed none: "
                             + json.dumps(request, sort_keys=True))


class _Capturing(object):
    """A replay client that keeps the request body it was handed."""

    name = "capturing"

    def __init__(self, inner):
        self.inner = inner
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.inner(request)


def config(**jev_block):
    return {"governance": {"provider": "jev", "jev": jev_block}}


class ConfigTests(unittest.TestCase):
    def refused(self, block):
        with self.assertRaises(decision.PolicyError) as caught:
            controls.Controls.from_config({"governance": {"jev": block}})
        return str(caught.exception)

    def test_a_configuration_that_names_nothing_leaves_every_point_off(self):
        for cfg in ({}, {"governance": {}}, {"governance": {"provider": "jev"}}):
            with self.subTest(config=cfg):
                resolved = controls.Controls.from_config(cfg)
                self.assertEqual(set(resolved.selected().values()), {"off"})
                self.assertFalse(resolved.live())
                self.assertEqual(resolved.state_fields, [])

    def test_an_unknown_mode_point_field_or_key_is_refused_rather_than_ignored(self):
        self.assertIn("off, shadow, advise, act", self.refused({"mode": "loud"}))
        self.assertIn("unknown decision point", self.refused({"modes": {"nope": "act"}}))
        self.assertIn("and nothing else", self.refused({"state_fields": ["transcript"]}))
        self.assertIn("unknown key(s) sentinal", self.refused({"sentinal": "/tmp/x"}))
        self.assertIn("must be an object", self.refused({"modes": ["grade-bash"]}))

    def test_a_timeout_or_a_ceiling_that_cannot_be_honoured_is_refused(self):
        self.assertIn("(0, 10]", self.refused({"timeout": 0}))
        self.assertIn("(0, 10]", self.refused({"timeout": 30}))
        self.assertIn("non-negative integer", self.refused({"max_requests": -1}))
        self.assertIn("non-negative integer", self.refused({"max_tokens": True}))

    def test_a_point_mode_wins_over_the_default_for_that_point_alone(self):
        resolved = controls.Controls.from_config(
            config(mode="shadow", modes={"grade-bash": "act"}))
        self.assertEqual(resolved.mode_for("grade-bash"), "act")
        self.assertEqual(resolved.mode_for("stop-gate"), "shadow")
        self.assertEqual(resolved.mode_for(None), "shadow")
        self.assertTrue(resolved.live())

    def test_the_points_a_mode_may_name_are_the_points_that_write_to_the_ledger(self):
        """A point added to the ledger and forgotten here is this failure, not a silent no-op."""
        ledger = decision._hook_module("decisions")
        self.assertIsNotNone(ledger, "the decision ledger module did not load")
        self.assertEqual(tuple(controls.POINTS), tuple(ledger.POINTS))

    def test_an_existing_configuration_keeps_working_and_selects_nothing_new(self):
        provider = decision.select_provider({"governance": {"provider": "local"}},
                                            root=str(REPO))
        self.assertIsInstance(provider, decision.LocalProvider)
        provider = decision.select_provider({}, root=str(REPO))
        self.assertIsInstance(provider, decision.NullProvider)


class OutboundTests(unittest.TestCase):
    def state(self, context, **block):
        action = decision.Action(action_class="coding.git_push", grade=3)
        return jev.decision_state(action, "repo:a/main", context,
                                  controls.Controls.from_config(config(**block)))

    def test_nothing_outside_the_allowlist_is_built_into_the_state(self):
        context = dict(LEAKY)
        context.update({"command": "git push origin main", "summary": "push the branch"})
        state = self.state(context, state_fields=["command"])
        self.assertEqual(sorted(state), sorted(list(controls.BASE_FIELDS) + ["command"]))
        body = json.dumps(state)
        for leaked in LEAKY.values():
            self.assertNotIn(leaked, body)
        self.assertNotIn("push the branch", body)

    def test_an_empty_allowlist_sends_the_action_and_no_free_text_at_all(self):
        state = self.state({"command": "git push origin main"})
        self.assertEqual(sorted(state), sorted(controls.BASE_FIELDS))

    def test_a_field_that_matches_a_known_secret_shape_is_dropped_whole(self):
        for secret in ("AKIA" + "Q" * 16, "export TOKEN=ghp_" + "a" * 24,
                       "curl -H 'Authorization: Bearer " + "b" * 30 + "'"):
            with self.subTest(secret=secret):
                state = self.state({"command": secret}, state_fields=["command"])
                self.assertNotIn("command", state)
        kept = self.state({"command": "git push origin main"}, state_fields=["command"])
        self.assertEqual(kept["command"], "git push origin main")

    def test_a_scan_that_cannot_load_sends_no_free_text_rather_than_unscanned_text(self):
        resolved = controls.Controls.from_config(config(state_fields=["command"]))
        saved = dict(decision._HOOK_MODULES)
        self.addCleanup(lambda: (decision._HOOK_MODULES.clear(),
                                 decision._HOOK_MODULES.update(saved)))
        decision._HOOK_MODULES[str(decision.ROOT) + "/rule-detectors"] = object()
        self.assertEqual(resolved.outbound({"command": "git push origin main"}), {})

    def test_a_key_no_configuration_allowed_out_refuses_the_request(self):
        resolved = controls.Controls.from_config(config(state_fields=["command"]))
        with self.assertRaises(decision.PolicyError) as caught:
            resolved.check_outbound({"action_class": "coding.git_push", "transcript": "…"})
        self.assertIn("transcript", str(caught.exception))

    def test_the_request_body_carries_no_key_outside_the_allowlist(self):
        """The whole POST body, not just the state: model, questions and every state key."""
        resolved = controls.Controls.from_config(config(state_fields=["command", "summary"]))
        context = dict(LEAKY)
        context.update({"command": "git push --force origin main", "summary": "force push"})
        action = decision.Action(action_class="coding.git_push", grade=3)
        request = jev.build_request(jev.DECISION_PACK,
                                    jev.decision_state(action, "repo:a/main", context, resolved))
        self.assertEqual(sorted(request), ["model", "questions", "state"])
        self.assertEqual(sorted(request["state"]),
                         sorted(list(controls.BASE_FIELDS) + ["command", "summary"]))
        body = jev.canonical(request).decode("ascii")
        for leaked in LEAKY.values():
            self.assertNotIn(leaked, body)
        for absent in ("file_path", "prompt", "tool_output", os.environ.get("HOME", "/nowhere")):
            self.assertNotIn(absent, body)


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "decisions.jsonl"
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        isolate_home(self.root)

    def provider(self, client=None, **block):
        base = decision.LocalProvider(root=str(self.root),
                                      policy_path=str(self.root / "missing.json"),
                                      variant="execute", target=str(self.ledger))
        block.setdefault("state_fields", ["command", "summary"])
        return jev.JevProvider(base=base, target=str(self.ledger),
                               client=client or jev.ReplayClient.from_file(FIXTURE),
                               config=config(**block))

    def decide(self, name="confirm", provider=None, point=None):
        entry = CASES[name]
        context = dict(entry["context"])
        if point:
            context["point"] = point
        action = decision.Action(action_class=entry["action_class"], grade=entry["grade"])
        return (provider or self.provider()).decide(action, entry["counterparty"], context)

    def events(self):
        return decision.read_events(str(self.ledger))

    def test_off_calls_nothing_writes_nothing_and_keeps_the_deterministic_answer(self):
        answer = self.decide(provider=self.provider(client=_Refusing()))
        self.assertEqual((answer.outcome, answer.autonomy_level), ("allow", 3))
        self.assertIn("jev: no judgment (off", " ".join(
            answer.injected_cognition["rule_matches"]))
        self.assertEqual(self.events(), [])

    def test_a_point_left_off_calls_nothing_while_another_point_acts(self):
        provider = self.provider(client=_Refusing(), modes={"grade-bash": "off"},
                                 mode="off")
        self.assertEqual(self.decide(provider=provider, point="grade-bash").outcome, "allow")
        self.assertEqual(self.events(), [])

    def test_shadow_calls_and_logs_and_reaches_neither_the_model_nor_the_user(self):
        base = self.decide(provider=self.provider(client=_Refusing()))
        answer = self.decide(provider=self.provider(mode="shadow"))
        self.assertEqual((answer.outcome, answer.autonomy_level, answer.provider),
                         ("allow", 3, "local"))
        self.assertIsNone(answer.injected_cognition["agent_message"])
        self.assertNotIn("jev", " ".join(answer.injected_cognition["rule_matches"]))
        self.assertNotEqual(base.injected_cognition["rule_matches"], ["jev"])
        rows = self.events()
        self.assertEqual([row["detail"]["status"] for row in rows], ["ok"])
        self.assertNotIn("git push --force", json.dumps(rows))

    def test_advise_says_what_it_would_have_done_and_changes_no_outcome(self):
        answer = self.decide(provider=self.provider(mode="advise"))
        matches = " ".join(answer.injected_cognition["rule_matches"])
        self.assertEqual((answer.outcome, answer.autonomy_level), ("allow", 3))
        self.assertIsNone(answer.injected_cognition["agent_message"])
        self.assertIn("jev: confirm at severity severe", matches)
        self.assertIn("advise only", matches)
        self.assertEqual(len(self.events()), 1)

    def test_act_may_tighten_the_decision_and_nothing_else_may(self):
        answer = self.decide(provider=self.provider(mode="act"))
        self.assertEqual((answer.outcome, answer.autonomy_level, answer.provider),
                         ("ask", 2, "jev"))
        self.assertIn("severity severe", answer.injected_cognition["agent_message"])

    def test_the_sentinel_file_stops_every_call_without_a_configuration_change(self):
        sentinel = self.root / ".local" / "state" / "agent-harness" / controls.SENTINEL_NAME
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("", encoding="utf-8")
        provider = self.provider(client=_Refusing(), mode="act")
        self.assertFalse(provider.controls.live())
        answer = self.decide(provider=provider)
        self.assertEqual(answer.outcome, "allow")
        self.assertEqual(self.events(), [])
        sentinel.unlink()
        # Read per decision, not at construction: removing it restores the mode in place.
        self.assertEqual(provider.controls.mode_for("grade-bash"), "act")

    def test_a_sentinel_elsewhere_is_honoured_when_a_configuration_names_one(self):
        elsewhere = self.root / "paused"
        provider = self.provider(client=_Refusing(), mode="act",
                                 sentinel=str(elsewhere))
        elsewhere.write_text("", encoding="utf-8")
        self.assertEqual(self.decide(provider=provider).outcome, "allow")

    def test_every_failure_of_the_provider_still_fails_open(self):
        class Exploding(object):
            name = "exploding"

            def __call__(self, request):
                raise RuntimeError("the transport came apart")

        answer = self.decide(provider=self.provider(client=Exploding(), mode="act"))
        self.assertEqual(answer.outcome, "allow")
        self.assertIn("the deterministic decision stands",
                      " ".join(answer.injected_cognition["rule_matches"]))
        self.assertNotIn("came apart", json.dumps(answer.as_dict()))

    def test_the_configured_allowlist_is_what_the_call_actually_sends(self):
        client = _Capturing(jev.ReplayClient.from_file(FIXTURE))
        self.decide(provider=self.provider(client=client, mode="act",
                                           state_fields=["command"]))
        self.assertEqual(len(client.requests), 1)
        self.assertEqual(sorted(client.requests[0]["state"]),
                         sorted(list(controls.BASE_FIELDS) + ["command"]))

    def test_a_budget_ceiling_from_the_configuration_bounds_the_calls(self):
        provider = self.provider(mode="act", max_requests=1)
        self.assertEqual(self.decide(provider=provider).outcome, "ask")
        self.assertEqual(self.decide(provider=provider).outcome, "allow")
        self.assertEqual([row["detail"]["error"] for row in self.events()],
                         [None, "over_budget"])

    def test_a_selected_provider_is_inert_until_a_mode_says_otherwise(self):
        off = decision.select_provider({"governance": {"provider": "jev"}}, root=str(self.root))
        self.assertFalse(off.client.live)
        on = decision.select_provider(config(mode="act"), root=str(self.root))
        self.assertTrue(on.client.live)
        self.assertEqual(on.client.timeout, controls.DEFAULT_TIMEOUT)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / ".config" / "agent-harness").mkdir(parents=True)

    def write(self, block):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps(config(**block)), encoding="utf-8")

    def run_harness(self, *args, **env):
        environment = without_harness_vars()
        environment.update({"HOME": str(self.home), "HARNESS_HOME": str(self.home)})
        environment.update(env)
        done = subprocess.run([sys.executable, str(REPO / "bin" / "harness")] + list(args),
                              capture_output=True, text=True, cwd=str(self.home),
                              env=environment)
        return done

    def test_doctor_says_the_mode_per_point_and_where_the_kill_switch_lives(self):
        self.write({"mode": "shadow", "modes": {"grade-bash": "act"},
                    "state_fields": ["command"]})
        done = self.run_harness("doctor")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("governance provider: jev", done.stdout)
        self.assertIn("grade-bash=act", done.stdout)
        self.assertIn("stop-gate=shadow", done.stdout)
        self.assertIn(controls.SENTINEL_NAME, done.stdout)
        self.assertIn("and command from the context", done.stdout)

    def test_doctor_says_whether_a_credential_is_set_and_never_what_it_is(self):
        self.write({"mode": "act"})
        done = self.run_harness("doctor", TYPESAFE_API_KEY="not-a-real-key")
        self.assertIn("TYPESAFE_API_KEY is set", done.stdout)
        self.assertNotIn("not-a-real-key", done.stdout)
        self.assertIn("none of TYPESAFE_API_KEY, JEV_API_KEY is set",
                      self.run_harness("doctor").stdout)

    def test_doctor_says_nothing_reaches_the_network_when_nothing_selects_it(self):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"governance": {"provider": "local"}}), encoding="utf-8")
        done = self.run_harness("doctor")
        self.assertIn("no provider reaches the network", done.stdout)

    def test_an_unreadable_governance_block_is_reported_rather_than_ignored(self):
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"governance": {"provider": "jev", "jev": {"mode": "loud"}}}),
            encoding="utf-8")
        done = self.run_harness("doctor")
        self.assertIn("governance.jev is unreadable", done.stdout)
        self.assertIn("nobody can honour", done.stdout)

    def test_the_command_refuses_a_mode_point_or_field_it_cannot_honour(self):
        for key, value, message in (
                ("governance.jev.mode", "loud", "off, shadow, advise, act"),
                ("governance.jev.modes.nope", "act", "unknown decision point"),
                ("governance.jev.state_fields", '["transcript"]', "and nothing else"),
                ("governance.jev.timeout", "30", "(0, 10]"),
                ("governance.provider", "hosted", "not a provider")):
            with self.subTest(key=key):
                done = self.run_harness("config", "set", key, value)
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(message, done.stderr)

    def test_a_set_value_round_trips_through_the_file_it_writes(self):
        self.assertEqual(self.run_harness("config", "set", "governance.jev.mode",
                                          "advise").returncode, 0)
        self.assertEqual(self.run_harness("config", "get",
                                          "governance.jev.mode").stdout.strip(), "advise")


if __name__ == "__main__":
    unittest.main()
