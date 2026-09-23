# SPDX-License-Identifier: MIT
"""The acceptance runner's readers, driven against recorded transcripts instead of a live client.

The runner's conclusions rest on how it reads what a client left on disk, and a qualification
round is the most expensive place to discover it read something wrong. The transcripts under
`fixtures/transcripts/` carry the client's record shapes — a routed spawn with its usage feed, a
null variant that fed nothing back, and a feed line that reports no budget — hand-authored to
those shapes with placeholder identifiers, so no session content is copied into the repository.

These are self-tests of the deterministic smoke tier: no client is launched, nothing is written
under `compatibility/evidence/`, and a green run is never native client qualification.
"""
import unittest
from pathlib import Path

from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "transcripts"
ROUTED = "00000000-0000-7000-8000-000000000001"
NULL_VARIANT = "00000000-0000-7000-8000-000000000002"
UNBUDGETED = "00000000-0000-7000-8000-000000000003"


def reader():
    """A Home whose client directory is the recorded fixture tree, with no client behind it."""
    home = home_in(FIXTURES.parent)
    home.client_dir = FIXTURES
    return home


class RoutedSessionTests(unittest.TestCase):
    def setUp(self):
        self.home = reader()

    def test_the_recorded_subagent_is_read_with_its_meta_and_its_transcript(self):
        meta, records = MODULE.spawned_subagent(self.home, ROUTED)
        self.assertEqual(meta["agentType"], "worker-a")
        self.assertTrue(records)

    def test_the_recorded_brief_carries_the_budget_sentence(self):
        _, records = MODULE.spawned_subagent(self.home, ROUTED)
        self.assertIn("Expected spend:", MODULE.brief_of(records))

    def test_the_orchestrator_transcript_reads_the_session_file_and_its_directory(self):
        text = self.home.orchestrator_text(ROUTED)
        self.assertIn("SPAWNED", text)
        self.assertIn("RESUMED", text)

    def test_the_escaped_feed_records_split_into_one_line_each(self):
        lines = MODULE.feed_lines(self.home.orchestrator_text(ROUTED))
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line.startswith("usage-feed: ") for line in lines))

    def test_the_recorded_worker_line_reports_spend_against_a_budget(self):
        lines = [line for line in MODULE.feed_lines(self.home.orchestrator_text(ROUTED))
                 if line.startswith("usage-feed: worker-a")]
        self.assertEqual(MODULE.spend_complaint(lines[-1]), "")


class NullVariantTests(unittest.TestCase):
    def setUp(self):
        self.home = reader()

    def test_a_session_that_fed_nothing_back_is_still_an_observed_transcript(self):
        text = self.home.orchestrator_text(NULL_VARIANT)
        self.assertTrue(text)
        self.assertIsNone(MODULE.assert_null_feed(text))

    def test_the_recorded_null_spawn_ran_on_no_band_worker_and_carried_no_budget(self):
        meta, records = MODULE.spawned_subagent(self.home, NULL_VARIANT)
        self.assertFalse(str(meta["agentType"]).startswith("worker-"))
        self.assertNotIn("Expected spend:", MODULE.brief_of(records))

    def test_an_unrecorded_session_is_unobserved_rather_than_an_absent_feed(self):
        self.assertEqual(self.home.orchestrator_text("00000000-0000-7000-8000-00000000ffff"), "")
        with self.assertRaises(MODULE.Unverified):
            MODULE.assert_null_feed("")


class UnbudgetedFeedTests(unittest.TestCase):
    """The defect class the case must fail on: a feed line present but measuring nothing."""

    def setUp(self):
        self.lines = MODULE.feed_lines(reader().orchestrator_text(UNBUDGETED))

    def test_a_line_with_no_figures_is_a_complaint(self):
        self.assertIn("no measured spend", MODULE.spend_complaint(self.lines[0]))

    def test_figures_with_nothing_to_measure_them_against_are_a_complaint(self):
        self.assertIn("against no budget", MODULE.spend_complaint(self.lines[-1]))

    def test_the_session_wrote_no_subagent_for_the_runner_to_read(self):
        with self.assertRaises(MODULE.Unverified):
            MODULE.spawned_subagent(reader(), UNBUDGETED)


if __name__ == "__main__":
    unittest.main()
