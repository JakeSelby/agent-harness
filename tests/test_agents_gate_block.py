# SPDX-License-Identifier: MIT
"""The repository's own `## Gate` block, as the stop-gate hook parses it, runs the BMad checks
CI's `test` job runs, so a green local gate is not a red `test` job on a stale sprint status.
Run: python3 -m unittest tests.test_agents_gate_block
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "stop-gate.py"
CI = REPO / ".github" / "workflows" / "ci.yml"
AUDIT = "python3 scripts/bmad_issue_sync.py audit"
SPRINT_CHECK = "python3 scripts/bmad_issue_sync.py sprint-status --check"


def load_hook():
    spec = importlib.util.spec_from_file_location("stop_gate_under_test", str(HOOK))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryGateBlockTests(unittest.TestCase):
    def setUp(self):
        self.commands = load_hook().gate_commands(REPO)

    def test_the_hook_parses_the_bmad_checks(self):
        self.assertIn(AUDIT, self.commands)
        self.assertIn(SPRINT_CHECK, self.commands)

    def test_the_bmad_checks_run_before_the_suite(self):
        suite = self.commands.index("python3 -m unittest discover -s tests")
        self.assertLess(self.commands.index(SPRINT_CHECK), suite)
        self.assertLess(self.commands.index(AUDIT), suite)

    def test_the_audit_is_the_command_ci_runs(self):
        self.assertIn("run: " + AUDIT + "\n", CI.read_text(encoding="utf-8"))

    def test_the_subcommands_and_flag_exist(self):
        script = str(REPO / "scripts" / "bmad_issue_sync.py")
        for args, flag in ((["audit"], None), (["sprint-status"], "--check")):
            out = subprocess.run([sys.executable, script] + args + ["--help"], cwd=str(REPO),
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            if flag:
                self.assertIn(flag, out.stdout)


if __name__ == "__main__":
    unittest.main()
