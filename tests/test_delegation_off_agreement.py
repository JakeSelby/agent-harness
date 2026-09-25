# SPDX-License-Identifier: MIT
"""The `delegation: off` stance, the spawn hook and the lifecycle say the same thing (issue #687).

The stance text says a spawn is denied outright. The lifecycle denies it before any spawn hook
runs, and `tier-agent-spawns.py`, run on its own, must deny it with the same reason, so neither
path can drift back to an ask the stance does not describe.

Run: python3 -m unittest discover tests
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STANCE = REPO / "primitives" / "stances" / "delegation" / "off.md"
HOOK = REPO / "policy" / "hooks" / "tier-agent-spawns.py"
LIFECYCLE = REPO / "lib" / "harness_core" / "lifecycle.py"


def lifecycle_reason():
    """The reason the lifecycle gives when it denies a spawn under `off`."""
    text = LIFECYCLE.read_text(encoding="utf-8")
    match = re.search(r'"permissionDecisionReason": "(Delegation is off;[^"]*)"', text)
    return match.group(1) if match else None


class DelegationOffAgreementTests(unittest.TestCase):
    def run_hook(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, HARNESS_STANCE_DELEGATION="off")
            env.pop("CLAUDE_CONFIG_DIR", None)
            payload = json.dumps({"tool_name": "Agent", "tool_input": {"prompt": "x"}})
            proc = subprocess.run([sys.executable, str(HOOK)], input=payload, env=env,
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["hookSpecificOutput"]

    def test_stance_says_denied(self):
        self.assertIn("denied outright", STANCE.read_text(encoding="utf-8"))

    def test_hook_header_says_deny(self):
        header = HOOK.read_text(encoding="utf-8").split('"""')[1]
        line = next(row for row in header.splitlines() if row.strip().startswith("off "))
        self.assertIn("deny every spawn", line)
        self.assertNotIn("ask", line)

    def test_hook_denies_with_the_lifecycle_reason(self):
        reason = lifecycle_reason()
        self.assertIsNotNone(reason, "the lifecycle's off-branch deny reason was not found")
        out = self.run_hook()
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertTrue(out["permissionDecisionReason"].startswith(reason),
                        out["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
