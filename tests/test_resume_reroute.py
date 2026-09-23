# SPDX-License-Identifier: MIT
"""A resumed session whose record predates the band workers, through the hooks and the case.

A headless `claude -p --resume <id>` keeps the session id and raises `SessionStart` with
`source: resume`, but it is a new process: it loads its agent registry from disk and writes a
non-initial `agent_listing_delta` naming every type added since the listing already in the
transcript. The session hook narrows the record on that resume and never widens it; the spawn
hook then routes on the runtime's announcement, which is the one widening its contract allows.
The qualification case has to judge the resumed turn by that evidence, not by the resume alone.

Run: python3 -m unittest discover tests
"""
import json
import unittest

from test_agent_listing_delta import DeltaCase, listing
from test_native_acceptance import MODULE
from test_session_registry import WORKERS

BEFORE = ["Explore", "general-purpose", "Plan", "reviewer"]


class HookSequenceTests(DeltaCase):
    """The case's own sequence: start without the workers, restore them, resume, spawn."""

    def setUp(self):
        super().setUp()
        (self.home / ".config" / "agent-harness" / "config.json").write_text(
            json.dumps({"stances": {"delegation": "tiered", "cost": "frugal"}}))
        self.start()
        self.install_workers()
        self.start(source="resume")
        self.announce(listing(BEFORE, initial=True))

    def recorded(self):
        return json.loads(self.record_path().read_text())["agents"]

    def test_the_resume_leaves_the_restored_workers_out_of_the_record(self):
        self.assertFalse([name for name in self.recorded() if name.startswith("worker-")])

    def test_with_no_announcement_a_resumed_session_is_not_rerouted(self):
        self.assertIsNone(self.routed(self.spawn()))

    def test_the_resumed_process_announcing_the_workers_is_what_reroutes_it(self):
        # The delta a headless resume wrote when a definition appeared between the two turns.
        self.announce(listing(WORKERS))
        self.assertIn(self.routed(self.spawn()), WORKERS)
        self.assertFalse([name for name in self.recorded() if name.startswith("worker-")])


class ResumeVerdictTests(unittest.TestCase):
    """What the case concludes from the record, the announcement and the spawn it observed."""

    record = {"agents": ["Explore", "reviewer"], "at": 0}

    def test_a_reroute_the_runtime_announced_passes_and_says_so(self):
        clause = MODULE.resume_verdict(self.record, list(WORKERS), "worker-a", True)
        self.assertIn("only after the resumed process announced it", clause)

    def test_a_reroute_nothing_named_is_the_defect(self):
        with self.assertRaisesRegex(AssertionError, "neither its record nor the runtime"):
            MODULE.resume_verdict(self.record, None, "worker-a", True)

    def test_a_record_widened_on_resume_is_the_defect(self):
        widened = dict(self.record, agents=["worker-a"])
        with self.assertRaisesRegex(AssertionError, "widened the record"):
            MODULE.resume_verdict(widened, list(WORKERS), "worker-a", True)

    def test_no_reroute_passes(self):
        clause = MODULE.resume_verdict(self.record, None, "general-purpose", True)
        self.assertIn("was not rerouted (the runtime announced nothing)", clause)

    def test_a_spawn_that_did_not_run_fails(self):
        with self.assertRaisesRegex(AssertionError, "did not run"):
            MODULE.resume_verdict(self.record, list(WORKERS), "worker-a", False)

    def test_no_record_is_unverified_not_a_pass(self):
        with self.assertRaises(MODULE.Unverified):
            MODULE.resume_verdict(None, list(WORKERS), "worker-a", True)


if __name__ == "__main__":
    unittest.main()
