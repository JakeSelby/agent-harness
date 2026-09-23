# SPDX-License-Identifier: MIT
"""Assistant records that carry no message id are deduplicated by a surrogate key.

Keyed per line, a repeated id-less usage record was billed once per line, with no bound on the
error. These tests hold the surrogate in place: a repeat collapses, two different responses do
not, and the row says how many id-less records it saw.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from isolation import without_config_dir

from test_usage import REPO

HOOK = REPO / "claude" / "hooks" / "usage-log.py"
STAMPS = [time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 600 + i * 60))
          for i in range(6)]


def assistant(stamp, output, mid=None, request_id=None, model="model-a"):
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


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self.restore)
        self.project = self.home / ".claude" / "projects" / "a-repo"
        self.transcript = self.project / "s-1.jsonl"

    def restore(self):
        if self._home is not None:
            os.environ["HOME"] = self._home

    def record(self, entries):
        write(self.transcript, entries)
        out = subprocess.run([sys.executable, str(HOOK), "--worker", str(self.transcript), "s-1", ""],
                             capture_output=True, text=True,
                             env=dict(without_config_dir(), HOME=str(self.home)), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.home / ".local/state/agent-harness/usage.jsonl"
        return [json.loads(line) for line in state.read_text().splitlines()]

    def session(self, entries):
        rows = [r for r in self.record(entries) if r["kind"] == "session"]
        self.assertEqual(len(rows), 1)
        return rows[0]


class IdlessSessionRecords(Fixture):
    def test_a_repeated_idless_record_is_counted_once_and_reported(self):
        """Three byte-identical id-less lines are one response, and the row says so."""
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]}]
                           + [assistant(STAMPS[1], 500) for _ in range(3)])
        self.assertEqual(row["output"], 500)
        self.assertEqual(row["input"], 1)
        self.assertEqual(row["idless_records"], 3)
        self.assertEqual(row["turns"], 1)

    def test_two_different_idless_responses_stay_apart(self):
        """The surrogate is a fingerprint, not a blanket: distinct usage is distinct spend."""
        row = self.session([assistant(STAMPS[1], 500), assistant(STAMPS[2], 700)])
        self.assertEqual(row["output"], 1200)
        self.assertEqual(row["idless_records"], 2)
        self.assertEqual(row["turns"], 2)

    def test_a_request_id_merges_the_streaming_lines_of_one_response(self):
        """With `requestId` present the partial streaming figures collapse onto the final one."""
        row = self.session([assistant(STAMPS[1], 90, request_id="req-1"),
                            assistant(STAMPS[2], 4000, request_id="req-1"),
                            assistant(STAMPS[2], 120, request_id="req-2")])
        self.assertEqual(row["output"], 4120)
        self.assertEqual(row["idless_records"], 3)
        self.assertEqual(row["turns"], 2)

    def test_a_row_of_identified_records_carries_no_idless_field(self):
        """A clean row is unchanged: the field is absent rather than a zero to read past."""
        row = self.session([assistant(STAMPS[1], 50, mid="m1"),
                            assistant(STAMPS[2], 60, mid="m2")])
        self.assertNotIn("idless_records", row)
        self.assertEqual((row["output"], row["turns"]), (110, 2))


class IdlessSubagentRecords(Fixture):
    def agent(self, entries, agent_id="aaa"):
        directory = self.project / "s-1" / "subagents"
        write(directory / ("agent-%s.jsonl" % agent_id), entries)
        (directory / ("agent-%s.meta.json" % agent_id)).write_text(
            json.dumps({"agentType": "gatherer", "spawnDepth": 1, "model": "model-a"}),
            encoding="utf-8")

    def test_the_agent_row_and_the_session_total_both_count_the_repeat_once(self):
        self.agent([assistant(STAMPS[3], 400) for _ in range(4)])
        rows = self.record([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 50, mid="m1")])
        agent = [r for r in rows if r["kind"] == "subagent"][0]
        session = [r for r in rows if r["kind"] == "session"][0]
        self.assertEqual(agent["output"], 400)
        self.assertEqual(agent["idless_records"], 4)
        self.assertEqual(agent["turns"], 1)
        self.assertEqual(session["output"], 450)

    def test_the_same_idless_line_in_two_files_is_still_two_messages(self):
        """A line with no id cannot be matched across files; the surrogate names its source."""
        self.agent([assistant(STAMPS[3], 400)])
        rows = self.record([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[3], 400)])
        session = [r for r in rows if r["kind"] == "session"][0]
        self.assertEqual(session["output"], 800)


if __name__ == "__main__":
    unittest.main()
