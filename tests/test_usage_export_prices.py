# SPDX-License-Identifier: MIT
"""Dollars on an exported row: one pricing path, reached from the CLI and from the hook.

The figure a dashboard reads has to be the figure `harness usage` prints, so what is asserted
here is agreement rather than arithmetic — the arithmetic has its own tests in
`test_usage_prices.py`. The other half is what an unpriced row carries, which is nothing: a zero
would say a run was free rather than that nobody knows what it cost.

Nothing here reads the real ledger, the real config or the real endpoint; every collector is a
stub on an ephemeral port. Run: python3 -m unittest discover tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from test_usage import REPO, _load, harness
from test_usage_export import HOOK, SESSION_ROW, SUBAGENT_ROW, attrs, collector, records

telemetry = _load("harness_telemetry", REPO / "claude" / "hooks" / "telemetry.py")
pricing = _load("harness_pricing", REPO / "claude" / "hooks" / "pricing.py")

STAMP = "2026-09-01T11:00:00.000Z"
# Invented rates, as in `test_usage_prices.py`: no figure here is read from a provider.
TABLE = {
    "test-model": {"input": 10.0, "output": 50.0, "cache_read": 0.25, "cache_write": 12.5,
                   "as_of": "2026-09-21", "source": "https://example.invalid/pricing"},
    "test-model-mini": {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25,
                        "as_of": "2026-08-01", "source": "https://example.invalid/pricing"},
}


def row(**extra):
    base = {"kind": "session", "runtime": "claude-code", "session_id": "s-1", "ended": STAMP,
            "models": ["test-model"], "input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    base.update(extra)
    return base


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.errors = self.root / "usage.errors.jsonl"

    def serve(self, **kwargs):
        server, seen = collector(**kwargs)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%d" % server.server_address[1], seen

    def send(self, rows, prices=TABLE, module=None, **overrides):
        """Export rows to a stub collector and return the attribute map of each record."""
        endpoint, seen = self.serve()
        config = {"export": "otlp", "endpoint": endpoint, "headers_env": "", "headers_file": "",
                  "labels": {}}
        config.update(overrides)
        sent, failed = (module or telemetry).export_rows(
            rows, config=config, env={}, version="0.12.0", prices=prices,
            errors_path=self.errors)
        self.assertEqual((sent, failed), (len(rows), 0))
        return [attrs(r) for r in records(seen[0])]


class WhatAPricedRowCarries(Fixture):
    def test_a_priced_row_carries_the_dollars_and_the_date_of_the_rates_used(self):
        values = self.send([row(output=1000000, session_id="p-1")])[0]
        self.assertEqual(values["harness.usd"], {"doubleValue": 50.0})
        self.assertEqual(values["harness.price_as_of"], {"stringValue": "2026-09-21"})

    def test_the_figure_is_the_one_the_report_prints_for_the_same_row(self):
        priced = row(output=1000000, cache_read=1000000, session_id="p-2")
        values = self.send([priced])[0]
        self.assertAlmostEqual(values["harness.usd"]["doubleValue"],
                               harness.row_cost(priced, TABLE))

    def test_a_session_is_priced_with_its_subagent_so_the_two_are_never_summed(self):
        parent = row(output=1000000, cache_read=1000000, session_id="j-1")
        child = {"kind": "subagent", "runtime": "claude-code", "session_id": "j-1",
                 "agent_id": "a-1", "ended": STAMP, "model": "test-model-mini",
                 "input": 0, "output": 400000, "cache_read": 1000000, "cache_write": 0}
        values = {a["session_id"]["stringValue"] + a.get("agent_id", {}).get("stringValue", ""): a
                  for a in self.send([parent, child])}
        joined = harness.row_cost(parent, TABLE, [child])
        self.assertAlmostEqual(values["j-1"]["harness.usd"]["doubleValue"], joined)
        self.assertAlmostEqual(values["j-1a-1"]["harness.usd"]["doubleValue"],
                               harness.row_cost(child, TABLE))
        # The parent's figure already contains the child's; the date is the older of the two.
        self.assertGreater(joined, harness.row_cost(child, TABLE))
        self.assertEqual(values["j-1"]["harness.price_as_of"], {"stringValue": "2026-09-21"})

    def test_a_codex_subagent_and_a_worker_are_priced_alone_as_the_report_prices_them(self):
        codex = row(kind="subagent", runtime="codex", agent_id="c-1", session_id="c-0",
                    model="test-model", output=1000000)
        worker = row(kind="worker", agent_type="worker-b", session_id="w-1", output=1000000)
        for values, plain in zip(self.send([codex, worker]), (codex, worker)):
            self.assertAlmostEqual(values["harness.usd"]["doubleValue"],
                                   harness.row_cost(plain, TABLE))

    def test_a_row_priced_model_by_model_carries_one_figure_for_the_whole_row(self):
        mixed = row(session_id="m-1", models=["test-model", "test-model-mini"],
                    input=2000000, output=2000000, cache_read=0, cache_write=0,
                    by_model={"test-model": {"input": 1000000, "output": 1000000,
                                             "cache_read": 0, "cache_write": 0},
                              "test-model-mini": {"input": 1000000, "output": 1000000,
                                                  "cache_read": 0, "cache_write": 0}})
        values = self.send([mixed])[0]
        self.assertAlmostEqual(values["harness.usd"]["doubleValue"], 66.0)
        self.assertAlmostEqual(values["harness.usd"]["doubleValue"],
                               harness.row_cost(mixed, TABLE))
        # Two entries priced it, and the figure is stamped with the newer of their dates.
        self.assertEqual(values["harness.price_as_of"], {"stringValue": "2026-09-21"})


class WhatAnUnpricedRowCarries(Fixture):
    def test_an_unknown_model_carries_neither_attribute_and_never_a_zero(self):
        values = self.send([row(models=["mystery-model"], output=10, session_id="u-1")])[0]
        for absent in ("harness.usd", "harness.price_as_of"):
            self.assertNotIn(absent, values)
        self.assertEqual(values["output"], {"intValue": "10"})

    def test_a_partial_row_is_unpriced_even_though_its_model_is_listed(self):
        values = self.send([row(output=1000000, partial=True, session_id="u-2")])[0]
        self.assertNotIn("harness.usd", values)

    def test_an_empty_table_leaves_every_row_unpriced_and_still_exported(self):
        values = self.send([row(output=1000000, session_id="u-3")], prices={})[0]
        self.assertNotIn("harness.usd", values)
        self.assertEqual(values["harness.row_key"], {"stringValue": "u-3|claude-code|session|"})


class TheStanceAttributes(Fixture):
    def test_a_stance_is_exported_once_and_the_body_carries_no_second_copy(self):
        values = self.send([dict(SESSION_ROW, stances={"testing": "required"})])[0]
        self.assertEqual(values["harness.testing"], {"stringValue": "required"})
        self.assertEqual([k for k in values if k.endswith("testing")], ["harness.testing"])
        self.assertEqual([k for k in values if k.startswith("stances")], [])
        body = json.loads(records(  # the body a backend would flatten into dotted keys
            self.serve_once([dict(SESSION_ROW, stances={"testing": "required"})]))[0]
            ["body"]["stringValue"])
        self.assertNotIn("stances", body)
        self.assertEqual(body["session_id"], SESSION_ROW["session_id"])

    def serve_once(self, rows):
        endpoint, seen = self.serve()
        telemetry.export_rows(rows, config={"export": "otlp", "endpoint": endpoint,
                                            "headers_env": "", "headers_file": "", "labels": {}},
                              env={}, version="0.12.0", prices=TABLE, errors_path=self.errors)
        return seen[0]

    def test_a_row_with_no_recorded_stances_exports_none(self):
        values = self.send([SUBAGENT_ROW])[0]
        self.assertEqual([k for k in values if k.startswith("harness.")
                          and k not in ("harness.row_key", "harness.exported_at",
                                        "harness.version", "harness.usd",
                                        "harness.price_as_of")], [])

    def test_no_other_attribute_was_dropped_with_the_stance_map(self):
        values = self.send([SESSION_ROW])[0]
        for kept in ("kind", "runtime", "session_id", "repo", "branch", "input", "output",
                     "turns", "rerouted", "harness.row_key", "harness.version"):
            self.assertIn(kept, values)


class FromTheHookPath(Fixture):
    """The layout the live hook runs in: `hooks/harness -> claude/hooks -> ../policy/hooks`.

    `lib/harness_core` does not resolve from there, so the price file and the `prices` override
    have to be found from the module's own real path and from `HARNESS_HOME`. This builds the
    same two symlinks in a temp tree and loads the exporter through them.
    """

    def checkout(self, models=None, broken=False):
        root = self.root / "checkout"
        (root / "policy" / "hooks").mkdir(parents=True)
        for name in ("telemetry.py", "pricing.py"):
            shutil.copy(str(REPO / "policy" / "hooks" / name), str(root / "policy" / "hooks" / name))
        if models is not None:
            (root / "policy" / "prices.json").write_text(
                "not json at all" if broken
                else json.dumps({"schema_version": 1, "models": models}), encoding="utf-8")
        (root / "claude").mkdir()
        os.symlink("../policy/hooks", str(root / "claude" / "hooks"))
        home = self.root / "home"
        (home / ".claude").mkdir(parents=True)
        os.symlink(str(root / "claude" / "hooks"), str(home / ".claude" / "hooks-harness"))
        return home / ".claude" / "hooks-harness", home

    def configure(self, home, block):
        path = home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(block), encoding="utf-8")

    def loaded(self, hooks):
        return _load("hook_telemetry", hooks / "telemetry.py")

    def test_the_price_file_resolves_through_both_symlinks(self):
        hooks, home = self.checkout(models=TABLE)
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            table = module.price_table()
        self.assertEqual(table["test-model"]["input"], 10.0)

    def test_a_config_override_merges_the_same_way_it_does_for_the_cli(self):
        hooks, home = self.checkout(models=TABLE)
        self.configure(home, {"prices": {"Test-Model": {"output": 99.0}}})
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            table = module.price_table()
        self.assertEqual(table["test-model"]["output"], 99.0)
        # Field by field, and normalised on both sides: the CLI's answer for the same inputs.
        self.assertEqual(table["test-model"]["input"], 10.0)
        self.assertEqual(table, harness.load_prices({"prices": {"Test-Model": {"output": 99.0}}},
                                                    hooks.resolve().parent / "prices.json"))

    def test_the_row_a_live_endpoint_receives_from_the_hook_path_carries_dollars(self):
        hooks, home = self.checkout(models=TABLE)
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            values = self.send([row(output=1000000, session_id="h-1")], prices=None,
                               module=module)[0]
        self.assertEqual(values["harness.usd"], {"doubleValue": 50.0})

    def test_a_missing_price_file_costs_the_dollars_and_nothing_else(self):
        hooks, home = self.checkout(models=None)
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            self.assertEqual(module.price_table(), {})
            values = self.send([row(output=1000000, session_id="h-2")], prices=None,
                               module=module)[0]
        self.assertNotIn("harness.usd", values)
        self.assertEqual(values["harness.row_key"], {"stringValue": "h-2|claude-code|session|"})

    def test_a_malformed_price_file_or_override_is_ignored_rather_than_raised(self):
        hooks, home = self.checkout(models=TABLE, broken=True)
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            self.assertEqual(module.price_table(), {})
            self.configure(home, {"prices": "free, obviously"})
            self.assertEqual(module.price_table(), {})
            values = self.send([row(output=1000000, session_id="h-3")], prices=None,
                               module=module)[0]
        self.assertNotIn("harness.usd", values)

    def test_the_exporter_carries_no_dollars_when_its_sibling_is_gone(self):
        hooks, home = self.checkout(models=TABLE)
        (hooks.resolve() / "pricing.py").unlink()
        module = self.loaded(hooks)
        with unittest.mock.patch.dict(os.environ, {"HARNESS_HOME": str(home)}):
            self.assertIsNone(module.pricing())
            values = self.send([row(output=1000000, session_id="h-4")], prices=None,
                               module=module)[0]
        self.assertNotIn("harness.usd", values)


class FromTheLiveWorker(Fixture):
    """The whole path: the SessionEnd worker writes the row, then exports it priced."""

    def test_a_real_model_id_reaches_the_collector_with_a_dollar_figure(self):
        endpoint, seen = self.serve()
        home = self.root / "live"
        (home / ".config" / "agent-harness").mkdir(parents=True)
        (home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"telemetry": {"export": "otlp", "endpoint": endpoint}}), encoding="utf-8")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 60))
        transcript = home / ".claude" / "projects" / "p" / "s-1.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.write_text(json.dumps(
            {"type": "assistant", "sessionId": "s-1", "cwd": "", "timestamp": stamp,
             "message": {"id": "m1", "model": "claude-fable-5-1", "content": [],
                         "usage": {"input_tokens": 1000000, "output_tokens": 0,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}}) + "\n", encoding="utf-8")
        out = subprocess.run([sys.executable, str(HOOK), "--worker", str(transcript), "s-1", ""],
                             capture_output=True, text=True,
                             env=dict(os.environ, HOME=str(home), HARNESS_HOME=str(home)),
                             timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        session = [attrs(r) for r in records(seen[0])
                   if attrs(r)["harness.row_key"]["stringValue"].endswith("|session|")][0]
        shipped = harness.load_prices({})
        self.assertAlmostEqual(session["harness.usd"]["doubleValue"],
                               shipped["claude-fable-5-1"]["input"])
        self.assertEqual(session["harness.price_as_of"],
                         {"stringValue": shipped["claude-fable-5-1"]["as_of"]})


if __name__ == "__main__":
    unittest.main()
