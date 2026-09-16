# SPDX-License-Identifier: MIT
"""Unit tests for the usage-log hook and `harness usage`. Run: python3 -m unittest discover tests"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


harness = _load("harness", REPO / "bin" / "harness")
usage_log = _load("usage_log", REPO / "claude" / "hooks" / "usage-log.py")

TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())
CFG = json.loads((REPO / "config.example.json").read_text())
STAMPS = [time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 300 + i)) for i in range(5)]


def assistant(mid, stamp, usage=None, tool=None, model="model-a"):
    message = {"id": mid, "model": model, "content": []}
    if tool:
        message["content"].append({"type": "tool_use", "id": tool, "name": "Agent", "input": {}})
    if usage is not None:
        message["usage"] = usage
    return {"type": "assistant", "sessionId": "s-1", "cwd": "", "gitBranch": "topic",
            "timestamp": stamp, "message": message}


def fixture(path):
    """Three messages, one of them split across two entries that repeat the same usage object."""
    entries = [
        {"type": "user", "sessionId": "s-1", "timestamp": STAMPS[0]},
        assistant("m1", STAMPS[1],
                  {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 800,
                   "cache_creation_input_tokens": 90}),
        assistant("m2", STAMPS[2],
                  {"input_tokens": 20, "output_tokens": 200, "cache_read_input_tokens": 1600,
                   "cache_creation_input_tokens": 180},
                  tool="tu-1"),
        assistant("m2", STAMPS[3],
                  {"input_tokens": 20, "output_tokens": 200, "cache_read_input_tokens": 1600,
                   "cache_creation_input_tokens": 180}),
        assistant("m3", STAMPS[4],
                  {"input_tokens": 30, "output_tokens": 300, "cache_read_input_tokens": 1600,
                   "cache_creation_input_tokens": 130},
                  model="model-b"),
        "not json at all",
    ]
    path.write_text("".join(
        (e if isinstance(e, str) else json.dumps(e)) + "\n" for e in entries), encoding="utf-8")
    return path


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        os.environ.pop("HARNESS_QUIET", None)
        self.transcript = fixture(self.home / "transcript.jsonl")

    def tearDown(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self.tmp.cleanup()

    def report(self, **kwargs):
        args = harness.argparse.Namespace(days=kwargs.pop("days", 30), by=kwargs.pop("by", "day"),
                                          rescan=kwargs.pop("rescan", False))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = harness.cmd_usage(args)
        self.assertEqual(rc, 0)
        return buf.getvalue()


class ScanTests(TempHome):
    def test_worker_writes_one_record_with_correct_sums(self):
        usage_log.main(["--worker", str(self.transcript), "s-1", ""])
        lines = (self.home / ".local/state/agent-harness/usage.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["session_id"], "s-1")
        self.assertEqual((rec["input"], rec["output"]), (60, 600))
        self.assertEqual((rec["cache_read"], rec["cache_write"]), (4000, 400))
        self.assertEqual(rec["turns"], 3)
        self.assertEqual(rec["subagents"], 1)
        self.assertEqual(rec["models"], ["model-a", "model-b"])
        self.assertEqual(rec["branch"], "topic")
        self.assertEqual(rec["started"], STAMPS[0])
        self.assertEqual(rec["ended"], STAMPS[4])

    def test_repeated_entries_of_one_message_are_counted_once(self):
        rec = usage_log.scan(self.transcript, "s-1", "")
        doubled = fixture(self.home / "again.jsonl")
        self.assertEqual(usage_log.scan(doubled, "s-1", "")["input"], rec["input"])

    def test_upsert_replaces_rather_than_appends(self):
        usage_log.main(["--worker", str(self.transcript), "s-1", ""])
        usage_log.main(["--worker", str(self.transcript), "s-1", ""])
        path = self.home / ".local/state/agent-harness/usage.jsonl"
        self.assertEqual(len(path.read_text().splitlines()), 1)
        usage_log.upsert(dict(json.loads(path.read_text().splitlines()[0]), session_id="s-2"))
        self.assertEqual(len(path.read_text().splitlines()), 2)

    def test_a_transcript_with_no_assistant_message_records_nothing(self):
        empty = self.home / "empty.jsonl"
        empty.write_text(json.dumps({"type": "user", "sessionId": "s-9"}) + "\n", encoding="utf-8")
        self.assertIsNone(usage_log.scan(empty))

    def test_rescan_picks_up_a_transcript_no_hook_ever_saw(self):
        project = self.home / ".claude" / "projects" / "a-repo"
        project.mkdir(parents=True)
        fixture(project / "s-1.jsonl")
        self.assertEqual(usage_log.rescan(30), 1)
        self.assertEqual(usage_log.rescan(30), 1)
        rows = (self.home / ".local/state/agent-harness/usage.jsonl").read_text().splitlines()
        self.assertEqual(len(rows), 1)

    def test_rescan_skips_transcripts_older_than_the_window(self):
        project = self.home / ".claude" / "projects" / "a-repo"
        project.mkdir(parents=True)
        old = fixture(project / "s-1.jsonl")
        stale = time.time() - 40 * 86400
        os.utime(old, (stale, stale))
        self.assertEqual(usage_log.rescan(7), 0)


class ReportTests(TempHome):
    def setUp(self):
        super().setUp()
        usage_log.main(["--worker", str(self.transcript), "s-1", ""])

    def test_totals_and_hit_rate(self):
        out = self.report()
        self.assertIn(STAMPS[4][:10], out)
        self.assertIn("TOTAL", out)
        self.assertIn("4,000", out)
        # 4000 / (60 + 4000 + 400)
        self.assertIn("90%", out)

    def test_grouping_by_repo_and_model(self):
        record = json.loads((self.home / ".local/state/agent-harness/usage.jsonl").read_text())
        usage_log.upsert(dict(record, session_id="s-2", repo="other-repo"))
        by_repo = self.report(by="repo")
        self.assertIn("other-repo", by_repo)
        self.assertIn("(no repo)", by_repo)
        self.assertIn("model-a+model-b", self.report(by="model"))

    def test_window_excludes_older_sessions(self):
        path = self.home / ".local/state/agent-harness/usage.jsonl"
        record = json.loads(path.read_text())
        path.write_text(json.dumps(dict(record, ended="2020-01-01T00:00:00.000Z")) + "\n")
        self.assertIn("no sessions recorded", self.report(days=7))

    def test_empty_state_is_not_an_error(self):
        os.remove(self.home / ".local/state/agent-harness/usage.jsonl")
        self.assertIn("no sessions recorded", self.report())


class HookEntryTests(TempHome):
    def test_malformed_stdin_exits_zero_quickly(self):
        start = time.time()
        out = subprocess.run([sys.executable, str(REPO / "claude" / "hooks" / "usage-log.py")],
                             input="not json", capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")
        self.assertLess(time.time() - start, 1.0)

    def test_registration_matches_the_ownership_contract(self):
        entries = TEMPLATE["hooks"]["SessionEnd"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertTrue(any("# harness:usage-log" in c and "usage-log.py" in c for c in commands))
        self.assertEqual(OWNERSHIP["claude"]["hook_ids"]["usage-log"],
                         {"event": "SessionEnd", "always": True})
        merged = harness.merge_claude_settings({}, TEMPLATE, CFG)
        self.assertIn("usage-log", harness.claude_projection(merged, TEMPLATE)["hooks"])
        self.assertNotIn("SessionEnd", harness.strip_claude_settings(merged, TEMPLATE).get("hooks", {}))


if __name__ == "__main__":
    unittest.main()
