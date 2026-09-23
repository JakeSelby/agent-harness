# SPDX-License-Identifier: MIT
"""Routing that starts again once a session has been told it can resolve the band workers.

Claude Code attaches an `agent_listing_delta` record to the transcript when the set of subagent
types it resolves changes: one with `isInitial` true at session start, and one more each time it
picks a definition up. A later record is the runtime's own statement about this session, so the
spawn hook may route on it even though the record written at session start predates the worker.
A session that reloaded nothing writes no later record and keeps the conservative gate, which is
what `docs/spikes/2026-09-22-registry-reload.md` measured.

Run: python3 -m unittest discover tests
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_session_registry import GUARD_HOOK, RegistryCase, WORKERS

REPO = Path(__file__).resolve().parent.parent
POSTURE = REPO / "claude" / "hooks" / "posture.py"


def posture():
    """The shared sibling the hooks load, loaded the same way here."""
    spec = importlib.util.spec_from_file_location("posture_under_test", str(POSTURE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def listing(added, removed=(), initial=False):
    """One transcript line in the shape Claude Code writes when the listing changes."""
    return json.dumps({"type": "attachment", "isSidechain": False, "attachment": {
        "type": "agent_listing_delta", "addedTypes": list(added),
        "removedTypes": list(removed), "isInitial": initial}})


class DeltaCase(RegistryCase):
    def announce(self, *lines):
        with open(str(self.transcript), "a", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def routed(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("updatedInput", {}).get("subagent_type")


class GateTests(DeltaCase):
    """The gate is the floor: only a later listing may lift it, and only for what it names."""

    def test_a_later_delta_naming_the_worker_reroutes(self):
        self.install_workers()
        self.record("reviewer", "gatherer")
        self.announce(listing(WORKERS, initial=True), listing(["worker-b"]))
        out = self.spawn()
        self.assertEqual(self.routed(out), "worker-b")

    def test_a_session_with_no_record_at_all_routes_on_the_delta(self):
        # A record is written at session start; a session that predates the policy has none, and
        # the runtime's own statement is enough on its own.
        self.install_workers()
        self.announce(listing(["worker-b"]))
        self.assertEqual(self.routed(self.spawn()), "worker-b")

    def test_the_initial_listing_alone_leaves_the_gate_closed(self):
        # What every session writes at start, including one that never reloads: not evidence of
        # anything the record does not already hold.
        self.install_workers()
        self.record("reviewer", "gatherer")
        self.announce(listing(WORKERS, initial=True))
        out = self.spawn()
        self.assertIsNone(self.routed(out))
        self.assertIn("worker-b is installed but this session started before it was",
                      out["systemMessage"])

    def test_a_delta_that_names_another_worker_routes_nothing(self):
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-a"]))
        self.assertIsNone(self.routed(self.spawn()))

    def test_a_worker_removed_again_is_not_routed_to(self):
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-b"]), listing([], removed=["worker-b"]))
        self.assertIsNone(self.routed(self.spawn()))

    def test_a_malformed_transcript_leaves_the_gate_closed(self):
        self.install_workers()
        self.record("reviewer")
        self.announce('{"type": "attachment", "attachment": {"type": "agent_listing_delta"',
                      json.dumps({"type": "attachment", "attachment": {
                          "type": "agent_listing_delta", "addedTypes": {"worker-b": 1}}}),
                      "agent_listing_delta")
        self.assertIsNone(self.routed(self.spawn()))

    def test_a_sidechain_delta_is_not_this_session_talking(self):
        # A subagent's own records ride the same file; its listing is not the parent's.
        self.install_workers()
        self.record("reviewer")
        self.announce(json.dumps({"type": "attachment", "isSidechain": True, "attachment": {
            "type": "agent_listing_delta", "addedTypes": ["worker-b"], "isInitial": False}}))
        self.assertIsNone(self.routed(self.spawn()))

    def test_an_initial_listing_after_a_delta_replaces_it(self):
        # A session starting from a listing resolves that listing and nothing an older one added.
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-b"]), listing(["reviewer"], initial=True))
        self.assertIsNone(self.routed(self.spawn()))

    def test_routing_outlives_the_delta_falling_out_of_the_tail(self):
        # The read is bounded, so a busy session scrolls the announcement away; routing that
        # stopped there would be the same defect again, on a slower clock.
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-b"]))
        self.assertEqual(self.routed(self.spawn()), "worker-b")
        self.announce(json.dumps({"type": "user", "message": {"role": "user", "content": "x" * 300000}}))
        self.assertIsNone(posture().transcript_agents(str(self.transcript)))
        self.assertEqual(self.routed(self.spawn()), "worker-b")

    def test_a_worker_removed_again_is_forgotten_as_well(self):
        # The memory is replaced by what the tail says, never merged with it.
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-b"]))
        self.assertEqual(self.routed(self.spawn()), "worker-b")
        self.announce(listing([], removed=["worker-b"]))
        self.assertIsNone(self.routed(self.spawn()))

    def test_a_missing_transcript_leaves_the_gate_closed(self):
        self.install_workers()
        self.record("reviewer")
        self.transcript.unlink()
        self.assertIsNone(self.routed(self.spawn()))


class GuardTests(DeltaCase):
    """The pricing hook asks the same question, so a spawn is never priced by another band."""

    def prompt(self):
        return self.spawn(hook=GUARD_HOOK)["hookSpecificOutput"]["updatedInput"]["prompt"]

    def test_a_delta_prices_the_spawn_by_the_band_it_will_be_routed_to(self):
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(["worker-b"]))
        self.assertIn("about 39,000 output tokens", self.prompt())  # band B

    def test_a_session_told_nothing_is_still_priced_by_nothing(self):
        self.install_workers()
        self.record("reviewer")
        self.announce(listing(WORKERS, initial=True))
        self.assertNotIn("Expected spend", self.prompt())


class ReaderTests(unittest.TestCase):
    """`posture.transcript_agents` answers unknown rather than empty whenever it cannot tell."""

    def setUp(self):
        self.posture = posture()

    def read(self, *lines):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        self.addCleanup(lambda: Path(tmp.name).unlink())
        tmp.write("".join(line + "\n" for line in lines))
        tmp.close()
        return self.posture.transcript_agents(tmp.name)

    def test_a_later_delta_is_the_set_it_names(self):
        self.assertEqual(self.read(listing(WORKERS, initial=True), listing(["worker-b", "planner"])),
                         ["planner", "worker-b"])

    def test_deltas_accumulate_in_the_order_they_were_written(self):
        self.assertEqual(self.read(listing(["worker-a"]), listing(["worker-b"], removed=["worker-a"])),
                         ["worker-b"])

    def test_an_initial_listing_alone_is_unknown(self):
        self.assertIsNone(self.read(listing(WORKERS, initial=True)))

    def test_an_initial_listing_resets_what_earlier_deltas_added(self):
        self.assertIsNone(self.read(listing(["worker-b"]), listing(["reviewer"], initial=True)))
        self.assertEqual(self.read(listing(["worker-b"]), listing(["reviewer"], initial=True),
                                   listing(["worker-c"])), ["worker-c"])

    def test_a_record_that_is_not_an_attachment_of_this_session_is_ignored(self):
        self.assertIsNone(self.read(
            json.dumps({"type": "user", "attachment": {"type": "agent_listing_delta",
                                                       "addedTypes": ["worker-b"]}}),
            json.dumps({"type": "attachment", "isSidechain": True,
                        "attachment": {"type": "agent_listing_delta",
                                       "addedTypes": ["worker-b"]}})))

    def test_no_transcript_is_unknown(self):
        self.assertIsNone(self.posture.transcript_agents(None))
        self.assertIsNone(self.posture.transcript_agents("/nonexistent/transcript.jsonl"))

    def test_only_the_tail_is_read(self):
        # A long session's early listing falls out of the bounded read, which is unknown and
        # routes nothing; what a reload just announced is at the end of the file.
        filler = json.dumps({"type": "assistant", "message": {"role": "assistant"}})
        lines = [listing(["worker-b"])]
        while sum(len(line) + 1 for line in lines) <= self.posture.TRANSCRIPT_TAIL_BYTES:
            lines.append(filler)
        self.assertIsNone(self.read(*lines))
        self.assertEqual(self.read(*(lines + [listing(["worker-c"])])), ["worker-c"])


if __name__ == "__main__":
    unittest.main()
