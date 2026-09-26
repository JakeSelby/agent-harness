#!/usr/bin/env python3
"""A smoke tier that does not pass stops the qualification round before any target runs (FR-52)."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO


def load_round():
    path = REPO / "scripts" / "qualification_round.py"
    spec = importlib.util.spec_from_file_location("qualification_round_smoke_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUND = load_round()
CLAUDE = "claude-code-cli-macos"
CODEX = "codex-cli-macos"
ROUTING = {"execution_class": "standard", "assessment_class": "strong"}


def done(code):
    return type("Done", (), {"returncode": code})()


class SmokeGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.round_dir = Path(self.temp.name)
        (self.round_dir / "provision.json").write_text(json.dumps(
            {"clone": str(self.round_dir / "clone"), "records": str(self.round_dir / "records"),
             "source_commit": "a" * 40}))
        self.launched = []

    def fake_run(self, argv, **kwargs):
        client = argv[argv.index("--client") + 1]
        self.launched.append(client)
        out = argv[argv.index("--out") + 1]
        Path(out).write_text(json.dumps({"cases": {"installation": "passed"}}))
        return done(0)

    def run_round(self, tier, skip_smoke=False):
        routing = {CLAUDE: ROUTING, CODEX: ROUTING}
        with patch.object(ROUND, "smoke", side_effect=lambda *a, **k: tier) as smoke, \
                patch.object(ROUND.subprocess, "run", side_effect=self.fake_run):
            result = ROUND.run_round(self.round_dir, [CLAUDE, CODEX], None, [],
                                     skip_smoke=skip_smoke, tier_routing=routing)
        return result, smoke

    def on_disk(self):
        return json.loads((self.round_dir / "round.json").read_text())

    def test_a_failed_tier_runs_no_target_and_records_why(self):
        result, _ = self.run_round(done(1))
        self.assertEqual(self.launched, [])
        self.assertEqual(result["smoke"], "failed")
        self.assertEqual(result["targets"], {})
        self.assertEqual(result["not_run"], [CLAUDE, CODEX])
        self.assertIn("smoke tier failed", result["stopped"])
        self.assertEqual(self.on_disk()["stopped"], result["stopped"])

    def test_a_timed_out_tier_also_runs_no_target(self):
        result, _ = self.run_round(None)
        self.assertEqual(self.launched, [])
        self.assertEqual(result["smoke"], "timed out")
        self.assertIn("timed out", result["stopped"])

    def test_a_passing_tier_still_runs_every_target(self):
        result, smoke = self.run_round(done(0))
        self.assertEqual(smoke.call_count, 1)
        self.assertEqual(self.launched, [CLAUDE, CODEX])
        self.assertEqual(result["smoke"], "passed")
        self.assertNotIn("stopped", result)
        self.assertEqual(sorted(result["targets"]), [CLAUDE, CODEX])

    def test_the_record_reads_running_not_skipped_while_the_tier_runs(self):
        seen = []

        def tier(*args, **kwargs):
            seen.append(self.on_disk()["smoke"])
            return done(0)

        routing = {CLAUDE: ROUTING, CODEX: ROUTING}
        with patch.object(ROUND, "smoke", side_effect=tier), \
                patch.object(ROUND.subprocess, "run", side_effect=self.fake_run):
            ROUND.run_round(self.round_dir, [CLAUDE, CODEX], None, [], tier_routing=routing)
        self.assertEqual(seen, ["running"])

    def test_skip_smoke_runs_no_tier_records_skipped_and_runs_every_target(self):
        result, smoke = self.run_round(done(1), skip_smoke=True)
        self.assertEqual(smoke.call_count, 0)
        self.assertEqual(result["smoke"], "skipped")
        self.assertNotIn("stopped", result)
        self.assertEqual(self.launched, [CLAUDE, CODEX])

    def test_the_command_exits_nonzero_and_says_the_round_stopped(self):
        out = io.StringIO()
        with patch.object(ROUND, "smoke", side_effect=lambda *a, **k: done(1)), \
                patch("platform.system", return_value="Darwin"), \
                patch.object(ROUND.subprocess, "run", side_effect=self.fake_run), \
                redirect_stdout(out):
            code = ROUND.main(["--round", str(self.round_dir), "--targets", CLAUDE])
        self.assertEqual(code, 1)
        self.assertEqual(self.launched, [])
        self.assertIn("round stopped: the smoke tier failed", out.getvalue())

    def test_a_timed_out_tier_is_not_a_clean_round(self):
        with patch.object(ROUND, "smoke", side_effect=lambda *a, **k: None), \
                patch("platform.system", return_value="Darwin"), \
                patch.object(ROUND.subprocess, "run", side_effect=self.fake_run), \
                redirect_stdout(io.StringIO()):
            code = ROUND.main(["--round", str(self.round_dir), "--targets", CLAUDE])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
