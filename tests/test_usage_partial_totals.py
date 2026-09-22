# SPDX-License-Identifier: MIT
"""The partial-totals warning `harness usage` prints, and when it stays quiet.

A run whose token counts are incomplete is usually unpriced, and the report's own footer counts
it. Printing the warning above that footer states the same fact twice in two voices — one saying
figures were dropped from the totals, the other that they were counted as unpriced. So the
warning belongs only to a report that has no unpriced run to account for, which happens when the
missing count is billed at a rate of zero and the row is priced regardless.

Run: python3 -m unittest discover tests
"""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


harness = _load("harness", REPO / "bin" / "harness")

STAMP = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
WARNING = "Partial totals: unavailable metrics are excluded"

# Invented rates, none of them read from a provider. `zero-write-model` charges nothing for a
# cache write, which is what lets a row that reports no cache-write count still be priced.
TABLE = {
    "models": {
        "test-model": {"input": 10.0, "output": 50.0, "cache_read": 0.25, "cache_write": 12.5,
                       "as_of": "2026-09-21", "source": "https://example.invalid/pricing"},
        "zero-write-model": {"input": 10.0, "output": 50.0, "cache_read": 0.25,
                             "cache_write": 0.0, "as_of": "2026-09-21",
                             "source": "https://example.invalid/pricing"},
    }
}


def row(**extra):
    base = {"kind": "session", "runtime": "claude-code", "session_id": "s-1", "ended": STAMP,
            "models": ["test-model"], "input": 100, "output": 200, "cache_read": 300,
            "cache_write": 400}
    base.update(extra)
    return base


@contextlib.contextmanager
def loud():
    prior = os.environ.pop("HARNESS_QUIET", None)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield buf
    finally:
        if prior is not None:
            os.environ["HARNESS_QUIET"] = prior


class PartialTotalsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._restore)
        self.path = self.home / ".local" / "state" / "agent-harness" / "usage.jsonl"
        self.path.parent.mkdir(parents=True)
        self.prices = self.home / "prices.json"
        self.prices.write_text(json.dumps(TABLE), encoding="utf-8")

    def _restore(self):
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home

    def report(self, *rows, **kwargs):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        args = argparse.Namespace(days=kwargs.pop("days", 30), by=kwargs.pop("by", "day"),
                                  rules=False, rescan=False, stance=kwargs.pop("stance", None))
        with unittest.mock.patch.object(harness, "PRICES_PATH", self.prices):
            with loud() as out:
                self.assertEqual(harness.cmd_usage(args), 0)
        return out.getvalue()

    def test_an_unpriced_run_is_reported_by_the_footer_alone(self):
        text = self.report(row(models=["mystery-model"], cache_write=None))
        self.assertIn("unpriced: 1 run(s)", text)
        self.assertNotIn(WARNING, text)

    def test_a_report_with_nothing_unpriced_still_warns_about_the_excluded_metric(self):
        text = self.report(row(models=["zero-write-model"], cache_write=None))
        self.assertIn("unpriced: none", text)
        self.assertIn(WARNING + ": cache_write", text)

    def test_one_unpriced_run_silences_the_warning_the_rest_of_the_report_would_carry(self):
        text = self.report(row(models=["zero-write-model"], cache_write=None),
                           row(session_id="s-2", models=["mystery-model"], cache_read=None))
        self.assertIn("unpriced: 1 run(s)", text)
        self.assertNotIn(WARNING, text)

    def test_a_complete_window_carries_neither_line(self):
        text = self.report(row())
        self.assertIn("unpriced: none", text)
        self.assertNotIn(WARNING, text)


if __name__ == "__main__":
    unittest.main()
