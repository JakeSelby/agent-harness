# SPDX-License-Identifier: MIT
"""A target's record is produced only on its own platform's host.

The runner stamps a record's `platform` from the target spec, so a Linux target driven on a Mac
would publish the Mac's outcome under the Linux name. Every test pins `platform.system()`, so the
answers hold on any host the suite runs on, and none launches a client.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import MODULE
from test_qualification_worker_class import FAKE_ROUTING, ROUND

MAC = "claude-code-cli-macos"
LINUX = "claude-code-cli-linux"
REFUSAL = ("claude-code-cli-linux is a linux target and this host is Darwin; run it inside the "
           "target image (docs/qualification-runbook.md, Target hosts)")


def host(name):
    return patch("platform.system", return_value=name)


class RunnerHostTests(unittest.TestCase):
    def test_a_linux_target_on_a_mac_is_refused_before_any_case_runs(self):
        with host("Darwin"), \
                patch.object(MODULE, "record", side_effect=AssertionError("a case ran")), \
                patch.object(MODULE.subprocess, "run",
                             side_effect=AssertionError("a process ran")):
            with self.assertRaises(SystemExit) as raised:
                MODULE.main(["--client", LINUX, "--cases", "cost-posture"])
        self.assertEqual(str(raised.exception), REFUSAL)

    def test_a_macos_target_on_linux_is_refused_naming_both(self):
        with host("Linux"):
            reason = MODULE.host_mismatch(MAC)
        self.assertIn("claude-code-cli-macos is a macos target", reason)
        self.assertIn("this host is Linux", reason)

    def test_a_target_on_its_own_host_is_not_refused(self):
        with host("Darwin"):
            self.assertEqual(MODULE.host_mismatch(MAC), "")
        with host("Linux"):
            self.assertEqual(MODULE.host_mismatch(LINUX), "")

    def test_an_unknown_host_runs_no_target(self):
        for client in MODULE.CLIENTS:
            self.assertIn("this host is Windows", MODULE.host_mismatch(client, "Windows"))

    def test_the_matching_host_reaches_the_record(self):
        with host("Linux"), patch.object(MODULE, "record",
                                         return_value={"cases": {"cost-posture": "passed"}}) as rec:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(MODULE.main(["--client", LINUX, "--cases", "cost-posture"]), 0)
        self.assertEqual(rec.call_count, 1)

    def test_a_dry_plan_is_not_refused(self):
        with host("Darwin"), redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main(["--client", LINUX, "--dry-plan"]), 0)


class RoundHostTests(unittest.TestCase):
    def plan(self, system, targets):
        buffer = io.StringIO()
        with host(system), redirect_stdout(buffer):
            self.assertEqual(ROUND.main(["--round", "/round", "--targets", targets, "--plan"]), 0)
        return buffer.getvalue()

    def test_the_plan_says_where_each_target_runs(self):
        printed = self.plan("Darwin", MAC + "," + LINUX)
        self.assertEqual(printed.count("runs on this host"), 1)
        self.assertEqual(printed.count("runs inside the Linux image"), 1)
        self.assertLess(printed.index(MAC), printed.index("runs on this host"))
        self.assertLess(printed.index(LINUX), printed.index("runs inside the Linux image"))

    def test_inside_the_image_the_linux_target_runs_here(self):
        printed = self.plan("Linux", MAC + "," + LINUX)
        self.assertEqual(printed.count("runs on this host"), 1)
        self.assertIn("runs on a macOS host, not this one", printed)

    def mixed_round(self, targets, record=None):
        launched = []
        done = type("Done", (), {"returncode": 0})()

        def run(argv, **kwargs):
            launched.append(argv)
            if record is not None:
                Path(argv[argv.index("--out") + 1]).write_text(json.dumps(record))
            return done

        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as temp:
            round_dir = Path(temp)
            (round_dir / "provision.json").write_text(json.dumps(
                {"clone": str(round_dir / "clone"), "records": str(round_dir / "records"),
                 "source_commit": "a" * 40}))
            with host("Darwin"), \
                    patch.object(ROUND, "routing",
                                 return_value=dict((name, FAKE_ROUTING) for name in targets)), \
                    patch.object(ROUND, "smoke",
                                 side_effect=lambda clone, env, targets=(): done), \
                    patch.object(ROUND.subprocess, "run",
                                 side_effect=run), \
                    redirect_stdout(buffer):
                code = ROUND.main(["--round", str(round_dir), "--targets", ",".join(targets)])
            written = json.loads((round_dir / "round.json").read_text()) \
                if (round_dir / "round.json").exists() else None
        return code, launched, buffer.getvalue(), written

    def test_a_mixed_round_on_a_mac_runs_the_mac_target_and_skips_the_linux_one(self):
        code, launched, printed, written = self.mixed_round([MAC, LINUX])
        self.assertEqual([argv[argv.index("--client") + 1] for argv in launched], [MAC])
        [line] = [line for line in printed.splitlines() if "not run here" in line]
        self.assertEqual(line.split(None, 1), [LINUX, "not run here: " + REFUSAL])
        self.assertEqual(sorted(written["targets"]), [MAC])
        self.assertEqual(written["not_run_here"], {LINUX: REFUSAL})
        # The skipped target is not a failure: the Mac target's own record decides the status,
        # and here its runner wrote none, so the status is 1 for that reason alone.
        self.assertIn(MAC, ROUND.summarise(written["targets"]))
        self.assertEqual(code, 1)

    def test_a_skipped_target_does_not_fail_a_round_whose_other_targets_passed(self):
        passed = {"cases": dict((name, "passed") for name in MODULE.catalog()["required_cases"])}
        code, launched, printed, written = self.mixed_round([MAC, LINUX], record=passed)
        self.assertIn("not run here", printed)
        self.assertEqual(written["targets"][MAC]["cases"], passed["cases"])
        self.assertEqual(code, 0)

    def test_a_round_with_no_target_for_this_host_runs_nothing(self):
        code, launched, printed, written = self.mixed_round([LINUX])
        self.assertEqual(launched, [])
        self.assertIn("ran nothing", printed)
        self.assertIsNone(written)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
