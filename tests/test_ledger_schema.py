# SPDX-License-Identifier: MIT
"""The ledgers grow compatibly: every row names its schema version, a reader carries what it does
not know, and a renamed field is folded on read.

The usage ledger and the decision log are read by releases other than the one that wrote them.
A row from a newer writer must read without error in this one, an old row written under a field's
previous name must read under the new one, and neither may be rewritten to get there. Every row
here is synthetic, shaped like the rows the writers produce.

Run: python3 -m unittest discover tests
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


harness = _load("harness", REPO / "bin" / "harness")
usage_log = _load("usage_log_schema", REPO / "claude" / "hooks" / "usage-log.py")
decisions = _load("decisions_schema", REPO / "claude" / "hooks" / "decisions.py")

FUTURE = 99


def stamp(hours_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - hours_ago * 3600))


def session_row(session_id="s-1", **extra):
    row = {"kind": "session", "session_id": session_id, "runtime": "claude-code",
           "repo": "repo", "branch": "main", "models": ["model-a"], "started": stamp(2),
           "ended": stamp(1), "input": 10, "output": 200, "cache_read": 0, "cache_write": 0,
           "subagents": 0, "turns": 1}
    row.update(extra)
    return row


def newer(row):
    """The row a later release might write: a higher version and fields this one has never seen."""
    return dict(row, schema_version=FUTURE, future_scalar="x", future_map={"nested": [1, 2]})


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        env = patch.dict(os.environ, {"HOME": str(self.home), "HARNESS_HOME": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("HARNESS_QUIET", None)
        self.state = self.home / ".local" / "state" / "agent-harness"
        self.state.mkdir(parents=True)
        self.usage = self.state / "usage.jsonl"
        self.decisions = self.state / "decisions.jsonl"

    def write(self, target, rows):
        target.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def lines(self, target):
        return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]

    def usage_report(self, **kwargs):
        args = harness.argparse.Namespace(days=30, by=kwargs.pop("by", "day"), rules=False,
                                          rescan=False, **kwargs)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = harness.cmd_usage(args)
        self.assertEqual(rc, 0)
        return buf.getvalue()


class UsageWriterTests(Home):
    def test_an_appended_row_names_the_schema_version(self):
        usage_log.append_row({"kind": "decision", "session_id": "d-1"}, path=self.usage)
        self.assertEqual(self.lines(self.usage)[0]["schema_version"], usage_log.SCHEMA_VERSION)

    def test_an_upserted_row_names_the_schema_version_and_the_caller_keeps_its_dict(self):
        record = session_row()
        usage_log.upsert(record, path=self.usage)
        usage_log.upsert([session_row("s-2")], path=self.usage)
        self.assertNotIn("schema_version", record)
        self.assertEqual([r["schema_version"] for r in self.lines(self.usage)],
                         [usage_log.SCHEMA_VERSION] * 2)

    def test_an_upsert_leaves_every_other_row_exactly_as_it_was_written(self):
        old, future = session_row("old"), newer(session_row("future"))
        self.write(self.usage, [old, future])
        usage_log.upsert(session_row("s-3"), path=self.usage)
        kept = self.lines(self.usage)
        self.assertEqual(kept[:2], [old, future])
        self.assertNotIn("schema_version", kept[0])

    def test_an_upsert_replaces_a_row_whose_key_was_written_under_an_old_name(self):
        old = session_row()
        old["sid"] = old.pop("session_id")
        self.write(self.usage, [old])
        with patch.dict(usage_log.FIELD_FOLDS, {"sid": "session_id"}):
            usage_log.upsert(session_row(output=999), path=self.usage)
        rows = self.lines(self.usage)
        self.assertEqual([r["output"] for r in rows], [999])


class UsageReaderTests(Home):
    def test_a_newer_writers_row_reads_with_every_field_it_carries(self):
        self.write(self.usage, [newer(session_row())])
        row = usage_log.recorded(self.usage)["s-1"]
        self.assertEqual((row["schema_version"], row["future_map"]), (FUTURE, {"nested": [1, 2]}))

    def test_the_report_reads_a_newer_writers_row_without_error(self):
        self.write(self.usage, [session_row("s-old"), newer(session_row("s-new"))])
        out = self.usage_report()
        self.assertIn("400", out.replace(",", ""))

    def test_the_export_replay_counts_a_newer_writers_row(self):
        self.write(self.usage, [newer(session_row())])
        args = harness.argparse.Namespace(since=stamp(1)[:10], until=None, dry_run=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(harness.cmd_usage_export(args), 0)
        self.assertIn("1 row(s)", buf.getvalue())

    def test_a_newer_provider_row_reads_through_the_decision_ledger(self):
        from harness_core.decisions import ledger
        self.write(self.usage, [newer({"kind": ledger.KIND, "session_id": "d-1"})])
        with patch.object(ledger.decision, "_hook_module", return_value=usage_log):
            rows = ledger.rows(self.usage)
        self.assertEqual([(r["session_id"], r["future_scalar"]) for r in rows], [("d-1", "x")])

    def test_a_line_that_is_not_an_object_is_skipped_not_fatal(self):
        text = "[1, 2]\nnot json\n" + json.dumps(session_row()) + "\n"
        self.assertEqual([r["session_id"] for r in usage_log.ledger_rows(text)], ["s-1"])


class UsageFoldTests(Home):
    def test_a_renamed_field_is_read_under_its_new_name(self):
        rows = usage_log.ledger_rows(json.dumps({"finished": "t", "output": 1}),
                                     folds={"finished": "ended"})
        self.assertEqual(rows, [{"ended": "t", "output": 1}])

    def test_a_row_carrying_both_names_keeps_the_new_one(self):
        rows = usage_log.ledger_rows(json.dumps({"finished": "old", "ended": "new"}),
                                     folds={"finished": "ended"})
        self.assertEqual(rows, [{"ended": "new"}])

    def test_the_report_counts_a_row_written_under_an_old_field_name(self):
        row = session_row()
        row["finished"] = row.pop("ended")
        self.write(self.usage, [row])
        with patch.object(harness, "load_hook_module", return_value=usage_log), \
                patch.dict(usage_log.FIELD_FOLDS, {"finished": "ended"}):
            out = self.usage_report(by="model")
        self.assertIn("model-a", out)
        self.assertEqual(self.lines(self.usage), [row])

    def assert_well_formed(self, folds):
        self.assertIsInstance(folds, dict)
        for old, new in folds.items():
            self.assertNotEqual(old, new)
            self.assertNotIn(new, folds)

    def test_the_shipped_fold_maps_name_distinct_old_and_new_fields(self):
        # Both maps ship empty; this guard binds the first rename either ledger adds.
        self.assert_well_formed(usage_log.FIELD_FOLDS)
        self.assert_well_formed(decisions.FIELD_FOLDS)

    def test_the_fold_map_guard_rejects_an_identity_or_chained_rename(self):
        for bad in ({"ended": "ended"}, {"finished": "done", "done": "ended"}):
            with self.assertRaises(AssertionError):
                self.assert_well_formed(bad)


class DecisionLogTests(Home):
    def test_decision_and_outcome_rows_name_the_schema_version(self):
        identity = decisions.record("grade-bash", "ask", "git push", key="k-1",
                                    event={"session_id": "s-1"}, target=self.decisions)
        decisions.observe(identity, "ran", "grade-bash", "s-1", target=self.decisions)
        self.assertEqual([r["schema_version"] for r in self.lines(self.decisions)],
                         [decisions.SCHEMA_VERSION] * 2)

    def test_a_newer_writers_rows_are_read_and_joined(self):
        self.write(self.decisions, [
            newer({"kind": "decision", "decision_id": "d-1", "point": "grade-bash",
                   "session_id": "s-1", "ts": stamp(1)[:19] + "Z", "outcome": None,
                   "deterministic_answer": "ask"}),
            newer({"kind": "outcome", "decision_id": "d-1", "outcome": "ran"})])
        rows = decisions.joined(decisions.read_rows(self.decisions))
        self.assertEqual([(r["outcome"], r["future_scalar"]) for r in rows], [("ran", "x")])

    def test_the_decision_report_reads_a_newer_writers_row_without_error(self):
        self.write(self.decisions, [newer({
            "kind": "decision", "decision_id": "d-1", "point": "grade-bash", "session_id": "s-1",
            "ts": stamp(1)[:19] + "Z", "outcome": None, "deterministic_answer": "ask"})])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(harness.decision_report(30), 0)
        self.assertIn("grade-bash", buf.getvalue())

    def test_a_renamed_field_is_folded_on_read(self):
        self.write(self.decisions, [{"kind": "decision", "id": "d-1", "point": "grade-bash"}])
        self.assertEqual(decisions.read_rows(self.decisions), [])
        with patch.dict(decisions.FIELD_FOLDS, {"id": "decision_id"}):
            rows = decisions.read_rows(self.decisions)
        self.assertEqual(rows, [{"kind": "decision", "decision_id": "d-1", "point": "grade-bash"}])

    def test_a_row_carrying_both_names_keeps_the_new_one(self):
        self.assertEqual(decisions.fold({"id": "old", "decision_id": "new"}, {"id": "decision_id"}),
                         {"decision_id": "new"})


if __name__ == "__main__":
    unittest.main()
