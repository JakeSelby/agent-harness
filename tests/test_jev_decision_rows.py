# SPDX-License-Identifier: MIT
"""Unit tests for the usage-ledger row a decision-provider call leaves behind.

The properties under test are that every call in a mode that calls writes exactly one
`kind: "decision"` row carrying the point, the mode, the status, both model ids, the hashes, the
tokens, the latency and the labels a shadow call is measured by; that a row never carries the outbound state, a prompt, a file path or an
environment value; that a call nobody could price is `partial` rather than zero; that two
identical calls stay two rows; that the rows are counted on their own report and never added to a
session's tokens; and that turning `telemetry.decisions` off stops them.

No test here reaches the network or the real ledger: every provider replays
`tests/fixtures/jev/decisions.json` and writes into a temporary home.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from isolation import isolate_home

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision  # noqa: E402
from harness_core.decisions import jev  # noqa: E402
from harness_core.decisions import ledger  # noqa: E402


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


CLI = _load("harness_cli_rows", REPO / "bin" / "harness")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "jev" / "decisions.json"
RECORDED = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = dict((entry["name"], entry) for entry in RECORDED["entries"])

# A context carrying exactly what must never reach a ledger row. The literals are split so the
# repository's own lint does not read its test data as a real home path or a real key.
LEAKY = {"file_path": "/" + "Users/someone/repos/private/secrets.env",
         "prompt": "the user asked me to push straight to production",
         "env": "AWS_SECRET" + "_ACCESS_KEY=wJalrXUtnFEMI",
         "tool_output": "3 files changed, 218 insertions(+)"}


# Every key a decision row may carry. Pinned rather than sampled: the leak test proves what is
# absent from the values, and this proves nothing new arrived in the keys.
# `schema_version` is stamped by the ledger's writer, not built by `row()`: see docs/usage.md.
EXPECTED_KEYS = ("kind", "runtime", "provider", "session_id", "agent_id", "repo", "counterparty",
                 "action_class", "point", "mode", "status", "judgment", "severity",
                 "base_outcome", "advised_outcome", "error", "requested_model", "model",
                 "pack_hash", "request_hash", "ms", "harness_version", "started", "ended",
                 "input", "output", "cache_read", "cache_write", "schema_version")


class _Failing(object):
    """A client that cannot answer: the `unavailable` path, with no usage to report."""

    name = "failing"

    def __call__(self, request):
        raise jev.Unavailable("timeout")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.decisions = self.root / "decisions.jsonl"
        self.usage = self.root / "usage.jsonl"
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        isolate_home(self.root)

    def provider(self, client=None, mode="act", **block):
        base = decision.LocalProvider(root=str(self.root),
                                      policy_path=str(self.root / "missing.json"),
                                      variant="execute", target=str(self.decisions))
        block.setdefault("state_fields", ["command", "summary"])
        block.setdefault("mode", mode)
        return jev.JevProvider(base=base, target=str(self.decisions),
                               usage_target=str(self.usage),
                               client=client or jev.ReplayClient.from_file(FIXTURE),
                               config={"governance": {"provider": "jev", "jev": block}})

    def decide(self, name="confirm", provider=None, point="grade-bash", context=None):
        entry = CASES[name]
        merged = dict(entry["context"])
        merged.update(context or {})
        if point:
            merged["point"] = point
        action = decision.Action(action_class=entry["action_class"], grade=entry["grade"])
        return (provider or self.provider()).decide(action, entry["counterparty"], merged)

    def rows(self):
        return ledger.rows(str(self.usage))


class RowTests(Base):
    def test_a_call_records_the_point_the_mode_the_models_and_what_it_cost(self):
        self.decide()
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["kind"], "decision")
        self.assertEqual((row["point"], row["mode"], row["status"]),
                         ("grade-bash", "act", "ok"))
        self.assertEqual(row["requested_model"], jev.DEFAULT_MODEL)
        self.assertEqual(row["model"], CASES["confirm"]["response"]["model"])
        self.assertEqual(row["request_hash"], CASES["confirm"]["request_hash"])
        self.assertEqual(row["pack_hash"], RECORDED["pack_hash"])
        usage = CASES["confirm"]["response"]["usage"]
        self.assertEqual((row["input"], row["output"]),
                         (usage["input_tokens"], usage["output_tokens"]))
        self.assertEqual((row["cache_read"], row["cache_write"]), (0, 0))
        self.assertIsInstance(row["ms"], float)
        self.assertNotIn("partial", row)

    def test_the_parent_session_is_on_the_row_and_never_in_the_request(self):
        client = jev.ReplayClient.from_file(FIXTURE)
        sent = []
        provider = self.provider(client=lambda request: (sent.append(request),
                                                         client(request))[1])
        self.decide(provider=provider, context={"session_id": "abc-123"})
        self.assertEqual(self.rows()[0]["session_id"], "abc-123")
        self.assertNotIn("abc-123", json.dumps(sent))

    def test_a_row_carries_none_of_the_state_no_prompt_no_path_no_environment_value(self):
        context = dict(LEAKY)
        context["summary"] = "force push the release branch"
        # A real variable in this process's environment, so the assertion is over what a row
        # could actually have picked up rather than over a literal nothing reads.
        os.environ["HARNESS_TEST_LEAK"] = "seventeen-syllable-secret"
        self.decide(context=context)
        body = json.dumps(self.rows())
        for leaked in list(LEAKY.values()) + ["seventeen-syllable-secret", str(self.root)]:
            self.assertNotIn(leaked, body)
        for absent in ("file_path", "prompt", "tool_output", "summary", "command",
                       CASES["confirm"]["context"]["command"],
                       "force push the release branch"):
            self.assertNotIn(absent, body)

    def test_the_row_holds_exactly_these_keys_and_no_field_a_caller_can_add(self):
        """The leak test is only as strong as this: a key added without a decision here is a
        field nobody vetted travelling in every row."""
        self.decide()
        self.assertEqual(sorted(self.rows()[0]), sorted(EXPECTED_KEYS))
        self.decide(provider=self.provider(client=_Failing()))
        self.assertEqual(sorted(self.rows()[1]), sorted(EXPECTED_KEYS + ("partial",)))

    def test_a_counterparty_that_is_not_a_repo_slug_is_kept_as_a_digest(self):
        path = "/" + "Users/someone/repos/private"
        self.assertEqual(ledger._counterparty("repo:agent-harness/main"),
                         "repo:agent-harness/main")
        for opaque in (path, "repo:" + path, "repo:a/" + "b" * 200, "", None):
            kept = ledger._counterparty(opaque)
            self.assertTrue(kept.startswith("sha256:"), kept)
            self.assertEqual(len(kept), len("sha256:") + 16)
        row = ledger.row("grade-bash", "act", dict(jev.blank_result(), status="ok"),
                         "coding.shell_exec", path)
        self.assertNotIn(path, json.dumps(row))
        self.assertEqual(row["repo"], row["counterparty"])

    def test_a_call_with_no_usage_is_partial_and_never_priced_at_zero(self):
        self.decide(provider=self.provider(client=_Failing()))
        row = self.rows()[0]
        self.assertEqual((row["status"], row["error"]), ("unavailable", "timeout"))
        self.assertTrue(row["partial"])
        for name in ("input", "output", "cache_read", "cache_write"):
            self.assertIsNone(row[name])

    def test_two_identical_calls_stay_two_rows(self):
        provider = self.provider()
        self.decide(provider=provider)
        self.decide(provider=provider)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["request_hash"], rows[1]["request_hash"])
        self.assertNotEqual(rows[0]["agent_id"], rows[1]["agent_id"])

    def test_shadow_writes_the_row_and_off_writes_nothing(self):
        self.decide(provider=self.provider(mode="shadow"))
        self.assertEqual([row["mode"] for row in self.rows()], ["shadow"])
        self.decide(provider=self.provider(mode="off"))
        self.assertEqual(len(self.rows()), 1)

    def test_a_shadow_row_says_what_it_judged_and_what_act_would_have_done(self):
        """A shadow call nobody can compare against the decision it did not change measures
        nothing, so the labels the decision log carries are on the priced row too."""
        self.decide(provider=self.provider(mode="shadow"))
        row = self.rows()[0]
        self.assertEqual((row["judgment"], row["severity"]), ("confirm", "severe"))
        self.assertEqual((row["base_outcome"], row["advised_outcome"]), ("allow", "ask"))
        # Labels from closed vocabularies, never the distribution behind them.
        self.assertNotIn("probabilities", json.dumps(row))

    def test_a_call_with_no_answer_leaves_every_label_null(self):
        self.decide(provider=self.provider(client=_Failing()))
        row = self.rows()[0]
        for name in ("judgment", "severity", "advised_outcome"):
            self.assertIsNone(row[name])

    def test_a_reporting_command_leaves_no_row_behind(self):
        with decision.events_suppressed():
            self.decide()
        self.assertEqual(self.rows(), [])

    def test_telemetry_off_stops_the_usage_row_with_the_decision_row(self):
        """`telemetry.decisions: false` is one switch over both ledgers, not one per file."""
        hooks = decision._ledger()
        original = hooks.enabled
        hooks.enabled = lambda cfg=None: False
        self.addCleanup(setattr, hooks, "enabled", original)
        self.decide()
        self.assertEqual(self.rows(), [])
        self.assertEqual(decision.read_events(str(self.decisions)), [])

    def test_a_ledger_that_cannot_be_written_never_changes_the_decision(self):
        self.usage.parent.joinpath("blocked").mkdir()
        provider = jev.JevProvider(
            base=decision.LocalProvider(root=str(self.root),
                                        policy_path=str(self.root / "missing.json"),
                                        variant="execute", target=str(self.decisions)),
            target=str(self.decisions), usage_target=str(self.root / "blocked"),
            client=jev.ReplayClient.from_file(FIXTURE),
            config={"governance": {"provider": "jev",
                                   "jev": {"mode": "act",
                                           "state_fields": ["command", "summary"]}}})
        answer = self.decide(provider=provider)
        self.assertEqual(answer.outcome, "ask")
        # And the write that failed is on record: a report with no rows in it has somewhere to
        # be explained, rather than reading as a provider that was never called.
        failures = self.root / "blocked.errors.jsonl"
        self.assertTrue(failures.exists())
        entry = json.loads(failures.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(entry["where"], "decision-row")
        self.assertIn("Error", entry["error"])
        # The type, never the message: a message can carry a path or a value.
        self.assertNotIn(str(self.root), json.dumps(entry))


class ShapeTests(unittest.TestCase):
    def test_a_row_is_built_from_a_fixed_list_and_nothing_a_caller_added(self):
        result = dict(jev.blank_result(), status="ok", model="m", request_hash="h",
                      usage={"input_tokens": 3, "output_tokens": 1},
                      answers={"judgment": {"prose": "never this"}})
        result["state"] = {"command": "rm -rf /"}
        row = ledger.row("stop-gate", "advise", result, "coding.shell_exec",
                         "repo:agent-harness/main", session_id="s")
        self.assertNotIn("answers", row)
        self.assertNotIn("state", row)
        self.assertNotIn("never this", json.dumps(row))
        self.assertEqual(row["repo"], "agent-harness")

    def test_an_unreported_token_count_is_unknown_rather_than_zero(self):
        result = dict(jev.blank_result(), status="ok",
                      usage={"input_tokens": "lots", "output_tokens": 1})
        self.assertTrue(ledger.row(None, "act", result, "coding.deploy", "repo:a/b")["partial"])


class ReportTests(Base):
    """The CLI over a ledger of its own: the rows report, and nothing else counts them."""

    def write(self, rows):
        state = self.root / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True, exist_ok=True)
        (state / "usage.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def run_usage(self, *args):
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env.pop("HARNESS_QUIET", None)
        out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "usage"] + list(args),
                             capture_output=True, text=True, env=env)
        return out.returncode, out.stdout + out.stderr

    def session(self, **fields):
        row = {"kind": "session", "runtime": "claude-code", "session_id": "S", "repo": "r",
               "models": ["claude-fable-5-1"], "input": 10, "output": 5, "cache_read": 0,
               "cache_write": 0, "started": self.now, "ended": self.now}
        row.update(fields)
        return row

    def subagent(self, **fields):
        row = {"kind": "subagent", "runtime": "claude-code", "session_id": "S",
               "agent_id": "sub", "agent_type": "worker-a", "repo": "r",
               "model": "claude-fable-5-1", "input": 4, "output": 2, "cache_read": 0,
               "cache_write": 0, "tool_calls": 3, "started": self.now, "ended": self.now}
        row.update(fields)
        return row

    def decision_row(self, **fields):
        row = {"kind": "decision", "runtime": "harness", "provider": "jev", "session_id": "S",
               "agent_id": "one", "repo": "r", "point": "grade-bash", "mode": "shadow",
               "status": "ok", "requested_model": "claude-fable-5-1",
               "model": "claude-fable-5-1", "ms": 40.0, "input": 1000, "output": 20,
               "cache_read": 0, "cache_write": 0, "started": self.now, "ended": self.now}
        row.update(fields)
        return row

    def setUp(self):
        Base.setUp(self)
        self.now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    def test_the_report_names_the_point_the_mode_the_statuses_and_the_latency(self):
        self.write([self.decision_row(),
                    self.decision_row(agent_id="two", status="unavailable", ms=2000.0,
                                      partial=True, input=None, output=None,
                                      cache_read=None, cache_write=None)])
        code, out = self.run_usage("--by", "provider", "--days", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("grade-bash", out)
        self.assertIn("shadow", out)
        self.assertIn("unpriced: 1 call(s)", out)
        self.assertIn("2000", out)

    def test_a_decision_row_changes_no_other_grouping_at_all(self):
        """Every report but `--by provider` must read exactly as it did before the row existed:
        a judgment's tokens are the harness's, and a session charged for them is a wrong bill."""
        groupings = (("--by", "day"), ("--by", "repo"), ("--by", "model"), ("--by", "role"),
                     ("--by", "prefix"), ("--by", "stance", "--stance", "cost"))
        self.write([self.session(), self.subagent()])
        before = {}
        for args in groupings:
            code, out = self.run_usage(*(args + ("--days", "2")))
            self.assertEqual(code, 0, out)
            before[args] = out
        self.write([self.session(), self.subagent(), self.decision_row(),
                    self.decision_row(agent_id="two", mode="act", status="unavailable",
                                      partial=True, input=None, output=None,
                                      cache_read=None, cache_write=None)])
        for args in groupings:
            code, out = self.run_usage(*(args + ("--days", "2")))
            self.assertEqual(code, 0, out)
            self.assertEqual(before[args], out, " ".join(args))

    def test_the_provider_report_counts_rows_nothing_else_does(self):
        self.write([self.session(), self.decision_row()])
        code, out = self.run_usage("--by", "provider", "--days", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("grade-bash", out)
        self.assertNotIn("(no repo)", out)

    def test_an_empty_window_says_so_rather_than_printing_an_empty_table(self):
        self.write([])
        code, out = self.run_usage("--by", "provider", "--days", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("no decision-provider calls recorded", out)


class DoctorTests(Base):
    def test_doctor_names_the_pinned_model_the_sentinel_and_the_last_call(self):
        state = self.root / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True, exist_ok=True)
        (state / "usage.jsonl").write_text(json.dumps(
            {"kind": "decision", "provider": "jev", "status": "ok", "model": "jev-other",
             "ended": "2026-09-21T00:00:00.000Z"}) + "\n", encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env.pop("HARNESS_QUIET", None)
        out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "doctor"],
                             capture_output=True, text=True, env=env, cwd=str(REPO))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        # Nothing is configured here, so `doctor` says the machine answers its own decisions
        # and names no provider detail: the quiet default is the behaviour under test.
        self.assertIn("governance provider: none", out.stdout)
        self.assertIn("no provider reaches the network", out.stdout)

    def test_the_lines_a_configured_provider_adds_name_the_model_and_the_last_call(self):
        state = self.root / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True, exist_ok=True)
        (state / "usage.jsonl").write_text(json.dumps(
            {"kind": "decision", "provider": "jev", "status": "ok", "model": "jev-other-model",
             "ended": "2026-09-21T00:00:00.000Z"}) + "\n", encoding="utf-8")
        self.assertEqual(CLI.pinned_jev_model(), jev.DEFAULT_MODEL)
        lines = CLI.governance_lines({"governance": {"provider": "jev",
                                                     "jev": {"mode": "shadow"}}})
        joined = "\n".join(lines)
        self.assertIn("jev model: " + jev.DEFAULT_MODEL, joined)
        self.assertIn("jev modes: ", joined)
        # The sentinel is named by path, and by whether it is there: a reader has to be able to
        # create it without being told where.
        self.assertIn(str(self.root / ".local" / "state" / "agent-harness" / "jev-disabled"),
                      joined)
        self.assertIn("absent; create it", joined)
        # A returned model the harness did not request is the line's whole reason to exist.
        self.assertIn("1 recorded; last ok at 2026-09-21T00:00:00.000Z returned jev-other-model",
                      joined)
        self.assertNotEqual(jev.DEFAULT_MODEL, "jev-other-model")

    def test_a_machine_that_has_never_called_says_so_rather_than_naming_a_model(self):
        joined = "\n".join(CLI.governance_lines(
            {"governance": {"provider": "jev", "jev": {"mode": "shadow"}}}))
        self.assertIn("jev calls: none recorded", joined)
        self.assertNotIn("returned", joined)

    def test_the_sentinel_being_in_place_is_said_on_the_line_that_names_it(self):
        state = self.root / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True, exist_ok=True)
        (state / "jev-disabled").write_text("", encoding="utf-8")
        joined = "\n".join(CLI.governance_lines(
            {"governance": {"provider": "jev", "jev": {"mode": "act"}}}))
        self.assertIn("present, every call is off", joined)


class ExportTests(Base):
    """A decision row reaching a collector must not read as a session's tokens or dollars."""

    def setUp(self):
        Base.setUp(self)
        self.now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        self.telemetry = _load("harness_telemetry_rows", REPO / "policy" / "hooks" / "telemetry.py")

    def row(self, **fields):
        row = {"kind": "decision", "runtime": "harness", "provider": "jev", "session_id": "S",
               "agent_id": "one", "repo": "r", "point": "grade-bash", "mode": "shadow",
               "status": "ok", "model": "claude-fable-5-1", "ms": 40.0, "input": 1000,
               "output": 20, "cache_read": 0, "cache_write": 0,
               "started": self.now, "ended": self.now}
        row.update(fields)
        return row

    def named(self, row, price=None):
        return dict((a["key"], a["value"]) for a in self.telemetry.attributes(
            row, {}, "0.0.0", price))

    def test_every_field_of_a_decision_row_travels_under_its_own_namespace(self):
        attrs = self.named(self.row(), price=(0.25, "2026-09-01"))
        for bare in ("input", "output", "ms", "status", "point", "mode", "harness.usd"):
            self.assertNotIn(bare, attrs)
        self.assertEqual(attrs["harness.decision.input"], {"intValue": "1000"})
        self.assertEqual(attrs["harness.decision.usd"], {"doubleValue": 0.25})
        self.assertEqual(attrs["harness.decision.price_as_of"], {"stringValue": "2026-09-01"})
        # The identity and the stamp stay shared: a reader de-duplicates every kind the same way.
        self.assertIn("harness.row_key", attrs)
        self.assertIn("harness.exported_at", attrs)
        self.assertTrue(attrs["harness.row_key"]["stringValue"].endswith("|decision|one"))

    def test_a_session_row_is_untouched_by_the_namespace(self):
        session = {"kind": "session", "runtime": "claude-code", "session_id": "S", "input": 7,
                   "ended": self.now}
        attrs = self.named(session, price=(1.5, "2026-09-01"))
        self.assertEqual(attrs["input"], {"intValue": "7"})
        self.assertEqual(attrs["harness.usd"], {"doubleValue": 1.5})
        self.assertNotIn("harness.decision.input", attrs)

    def test_a_dry_run_counts_the_decision_row_in_the_window(self):
        state = self.root / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True, exist_ok=True)
        (state / "usage.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (
            {"kind": "session", "runtime": "claude-code", "session_id": "S",
             "ended": self.now}, self.row())), encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = str(self.root)
        env.pop("HARNESS_QUIET", None)
        out = subprocess.run(
            [sys.executable, str(REPO / "bin" / "harness"), "usage", "export", "--dry-run",
             "--since", self.now[:10]], capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("2 row(s)", out.stdout)


if __name__ == "__main__":
    unittest.main()
