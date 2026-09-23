# SPDX-License-Identifier: MIT
"""The per-run cache-miss ratio the replay records beside its normalised cost, on recorded CLI
output only: no test here launches an agent. Run: python3 -m unittest discover tests"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from test_harness import REPO
from test_cost_bench import Launch, TASK, options  # the runner's own fakes, not a second set

sys.path.insert(0, str(REPO / "lib"))
from harness_core import cache_prefix  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BENCH = load("cost_bench")


def result(cost=0.5):
    return {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
            "total_cost_usd": cost,
            "usage": {"input_tokens": 10, "output_tokens": 20,
                      "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40}}


def turn(thread=None, read=0, write=0, model="claude-test-20260101"):
    """An assistant message carrying the per-turn usage block the ratio is summed over."""
    return {"type": "assistant", "parent_tool_use_id": thread,
            "message": {"model": model,
                        "usage": {"cache_read_input_tokens": read,
                                  "cache_creation_input_tokens": write}}}


def row(arm, cost=1.0, miss=0.1, error=False, **extra):
    out = {"arm": arm, "rep": 1, "passed": not error, "error": error, "cost_usd": cost,
           "cost_normalised_usd": cost, "cache_miss_ratio": miss, "date": "2026-01-01",
           "harness_version": "9.9.9", "harness_sha": "a" * 40, "tag": "candidate",
           "model": "claude-test", "cli_version": "1.0", "bucket": "", "predicted_ratio": None,
           "task": "demo", "change_note": ""}
    out.update(extra)
    return out


class PerRunRatioTests(unittest.TestCase):
    def test_the_ratio_is_the_write_share_of_every_turn_the_run_opened(self):
        stream = [turn(None, read=9000, write=1000), turn("toolu_1", read=0, write=10000),
                  result()]
        parsed = BENCH.parse_result(json.dumps(stream))
        self.assertEqual(parsed["cache_miss_ratio"], 0.55)  # 11000 written of 20000 served

    def test_it_is_the_figure_the_ledger_reports_for_a_session(self):
        """One definition, imported rather than restated: a replay row and `usage --by prefix`
        that disagreed about the same arithmetic would be worse than either alone."""
        stream = [turn(None, read=7000, write=3000), result()]
        parsed = BENCH.parse_result(json.dumps(stream))
        ledger = cache_prefix.miss_ratio({"cache_read": 7000, "cache_write": 3000}, "")
        self.assertEqual(parsed["cache_miss_ratio"], round(ledger, 4))

    def test_output_with_no_per_turn_cache_figures_is_unknown_and_never_zero(self):
        self.assertIsNone(BENCH.parse_result(json.dumps([result()]))["cache_miss_ratio"])

    def test_turns_reporting_neither_reads_nor_writes_are_unknown_too(self):
        stream = [turn(None, read=0, write=0), result()]
        self.assertIsNone(BENCH.parse_result(json.dumps(stream))["cache_miss_ratio"])

    def test_a_run_that_served_its_whole_prefix_reports_zero_not_unknown(self):
        stream = [turn(None, read=5000, write=0), result()]
        self.assertEqual(BENCH.parse_result(json.dumps(stream))["cache_miss_ratio"], 0.0)

    def test_the_ratio_sits_beside_the_normalised_cost_on_every_scored_row(self):
        """Both are derived from the same stream and neither replaces the other: the normalised
        cost says what a cold prefix would have cost, the ratio says how cold it actually was."""
        stream = json.dumps([turn(None, read=9000, write=1000), result()])
        with tempfile.TemporaryDirectory() as tmp:
            rows, _ = BENCH.replay([TASK], options(tmp, reps=1), Launch([stream] * 2))
        self.assertEqual([r["arm"] for r in rows], list(BENCH.ARMS))
        for scored in rows:
            self.assertEqual(scored["cache_miss_ratio"], 0.1)
            self.assertIsNotNone(scored["cost_normalised_usd"])

    def test_an_errored_row_reports_unknown_rather_than_a_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, _ = BENCH.replay([TASK], options(tmp, reps=1), Launch(["garbage"] * 2))
        self.assertEqual([r["error"] for r in rows], [True, True])
        self.assertIsNone(rows[0]["cache_miss_ratio"])


class BackfillTests(unittest.TestCase):
    def test_a_row_written_before_the_field_existed_gets_it_from_the_raw_output(self):
        stream = json.dumps([turn(None, read=9000, write=1000), result()])
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            (raw / "demo-harness-1.json").write_text(stream, encoding="utf-8")
            old = {"task": "demo", "arm": "harness", "rep": 1}
            rows, missing = BENCH.backfill_rows([old], raw)
        self.assertEqual(missing, [])
        self.assertEqual(rows[0]["cache_miss_ratio"], 0.1)

    def test_a_row_with_no_raw_output_stays_unknown_rather_than_borrowing_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, missing = BENCH.backfill_rows([{"task": "demo", "arm": "bare", "rep": 1}],
                                                Path(tmp))
        self.assertEqual(len(missing), 1)
        self.assertIsNone(rows[0]["cache_miss_ratio"])


class HistoryTests(unittest.TestCase):
    def test_each_arm_carries_the_mean_of_the_runs_that_reported_a_figure(self):
        rows = [row("bare", miss=0.2), row("bare", miss=0.4), row("harness", miss=0.1)]
        self.assertEqual(BENCH.cache_miss(rows), {"bare": 0.3, "harness": 0.1})

    def test_an_arm_with_no_figure_is_none_and_an_errored_run_is_left_out(self):
        rows = [row("bare", miss=None), row("bare", miss=0.9, error=True),
                row("harness", miss=0.2), row("harness", miss=None)]
        self.assertEqual(BENCH.cache_miss(rows), {"bare": None, "harness": 0.2})

    def test_the_history_row_carries_it_without_changing_the_upsert_key(self):
        rows = [row("bare", cost=1.0, miss=0.5), row("harness", cost=0.5, miss=0.25)]
        made = BENCH.history_row(rows, "s1")
        self.assertEqual(made["cache_miss"], {"bare": 0.5, "harness": 0.25})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            BENCH.upsert_history(path, made)
            kept = BENCH.upsert_history(path, BENCH.history_row(rows, "s1"))
        self.assertEqual(len(kept), 1)

    def test_the_rendered_table_shows_both_arms_and_an_older_row_still_renders(self):
        rows = [row("bare", cost=1.0, miss=0.5), row("harness", cost=0.5, miss=0.25)]
        made = BENCH.history_row(rows, "s1")
        older = dict(made)
        older.pop("cache_miss")
        older["date"] = "2025-12-01"
        text = BENCH.render_history([older, made])
        self.assertIn("| Cache miss, bare | Cache miss, harness |", text)
        self.assertIn("| 0.500 | 0.250 |", text)
        self.assertIn("| n/a | n/a |", text)
        header, rule = text.splitlines()[4], text.splitlines()[5]
        self.assertEqual(header.count("|"), rule.count("|"))
        for line in text.splitlines():
            if line.startswith("| 2026-01-01"):
                self.assertEqual(line.count("|"), header.count("|"))


if __name__ == "__main__":
    unittest.main()
