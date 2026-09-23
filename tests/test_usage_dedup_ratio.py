# SPDX-License-Identifier: MIT
"""`raw_vs_deduped`: how much the usage deduplication removed, on the row and in the report.

The totals are summed once per message id at that id's largest figure, so a transcript that
repeats one response is corrected silently and two sessions with very different tool profiles
can land on the same number. These tests hold the correction's size in view: a transcript with
nothing to remove measures 1.0, one that repeats a response measures above it, a record nothing
identified was never deduplicated and so contributes nothing to the ratio, and a row that
measured no raw figure says `unknown` rather than claiming 1.0.

Run: python3 -m unittest discover tests
"""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from isolation import without_harness_vars

from test_usage import REPO, _load, harness

telemetry = _load("dedup_ratio_telemetry", REPO / "claude" / "hooks" / "telemetry.py")
usage_log = _load("dedup_ratio_usage_log", REPO / "claude" / "hooks" / "usage-log.py")
CODEX_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
STAMPS = [time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 600 + i * 60))
          for i in range(6)]


def assistant(stamp, output, mid=None, request_id=None, model="model-a"):
    """One assistant record with a token figure worth counting. Input is 1, so the raw input
    sum is the number of records and the deduplicated one is the number of slots."""
    entry = {"type": "assistant", "sessionId": "s-1", "cwd": "", "timestamp": stamp,
             "message": {"model": model, "content": [],
                         "usage": {"input_tokens": 1, "output_tokens": output,
                                   "cache_read_input_tokens": 0,
                                   "cache_creation_input_tokens": 0}}}
    if mid:
        entry["message"]["id"] = mid
    if request_id:
        entry["requestId"] = request_id
    return entry


def write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def ratio(raw, deduped):
    """The figure the hook records, computed the way a reader would check it by hand."""
    return round(raw / float(deduped), 3)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.project = self.home / ".claude" / "projects" / "a-repo"
        self.transcript = self.project / "s-1.jsonl"

    def agent(self, entries, agent_id="aaa"):
        directory = self.project / "s-1" / "subagents"
        write(directory / ("agent-%s.jsonl" % agent_id), entries)
        (directory / ("agent-%s.meta.json" % agent_id)).write_text(
            json.dumps({"agentType": "gatherer", "spawnDepth": 1, "model": "model-a"}),
            encoding="utf-8")

    def record(self, entries):
        """The SessionEnd worker, run the way the hook runs it: a subprocess over a temp HOME."""
        write(self.transcript, entries)
        out = subprocess.run([sys.executable, str(usage_log.__file__), "--worker",
                              str(self.transcript), "s-1", ""],
                             capture_output=True, text=True,
                             env=dict(without_harness_vars(), HOME=str(self.home)), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.home / ".local/state/agent-harness/usage.jsonl"
        return [json.loads(line) for line in state.read_text().splitlines()]

    def session(self, entries):
        rows = [r for r in self.record(entries) if r["kind"] == "session"]
        self.assertEqual(len(rows), 1)
        return rows[0]


class TheRatioIsMeasured(Fixture):
    def test_a_transcript_with_nothing_to_remove_measures_one(self):
        """One line per response: the raw sum and the corrected total are the same figure."""
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 500, mid="m1"),
                            assistant(STAMPS[2], 700, mid="m2")])
        self.assertEqual((row["input"], row["output"]), (2, 1200))
        self.assertEqual(row["raw_vs_deduped"], 1.0)

    def test_a_response_written_several_times_measures_above_one(self):
        """Three lines of one streamed response, and one more of a second."""
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 90, mid="m1"),
                            assistant(STAMPS[1], 1500, mid="m1"),
                            assistant(STAMPS[1], 4000, mid="m1"),
                            assistant(STAMPS[2], 60, mid="m2")])
        self.assertEqual((row["input"], row["output"]), (2, 4060))
        # Raw: four records of 1 input each, and 90 + 1500 + 4000 + 60 output.
        self.assertEqual(row["raw_vs_deduped"], ratio(4 + 5650, 2 + 4060))
        self.assertGreater(row["raw_vs_deduped"], 1.0)

    def test_an_id_less_record_is_not_deduplicated_so_it_inflates_nothing(self):
        """#519 leaves a record nothing identified summed as written: raw and counted agree."""
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 500), assistant(STAMPS[1], 500)])
        self.assertEqual((row["idless_records"], row["output"]), (2, 1000))
        self.assertEqual(row["raw_vs_deduped"], 1.0)

    def test_the_session_figure_covers_the_subagent_files_folded_into_its_totals(self):
        """The totals include an agent's tokens, so the raw sum they are measured against does."""
        self.agent([assistant(STAMPS[3], 80, mid="a1"), assistant(STAMPS[3], 800, mid="a1")])
        rows = self.record([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 500, mid="m1")])
        session = [r for r in rows if r["kind"] == "session"][0]
        self.assertEqual(session["output"], 500 + 800)
        # Raw: three records, 500 + 80 + 800 output; counted: two slots, 500 + 800.
        self.assertEqual(session["raw_vs_deduped"], ratio(3 + 1380, 2 + 1300))

    def test_a_codex_session_says_unknown_rather_than_one(self):
        """Codex reports cumulative snapshots, so there is no per-line sum to measure against."""
        row = usage_log.scan(CODEX_FIXTURES / "session-vscode.jsonl")
        self.assertEqual(row["runtime"], "codex")
        self.assertEqual(row["raw_vs_deduped"], "unknown")


