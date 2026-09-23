# SPDX-License-Identifier: MIT
"""Tests for the newest-first contract on the capped Remote Control sessions read."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402

from harness_core import remote_control  # noqa: E402

loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)


def opener_for(payload):
    """A stand-in for `urlopen` serving one payload, encoded as the real one would be."""
    def opener(request, timeout=None):
        class Response(object):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")
        return Response()
    return opener


def session(sid, stamp):
    return {"id": sid, "status": "active", "connection_status": "disconnected",
            "environment_id": "env_01LIVE", "title": sid, "last_event_at": stamp}


# Oldest first, which is what a page in some other order would look like: under the cap the
# newest session — the one a host lost minutes ago — is the row such a page drops.
ASCENDING = [session("cse_01OLDEST", "2026-09-20T09:00:00.000000Z"),
             session("cse_01MIDDLE", "2026-09-21T09:00:00.000000Z"),
             session("cse_01NEWEST", "2026-09-22T17:49:06.555477Z")]
DESCENDING = list(reversed(ASCENDING))


def page(rows, cursor=None):
    return {"data": rows, "next_cursor": cursor}


class RequestTests(unittest.TestCase):
    def test_the_request_asks_for_the_cap_and_no_sort(self):
        # `sort` and `order` are ignored by the endpoint, so naming them would claim an order
        # the request does not obtain; the answer is checked instead.
        query = parse_qs(urlparse(remote_control.SESSIONS_URL).query)
        self.assertEqual(query, {"limit": [str(remote_control.PAGE_LIMIT)]})


class OrderTests(unittest.TestCase):
    def fetch(self, payload):
        return remote_control.fetch_sessions("sk-live", opener=opener_for(payload))

    def test_a_descending_page_is_accepted_in_the_order_it_arrived(self):
        got = self.fetch(page(DESCENDING))
        self.assertTrue(got.ok)
        self.assertEqual([r["id"] for r in got.rows],
                         ["cse_01NEWEST", "cse_01MIDDLE", "cse_01OLDEST"])
        self.assertFalse(got.truncated)

    def test_a_page_in_the_wrong_order_is_refused(self):
        self.assertFalse(remote_control.descending_by_event(ASCENDING))
        got = self.fetch(page(ASCENDING))
        self.assertEqual(got.status, remote_control.SessionPage.REFUSED)
        self.assertEqual(got.rows, [])

    def test_one_row_out_of_place_is_enough_to_refuse_the_page(self):
        shuffled = [DESCENDING[1], DESCENDING[0], DESCENDING[2]]
        self.assertEqual(self.fetch(page(shuffled)).status, remote_control.SessionPage.REFUSED)

    def test_the_order_is_read_from_last_event_at_not_updated_at(self):
        # The live shape: descending by `last_event_at` while `updated_at` goes backwards.
        rows = [dict(DESCENDING[0], updated_at="2026-09-01T00:00:00Z"),
                dict(DESCENDING[1], updated_at="2026-09-30T00:00:00Z")]
        self.assertTrue(self.fetch(page(rows)).ok)

    def test_mixed_timestamp_spellings_compare_as_times(self):
        rows = [dict(DESCENDING[0], last_event_at="2026-09-22T17:49:06.555477Z"),
                dict(DESCENDING[1], last_event_at="2026-09-22T09:00:00Z"),
                dict(DESCENDING[2], last_event_at="2026-09-22T08:00:00+00:00")]
        self.assertTrue(self.fetch(page(rows)).ok)

    def test_a_page_whose_order_cannot_be_read_is_refused(self):
        undated = [{"id": "cse_01A"}, {"id": "cse_01B"}]
        self.assertFalse(remote_control.descending_by_event(undated))
        self.assertFalse(remote_control.descending_by_event(
            [DESCENDING[0], {"id": "cse_01B"}]))
        self.assertFalse(remote_control.descending_by_event(
            [DESCENDING[0], dict(DESCENDING[1], last_event_at="not a time")]))
        self.assertEqual(self.fetch(page(undated)).status, remote_control.SessionPage.REFUSED)

    def test_one_row_and_no_rows_are_in_order_by_definition(self):
        self.assertTrue(remote_control.descending_by_event([{"id": "cse_01A"}]))
        self.assertTrue(remote_control.descending_by_event([]))
        self.assertTrue(self.fetch(page([])).ok)

    def test_a_page_of_junk_rows_is_refused_whole_and_not_shrunk(self):
        self.assertEqual(self.fetch({"data": ["junk", "junk"]}).status,
                         remote_control.SessionPage.FAILED)
        self.assertEqual(self.fetch({"data": [DESCENDING[0], "junk"]}).rows, [])
        self.assertEqual(self.fetch({"data": "not a list"}).status,
                         remote_control.SessionPage.FAILED)
        self.assertIsNone(remote_control.session_rows({"data": ["junk"]}))

    def test_a_cursor_means_the_page_does_not_speak_for_the_account(self):
        got = self.fetch(page(DESCENDING, cursor="cur_01NEXT"))
        self.assertTrue(got.truncated)
        self.assertEqual(got.scope(), " in the newest %d" % remote_control.PAGE_LIMIT)
        self.assertEqual(self.fetch(page(DESCENDING)).scope(), "")


class ReportingTests(unittest.TestCase):
    """The caller's wording, because three answers here must never print as one another."""

    def report(self, payload):
        lines = []
        with mock.patch.object(remote_control, "urlopen", opener_for(payload)), \
             mock.patch.object(harness, "claude_oauth_token", lambda: "sk-live"), \
             mock.patch.object(harness, "host_environment_ids", lambda folders: ["env_01LIVE"]), \
             mock.patch.object(harness, "say", lines.append):
            found = harness.report_lost_sessions([Path("/repos/app")],
                                                 {"permission_mode": "auto"})
        return found, "\n".join(lines)

    def test_a_refused_page_does_not_read_as_an_account_with_nothing_lost(self):
        found, out = self.report(page(ASCENDING))
        self.assertEqual(found, 0)
        self.assertEqual(out, "lost sessions: not checked (page order unknown)")

    def test_a_failed_call_and_a_refused_page_read_differently(self):
        _, out = self.report({"data": "not a list"})
        self.assertIn("no claude.ai token in the keychain, or the API call failed", out)
        self.assertNotIn("page order unknown", out)

    def test_none_claims_only_the_page_when_a_cursor_follows_it(self):
        connected = [dict(row, connection_status="connected") for row in DESCENDING]
        _, out = self.report(page(connected, cursor="cur_01NEXT"))
        self.assertEqual(out, "lost sessions: none in the newest %d" % remote_control.PAGE_LIMIT)
        _, whole = self.report(page(connected))
        self.assertEqual(whole, "lost sessions: none")

    def test_a_count_over_a_truncated_page_says_which_page_it_counted(self):
        found, out = self.report(page(DESCENDING, cursor="cur_01NEXT"))
        self.assertEqual(found, 3)
        self.assertIn("3 active but disconnected in the newest %d"
                      % remote_control.PAGE_LIMIT, out)
        self.assertIn("cse_01NEWEST", out)


if __name__ == "__main__":
    unittest.main()
