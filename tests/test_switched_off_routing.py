# SPDX-License-Identifier: MIT
"""The spawn hook never routes an unnamed spawn to a band worker the selection switches off.

Run: python3 -m unittest discover tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
COMMITTED = REPO / "claude" / "agents"
WORKERS = ("worker-a", "worker-b", "worker-c")
SESSION = "fixture-session"


class SwitchedOffWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text(json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5"}}) + "\n")
        # Every worker installed and known to this session, as a sync made before the switch.
        agents = self.home / ".claude" / "agents"
        agents.mkdir(parents=True)
        for name in WORKERS:
            (agents / (name + ".md")).write_text((COMMITTED / (name + ".md")).read_text(encoding="utf-8"))
        sessions = self.home / ".local" / "state" / "agent-harness" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / (SESSION + ".json")).write_text(json.dumps({"agents": list(WORKERS), "at": 0}))

    def config(self, **selection):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(dict({"stances": {"delegation": "tiered"}}, **selection)))

    def spawn(self):
        env = without_harness_vars()
        env["HOME"] = str(self.home)
        payload = {"tool_name": "Agent", "transcript_path": str(self.transcript),
                   "session_id": SESSION, "tool_input": {"prompt": "x"}}
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_an_installed_worker_routes_while_it_is_on(self):
        self.config()
        updated = self.spawn()["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["subagent_type"], "worker-b")

    def test_a_worker_switched_off_is_not_routed_to_even_while_its_file_remains(self):
        self.config(roles={"worker-b": "off"})
        out = self.spawn()
        updated = out["hookSpecificOutput"]["updatedInput"]
        self.assertNotIn("subagent_type", updated)
        self.assertEqual(updated["model"], "sonnet")  # the one-rung rule, as with no worker at all
        self.assertIn("worker-b is switched off in the selection", out["systemMessage"])


if __name__ == "__main__":
    unittest.main()