class TheHelperRefusesToGuess(unittest.TestCase):
    """`inflation` is the one place the figure is decided, so its absences are asserted here."""

    def test_no_raw_figure_is_unknown(self):
        self.assertEqual(usage_log.inflation({}, {"input": 5}), usage_log.RAW_UNKNOWN)

    def test_a_row_that_counted_no_tokens_is_unknown(self):
        self.assertEqual(usage_log.inflation({"input": 5}, {"input": 0}), usage_log.RAW_UNKNOWN)

    def test_the_default_is_never_one(self):
        self.assertNotEqual(usage_log.RAW_UNKNOWN, 1.0)


class TheReportSaysIt(unittest.TestCase):
    """`harness usage` prints the token-weighted ratio for the window as a footer figure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._restore)
        self.path = self.home / ".local" / "state" / "agent-harness" / "usage.jsonl"
        self.path.parent.mkdir(parents=True)

    def _restore(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home

    def row(self, **extra):
        base = {"kind": "session", "runtime": "claude-code", "session_id": "s-1",
                "ended": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "models": ["claude-fable-5-1"], "input": 100, "output": 900,
                "cache_read": 0, "cache_write": 0, "raw_vs_deduped": 1.5}
        base.update(extra)
        return base

    def report(self, *rows):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        args = argparse.Namespace(days=30, by="day", rules=False, rescan=False, stance=None)
        prior = os.environ.pop("HARNESS_QUIET", None)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                self.assertEqual(harness.cmd_usage(args), 0)
        finally:
            if prior is not None:
                os.environ["HARNESS_QUIET"] = prior
        return buf.getvalue()

    def test_the_footer_carries_the_measured_ratio(self):
        text = self.report(self.row())
        self.assertIn("raw_vs_deduped: raw totals were 1.50x the counted totals over 1 run(s)",
                      text)

    def test_two_runs_are_weighted_by_the_tokens_each_counted(self):
        """A long session moves the window's figure more than a short one."""
        text = self.report(self.row(raw_vs_deduped=2.0),
                           self.row(session_id="s-2", input=0, output=9000,
                                    raw_vs_deduped=1.0))
        # (2.0 * 1000 + 1.0 * 9000) / 10000.
        self.assertIn("raw_vs_deduped: raw totals were 1.10x the counted totals over 2 run(s)",
                      text)

    def test_a_row_without_the_field_is_counted_as_unknown(self):
        row = self.row(session_id="s-2")
        row.pop("raw_vs_deduped")
        text = self.report(self.row(), row)
        self.assertIn("over 1 run(s), 1 run(s) unknown", text)

    def test_a_window_that_measured_nothing_says_unknown_rather_than_one(self):
        row = self.row()
        row["raw_vs_deduped"] = "unknown"
        text = self.report(row)
        self.assertIn("raw_vs_deduped: unknown, no run in this window recorded a raw figure",
                      text)
        self.assertNotIn("1.00x", text)


class TheExportCarriesIt(unittest.TestCase):
    def test_the_attribute_travels_with_the_rows_own_value(self):
        row = {"kind": "session", "runtime": "claude-code", "session_id": "s-1",
               "ended": "2026-09-01T11:00:00.000Z", "output": 200, "raw_vs_deduped": 1.25}
        values = dict((a["key"], a["value"]) for a in telemetry.attributes(row))
        self.assertEqual(values["raw_vs_deduped"], {"doubleValue": 1.25})

    def test_an_unmeasured_row_exports_unknown_and_not_a_number(self):
        row = {"kind": "session", "runtime": "codex", "session_id": "c-1",
               "ended": "2026-09-01T11:00:00.000Z", "raw_vs_deduped": "unknown"}
        values = dict((a["key"], a["value"]) for a in telemetry.attributes(row))
        self.assertEqual(values["raw_vs_deduped"], {"stringValue": "unknown"})


if __name__ == "__main__":
    unittest.main()
