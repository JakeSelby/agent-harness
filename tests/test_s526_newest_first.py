# SPDX-License-Identifier: MIT
"""Tests for the newest-first contract on the capped Remote Control sessions read."""
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import remote_control  # noqa: E402


def page(rows):
    def opener(request, timeout=None):
        class Response(object):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"data": rows, "next_cursor": None}).encode("utf-8")
        return Response()
    return opener


def session(sid, stamp):
    return {"id": sid, "status": "active", "connection_status": "disconnected",
            "environment_id": "env_01LIVE", "title": sid, "updated_at": stamp}


# Oldest first, which is what a page in server order looked like: under `limit=50` the newest
# session — the one a host lost minutes ago — is the row the cap drops.
ASCENDING = [session("cse_01OLDEST", "2026-09-20T09:00:00Z"),
             session("cse_01MIDDLE", "2026-09-21T09:00:00Z"),
             session("cse_01NEWEST", "2026-09-22T17:49:06.555477Z")]
DESCENDING = list(reversed(ASCENDING))


class RequestTests(unittest.TestCase):
    def test_the_sessions_request_names_a_descending_sort_by_update(self):
        query = parse_qs(urlparse(remote_control.SESSIONS_URL).query)
        self.assertEqual(query["limit"], ["50"])
        self.assertEqual(query["sort"], ["updated_at"])
        self.assertEqual(query["order"], ["desc"])


class OrderTests(unittest.TestCase):
    def test_a_descending_page_is_accepted_in_the_order_it_arrived(self):
        rows = remote_control.fetch_sessions("sk-live", opener=page(DESCENDING))
        self.assertEqual([r["id"] for r in rows],
                         ["cse_01NEWEST", "cse_01MIDDLE", "cse_01OLDEST"])

    def test_a_page_in_the_wrong_order_is_refused(self):
        self.assertFalse(remote_control.descending_by_update(ASCENDING))
        self.assertIsNone(remote_control.fetch_sessions("sk-live", opener=page(ASCENDING)))

    def test_one_row_out_of_place_is_enough_to_refuse_the_page(self):
        shuffled = [DESCENDING[1], DESCENDING[0], DESCENDING[2]]
        self.assertIsNone(remote_control.fetch_sessions("sk-live", opener=page(shuffled)))

    def test_a_missing_timestamp_sorts_oldest(self):
        undated = dict(session("cse_01NONE", ""), updated_at=None)
        self.assertTrue(remote_control.descending_by_update([DESCENDING[0], undated]))
        self.assertFalse(remote_control.descending_by_update([undated, DESCENDING[0]]))
        self.assertTrue(remote_control.descending_by_update([undated]))
        self.assertTrue(remote_control.descending_by_update([]))

    def test_a_payload_that_is_not_a_page_is_still_none(self):
        self.assertIsNone(remote_control.fetch_sessions("sk-live", opener=page("not a list")))

    def test_the_lost_sessions_a_refused_page_would_have_named_are_not_reported(self):
        # The refusal has to reach the caller as "not checked", never as "none lost".
        self.assertEqual([r["id"] for r in remote_control.disconnected_sessions(
            ASCENDING, ["env_01LIVE"])], ["cse_01NEWEST", "cse_01MIDDLE", "cse_01OLDEST"])
        self.assertIsNone(remote_control.fetch_sessions("sk-live", opener=page(ASCENDING)))


if __name__ == "__main__":
    unittest.main()
