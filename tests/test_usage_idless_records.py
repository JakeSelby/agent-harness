# SPDX-License-Identifier: MIT
"""Assistant records that carry no message id: what identifies them, and what does not.

Every such record used to open a slot of its own per line, so a runtime that writes one
response several times without an id was billed for it several times. These tests hold the
rule in place: a `requestId` names the API call and deduplicates across files and against the
same call's id-bearing records, a record with neither id is not deduplicated at all, and the
row says how many records it counted that way.

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

from isolation import without_harness_vars

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
        out = subprocess.run([sys.executable, str(HOOK), "--worker", str(self.transcript), "s-1", ""],
                             capture_output=True, text=True,
                             env=dict(without_harness_vars(), HOME=str(self.home)), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.home / ".local/state/agent-harness/usage.jsonl"
        return [json.loads(line) for line in state.read_text().splitlines()]

    def session(self, entries):
        rows = [r for r in self.record(entries) if r["kind"] == "session"]
        self.assertEqual(len(rows), 1)
        return rows[0]


class RequestIdIdentifies(Fixture):
    """A `requestId` names one API call, so it deduplicates wherever the call was written."""

    def test_the_same_call_in_a_session_file_and_an_agent_file_is_one_slot(self):
        """Unscoped by file, and kept at its largest figure, as a message id would be."""
        self.agent([assistant(STAMPS[3], 4000, request_id="req-1")])
        session = [r for r in self.record([
            {"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
            assistant(STAMPS[1], 90, request_id="req-1"),
        ]) if r["kind"] == "session"][0]
        self.assertEqual(session["output"], 4000)
        self.assertEqual(session["input"], 1)
        self.assertNotIn("idless_records", session)

    def test_an_idless_record_joins_the_slot_of_the_call_that_did_carry_an_id(self):
        """The streaming lines of one response: the id-bearing one first, the id-less after."""
        row = self.session([assistant(STAMPS[1], 4000, mid="m1", request_id="req-1"),
                            assistant(STAMPS[1], 90, request_id="req-1")])
        self.assertEqual((row["output"], row["input"], row["turns"]), (4000, 1, 1))
        self.assertNotIn("idless_records", row)

    def test_it_joins_that_slot_in_either_order(self):
        """Files are not read in the order they were written, so the merge runs both ways."""
        row = self.session([assistant(STAMPS[1], 90, request_id="req-1"),
                            assistant(STAMPS[1], 4000, mid="m1", request_id="req-1")])
        self.assertEqual((row["output"], row["input"], row["turns"]), (4000, 1, 1))

    def test_two_request_ids_are_two_responses(self):
        row = self.session([assistant(STAMPS[1], 500, request_id="req-1"),
                            assistant(STAMPS[2], 700, request_id="req-2")])
        self.assertEqual((row["output"], row["turns"]), (1200, 2))


class NothingIdentifies(Fixture):
    """With neither id, the record is unknown rather than a duplicate: summed, and counted."""

    def test_two_identical_unidentified_records_are_two_and_are_counted(self):
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 500), assistant(STAMPS[1], 500)])
        self.assertEqual(row["output"], 1000)
        self.assertEqual(row["idless_records"], 2)
        self.assertEqual(row["turns"], 2)

    def test_the_session_count_includes_the_subagent_files_folded_into_its_totals(self):
        """The session's totals include an agent's tokens, so they include its unknowns too."""
        self.agent([assistant(STAMPS[3], 400), assistant(STAMPS[3], 400)])
        rows = self.record([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 500), assistant(STAMPS[1], 50, mid="m1")])
        agent = [r for r in rows if r["kind"] == "subagent"][0]
        session = [r for r in rows if r["kind"] == "session"][0]
        self.assertEqual((agent["output"], agent["idless_records"]), (800, 2))
        self.assertEqual(session["output"], 500 + 50 + 800)
        self.assertEqual(session["idless_records"], 3)


class IdentifiedRowsAreUnchanged(Fixture):
    def test_a_transcript_of_message_ids_is_the_row_it_always_was(self):
        """The repeated lines of one id are still one message at its largest figure."""
        row = self.session([{"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": STAMPS[0]},
                            assistant(STAMPS[1], 90, mid="m1"),
                            assistant(STAMPS[1], 4000, mid="m1"),
                            assistant(STAMPS[2], 60, mid="m2")])
        self.assertEqual((row["output"], row["input"], row["turns"]), (4060, 2, 2))
        self.assertNotIn("idless_records", row)


if __name__ == "__main__":
    unittest.main()
