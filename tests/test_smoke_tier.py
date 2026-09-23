# SPDX-License-Identifier: MIT
"""The smoke tier runs deterministic checks, bounds every one, and never reads as qualification.

No check in the tier launches a client or spends a model turn, so the tier's own contract is
what is tested here: every check carries a timeout and a check that hangs is reported as a
failure rather than waiting; a check that could not run is `unverified` and never a pass; the
tier fails if anything it ran touched `compatibility/evidence/` or the catalog; and no catalog
record names it.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO


def load():
    path = REPO / "scripts" / "smoke_tier.py"
    spec = importlib.util.spec_from_file_location("smoke_tier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load()
PLAN = MODULE.steps(Path("/tmp/does-not-need-to-exist"))


def step(argv, **extra):
    item = {"name": "fixture", "how": "a fixture check", "argv": argv, "timeout": 30}
    item.update(extra)
    return item


class PlanTests(unittest.TestCase):
    def test_listing_runs_nothing_and_names_every_check(self):
        buffer = io.StringIO()
        with patch.object(MODULE.subprocess, "run", side_effect=AssertionError("a check ran")):
            with redirect_stdout(buffer):
                self.assertEqual(MODULE.main(["--list"]), 0)
        printed = buffer.getvalue()
        for name in ("credentials", "projection-drift", "documentation-links",
                     "runner-self-tests", "disposable-home-lifecycle"):
            self.assertIn(name, printed)

    def test_the_plan_says_a_green_run_is_not_qualification(self):
        self.assertIn("not native client qualification", MODULE.NOT_QUALIFICATION)

    def test_every_check_is_bounded(self):
        for item in PLAN:
            self.assertGreater(item["timeout"], 0, item["name"])

    def test_an_unknown_check_is_refused_and_a_skipped_one_is_dropped(self):
        with self.assertRaises(SystemExit):
            MODULE.selected("no-such-check", None, PLAN)
        kept = [item["name"] for item in MODULE.selected(None, "credentials", PLAN)]
        self.assertNotIn("credentials", kept)
        self.assertEqual(len(kept), len(PLAN) - 1)


class StepTests(unittest.TestCase):
    def test_a_check_that_does_not_answer_is_failed_rather_than_waited_on(self):
        argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        result = MODULE.run_step(step(argv, timeout=1))
        self.assertEqual(result["result"], "failed")
        self.assertIn("no answer within 1s", result["detail"])

    def test_a_dirty_checkout_leaves_a_clean_tree_check_unverified_and_never_passed(self):
        with patch.object(MODULE, "dirty", return_value=" M file"):
            result = MODULE.run_step(step(["false"], clean_tree=True))
        self.assertEqual(result["result"], "unverified")

    def test_a_failing_check_reports_its_output_with_home_paths_and_secrets_removed(self):
        # Assembled here so the fixture is not itself a secret-shaped literal in source.
        secret = "sk-" + "a1b2c3d4e5f6g7h8"
        argv = [sys.executable, "-c",
                "import sys; sys.stderr.write(%r + %r); raise SystemExit(1)"
                % (os.path.expanduser("~") + "/notes ", secret)]
        result = MODULE.run_step(step(argv))
        self.assertEqual(result["result"], "failed")
        self.assertNotIn(secret, result["detail"])
        self.assertNotIn(os.path.expanduser("~"), result["detail"])


class EvidenceGuardTests(unittest.TestCase):
    """The tier is additive: it observes no client, so it may write no claim that one was observed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "compatibility" / "evidence").mkdir(parents=True)
        (self.root / "compatibility" / "catalog.json").write_text("{}\n")

    def passing(self, item, root):
        return {"name": item["name"], "result": "passed", "seconds": 0.1, "detail": ""}

    def writing(self, item, root):
        (root / "compatibility" / "evidence" / "native.json").write_text("{}\n")
        return self.passing(item, root)

    def test_a_tier_that_touched_nothing_reports_no_write(self):
        results, wrote = MODULE.tier(PLAN[:1], self.root, runner=self.passing)
        self.assertFalse(wrote)
        self.assertEqual([item["result"] for item in results], ["passed"])

    def test_a_check_that_wrote_an_evidence_record_fails_the_tier(self):
        _, wrote = MODULE.tier(PLAN[:1], self.root, runner=self.writing)
        self.assertTrue(wrote)
        self.assertIn("writes no evidence", MODULE.report([], wrote))

    def test_no_catalog_record_names_the_tier(self):
        catalog = json.loads((REPO / "compatibility" / "catalog.json").read_text())
        self.assertNotIn("smoke", json.dumps(catalog).lower())


class ReportTests(unittest.TestCase):
    def counted(self, results):
        buffer = io.StringIO()
        with patch.object(MODULE, "tier", return_value=(results, False)):
            with redirect_stdout(buffer):
                code = MODULE.main([])
        return code, buffer.getvalue()

    def test_every_check_passing_exits_zero(self):
        code, printed = self.counted([{"name": "a", "result": "passed", "seconds": 1, "detail": ""}])
        self.assertEqual(code, 0)
        self.assertIn("1 passed", printed)

    def test_an_unverified_check_is_not_a_green_tier(self):
        code, printed = self.counted([{"name": "a", "result": "unverified", "seconds": 0,
                                       "detail": "the checkout is dirty"}])
        self.assertEqual(code, 1)
        self.assertIn("1 unverified", printed)


if __name__ == "__main__":
    unittest.main()
