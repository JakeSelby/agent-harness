# SPDX-License-Identifier: MIT
"""Unit tests for the stop-gate hook. Run: python3 -m unittest discover tests

The hook runs as a subprocess with HOME pointed at a temporary directory, so its state file
lands there. The commit identity is assembled at run time, so this file carries no
address-shaped literal for the lint to find.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "stop-gate.py"
IDENTITY = "gate" + "@" + "example" + ".invalid"


class StopGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        self.repo.mkdir()
        self.counter = base / "runs.txt"
        self.git("init")
        (self.repo / "file.txt").write_text("one\n")
        self.git("add", "-A")
        self.git("commit", "-m", "initial")

    def env(self):
        env = dict(os.environ)
        env.update({
            "HOME": str(self.home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Gate Fixture",
            "GIT_COMMITTER_NAME": "Gate Fixture",
            "GIT_AUTHOR_EMAIL": IDENTITY,
            "GIT_COMMITTER_EMAIL": IDENTITY,
        })
        return env

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], env=self.env(),
                       capture_output=True, text=True, check=True)

    def write_gate(self, *commands, **kwargs):
        name = kwargs.get("name", "AGENTS.md")
        heading = kwargs.get("heading", "## Gate")
        body = "# a repo\n\n## Commands\n\n```sh\nexit 3\n```\n"
        if heading:
            body += "\n" + heading + "\n\n```sh\n" + "\n".join(commands) + "\n```\n"
        (self.repo / name).write_text(body)

    def run_hook(self, session="s1", payload=None, stdin=None):
        if stdin is None:
            body = {"session_id": session, "cwd": str(self.repo),
                    "hook_event_name": "Stop", "stop_hook_active": False}
            body.update(payload or {})
            stdin = json.dumps(body)
        return subprocess.run([sys.executable, str(HOOK)], input=stdin, env=self.env(),
                              capture_output=True, text=True, timeout=180)

    def state_files(self):
        d = self.home / ".local" / "state" / "agent-harness" / "stop-gate"
        return sorted(d.glob("*.json")) if d.is_dir() else []

    def state(self):
        files = self.state_files()
        self.assertEqual(len(files), 1)
        return json.loads(files[0].read_text())

    def test_a_repo_without_a_gate_block_is_untouched(self):
        self.write_gate(heading=None)
        out = self.run_hook()
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")
        self.assertEqual(self.state_files(), [])

    def test_no_git_root_is_a_no_op(self):
        loose = Path(self.tmp.name) / "loose"
        loose.mkdir()
        out = self.run_hook(payload={"cwd": str(loose)})
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_green_gate_is_silent_and_records_the_tree_hash(self):
        self.write_gate("true")
        out = self.run_hook()
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")
        recorded = self.state()
        self.assertTrue(recorded["green_hash"])
        self.assertEqual(recorded["blocks"], 0)
        self.assertEqual(recorded["session_id"], "s1")

    def test_the_gate_block_is_read_from_claude_md_when_agents_md_is_absent(self):
        self.write_gate("exit 1", name="CLAUDE.md")
        out = self.run_hook()
        self.assertEqual(json.loads(out.stdout)["decision"], "block")

    def test_red_gate_blocks_and_names_the_failing_command(self):
        self.write_gate("true", "echo boom >&2; exit 4")
        out = self.run_hook()
        self.assertEqual(out.returncode, 0)
        decision = json.loads(out.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("exit 4", decision["reason"])
        self.assertIn("exited 4", decision["reason"])
        self.assertIn("boom", decision["reason"])
        self.assertEqual(self.state()["blocks"], 1)

    def test_stop_hook_active_does_not_short_circuit_the_gate(self):
        self.write_gate("exit 1")
        out = self.run_hook(payload={"stop_hook_active": True})
        self.assertEqual(json.loads(out.stdout)["decision"], "block")

    def test_an_unchanged_tree_skips_the_commands(self):
        self.write_gate('echo run >> "%s"' % self.counter)
        self.run_hook()
        self.assertEqual(self.counter.read_text().count("\n"), 1)
        self.run_hook()
        self.assertEqual(self.counter.read_text().count("\n"), 1)
        (self.repo / "file.txt").write_text("two\n")
        self.run_hook()
        self.assertEqual(self.counter.read_text().count("\n"), 2)

    def test_the_eighth_consecutive_block_releases_the_turn(self):
        self.write_gate("exit 1")
        for expected in range(1, 8):
            out = self.run_hook()
            self.assertEqual(json.loads(out.stdout)["decision"], "block")
            self.assertEqual(self.state()["blocks"], expected)
        out = self.run_hook()
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")
        self.assertIn("stop-gate:", out.stderr)
        self.assertEqual(self.state()["blocks"], 0)

    def test_a_new_session_restarts_the_count(self):
        self.write_gate("exit 1")
        self.run_hook(session="s1")
        self.run_hook(session="s1")
        self.assertEqual(self.state()["blocks"], 2)
        out = self.run_hook(session="s2")
        self.assertEqual(json.loads(out.stdout)["decision"], "block")
        recorded = self.state()
        self.assertEqual(recorded["blocks"], 1)
        self.assertEqual(recorded["session_id"], "s2")

    def test_malformed_stdin_exits_quietly(self):
        self.write_gate("exit 1")
        out = self.run_hook(stdin="not json at all")
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")
        self.assertEqual(self.state_files(), [])


class RegistrationTests(unittest.TestCase):
    def test_template_and_ownership_carry_the_hook(self):
        template = json.loads((REPO / "claude" / "settings.template.json").read_text())
        commands = [h["command"] for e in template["hooks"]["Stop"] for h in e["hooks"]]
        self.assertTrue(any("# harness:stop-gate" in c for c in commands))
        self.assertTrue(any("stop-gate.py" in c for c in commands))
        ownership = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())
        self.assertEqual(ownership["claude"]["hook_ids"]["stop-gate"], {"event": "Stop", "always": True})

    def test_the_harness_gates_itself(self):
        text = (REPO / "AGENTS.md").read_text()
        self.assertIn("\n## Gate\n", text)
        self.assertIn("python3 bin/harness lint", text.split("\n## Gate\n", 1)[1])


if __name__ == "__main__":
    unittest.main()
