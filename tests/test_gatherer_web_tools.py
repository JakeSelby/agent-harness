# SPDX-License-Identifier: MIT
"""An isolated `gatherer` is launched offline, and every surface that describes it says so.

The role declared `WebFetch` and `WebSearch` while the only path left open to it — the spawn
guard refuses a native constrained role and points at `harness role run` — launched it with
`Read,Grep,Glob`, so a web brief returned "no web tools". The confinement is the boundary
`docs/role-workers.md` states, so these tests hold the launched tool list where it is and hold
the declaration, the refusal and `/research` to it instead.

Run: python3 -m unittest discover tests
"""
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from test_harness import CFG, REPO
from harness_core import lifecycle, reconcile, workers
from pathlib import Path

READ_ONLY = ("Read", "Grep", "Glob")
FORBIDDEN = ("WebFetch", "WebSearch", "Bash", "Write", "Edit", "Agent", "Task")


def front_matter(path):
    body = path.read_text().split("---", 2)[1]
    return {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in body.strip().splitlines())}


class LaunchedToolsTests(unittest.TestCase):
    """The command `harness role run gatherer` actually launches, captured at the last step.

    Driven through `workers.run` rather than the adapter alone, so the assertion covers the role
    the caller named and not a tool list that happens to be the same for every role today.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.cfg = copy.deepcopy(CFG)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base / "user"), "PATH": os.environ["PATH"]}, clear=True).start()

    def launch(self, runtime):
        """The command line of a completed `gatherer` run, with the native process stubbed out."""
        captured = {}

        def execute(command, prompt, env, cwd, run_dir, timeout):
            captured["command"] = command
            # The worker's private home is removed when the run returns, so read it here.
            config = cwd.parent / "codex/config.toml"
            if config.is_file():
                captured["config"] = config.read_text()
            if "--output-format" in command:
                (run_dir / "stdout.log").write_text(json.dumps(
                    {"type": "result", "subtype": "success", "is_error": False, "result": "verdict"}))
            else:
                Path(command[command.index("-o") + 1]).write_text("verdict")
            return 0

        with patch.object(workers.shutil, "which", return_value="/native/cli"), \
             patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
             patch.object(workers, "execute", execute):
            record = workers.run(REPO, self.cfg, runtime, "gatherer", self.workspace, "Find every caller.",
                                 self.base / "state", model="fixture-model")
        self.assertEqual(record["status"], "completed")
        return captured

    def test_claude_gatherer_launches_with_read_tools_and_no_web_tools(self):
        command = self.launch("claude-code")["command"]
        self.assertEqual(command[command.index("--tools") + 1], ",".join(READ_ONLY))
        for tool in FORBIDDEN:
            self.assertNotIn(tool, " ".join(command))

    def test_codex_gatherer_launches_read_only_with_hosted_search_disabled(self):
        config = reconcile.tomlkit.parse(self.launch("codex")["config"]).unwrap()
        self.assertEqual(config["web_search"], "disabled")
        self.assertEqual(config["sandbox_mode"], "read-only")


class DeclarationTests(unittest.TestCase):
    """The role contract, the adapter binding and the rendered projection declare the same list."""

    def test_the_claude_binding_declares_only_the_read_tools(self):
        bindings = json.loads((REPO / "adapters/claude-code/bindings.json").read_text())
        declared = [part.strip() for part in bindings["roles"]["gatherer"]["tools"].split(",")]
        self.assertEqual(declared, list(READ_ONLY))

    def test_the_rendered_agent_declares_only_the_read_tools(self):
        self.assertEqual(front_matter(REPO / "claude/agents/gatherer.md")["tools"], ", ".join(READ_ONLY))

    def test_the_role_body_states_the_worker_is_offline(self):
        body = (REPO / "primitives/roles/gatherer.md").read_text()
        self.assertIn("offline", body.lower())
        self.assertIn("WebFetch", body)


class RoutingTests(unittest.TestCase):
    """The refusal and `/research` send a web dimension somewhere that has web tools."""

    def test_the_refusal_names_the_offline_worker_and_the_band_alternative(self):
        reason = lifecycle.role_deny("claude-code", "gatherer", lifecycle.constrained_role("gatherer"))
        text = reason["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("harness role run gatherer", text)
        self.assertIn("offline", text)
        self.assertIn("worker-a", text)

    def test_another_constrained_role_keeps_its_unchanged_refusal(self):
        reason = lifecycle.role_deny("claude-code", "reviewer", lifecycle.constrained_role("reviewer"))
        text = reason["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("harness role run reviewer", text)
        self.assertNotIn("worker-a", text)

    def test_research_routes_web_dimensions_away_from_the_worker(self):
        text = (REPO / "primitives/workflows/research.md").read_text()
        self.assertIn("harness role run gatherer", text)
        self.assertIn("band worker", text)


if __name__ == "__main__":
    unittest.main()
