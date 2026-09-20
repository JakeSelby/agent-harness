# SPDX-License-Identifier: MIT
"""Unit tests for the designer subagent. Run: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)
sys.path.insert(0, str(REPO / "lib"))
from harness_core import catalog, lifecycle  # noqa: E402

AGENT = REPO / "claude" / "agents" / "designer.md"
ROLE = REPO / "primitives" / "roles" / "designer.md"
SKILL = REPO / "claude" / "skills" / "design-loop" / "SKILL.md"
HOOK = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
REQUIRED_KEYS = {"name", "description", "model", "tools", "effort"}
GATES = ["accessibility", "design tokens", "runtime", "asset licensing"]
BODY_CAP = 50


def frontmatter(path):
    """The leading --- block as a flat mapping; values stay strings."""
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, lines[end + 1:]


class DesignerFileTests(unittest.TestCase):
    def test_it_declares_the_five_frontmatter_keys_and_the_strongest_class(self):
        fields, _ = frontmatter(AGENT)
        self.assertEqual(REQUIRED_KEYS - set(fields), set())
        self.assertEqual(fields["name"], "designer")
        self.assertEqual(fields["effort"], "high")
        self.assertEqual(frontmatter(ROLE)[0]["tier"], "frontier")
        tiers = json.loads((REPO / "adapters" / "claude-code" / "bindings.json").read_text())["tiers"]
        self.assertEqual(fields["model"], tiers["frontier"])

    def test_it_can_write_and_cannot_re_delegate(self):
        fields, _ = frontmatter(AGENT)
        tools = {t.strip() for t in fields["tools"].split(",")}
        self.assertTrue({"Edit", "Write", "Bash"} <= tools)
        self.assertNotIn("Agent", tools)
        self.assertEqual(frontmatter(ROLE)[0]["authority"], "workspace-write")

    def test_the_body_stays_short_and_never_judges_its_own_work(self):
        _, body = frontmatter(AGENT)
        self.assertLessEqual(len([l for l in body if l.strip()]), BODY_CAP)
        text = "\n".join(body).lower()
        for phrase in ("never score", "locked target", "capture", "licensing-review", "rubric-ui.md", "rubric-scene.md"):
            self.assertIn(phrase, text, msg=phrase)
        for gate in GATES:
            self.assertIn(gate, text, msg=gate)

    def test_the_loop_names_the_designer_and_keeps_the_judge_separate(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("`designer`", text)
        self.assertIn("`design-judge`", text)

    def test_both_adapters_bind_it_and_codex_gets_its_strongest_model(self):
        codex = json.loads((REPO / "adapters" / "codex" / "bindings.json").read_text())
        self.assertEqual(codex["roles"]["designer"], {"model_reasoning_effort": "high"})
        self.assertIn('model = "' + codex["tiers"]["frontier"] + '"', catalog.role_projection(REPO, "codex", ROLE))
        self.assertIn('sandbox_mode = "workspace-write"', catalog.role_projection(REPO, "codex", ROLE))


class DesignerSpawnTests(unittest.TestCase):
    """The strongest class is the designer's by declaration, which is the only way a spawn reaches it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        agents = self.home / ".claude" / "agents"
        agents.mkdir(parents=True)
        (agents / "designer.md").write_text(AGENT.read_text(encoding="utf-8"))
        self.env = dict(os.environ, HOME=str(self.home), HARNESS_STANCE_DELEGATION="tiered")

    def hook(self, tool_input):
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": "Agent", "tool_input": tool_input}),
                             capture_output=True, text=True, env=self.env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def test_a_designer_spawn_keeps_the_top_tier_and_an_unnamed_one_does_not(self):
        top = json.loads((REPO / "adapters" / "claude-code" / "bindings.json").read_text())["tiers"]["frontier"]
        self.assertIsNone(self.hook({"prompt": "design", "subagent_type": "designer"}))
        self.assertIsNone(self.hook({"prompt": "design", "subagent_type": "designer", "model": top}))
        self.assertNotEqual(self.hook({"prompt": "design", "model": top})["hookSpecificOutput"]["updatedInput"]["model"], top)

    def test_it_spawns_natively_because_it_writes(self):
        with unittest.mock.patch.dict(os.environ, self.env, clear=True):
            out = lifecycle.dispatch("claude-code", {"hook_event_name": "PreToolUse", "tool_name": "Agent",
                "tool_input": {"prompt": "Design one pass. Return at most 300 words.", "subagent_type": "designer"}})
        self.assertNotEqual(out.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")


class DesignerSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_environ = dict(os.environ)
        os.environ["HOME"] = str(self.home)
        for k in list(os.environ):
            if k.startswith("HARNESS_"):
                del os.environ[k]
        os.environ["HARNESS_QUIET"] = "1"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_environ)
        self.tmp.cleanup()

    def test_sync_renders_the_agent_and_uninstall_removes_it(self):
        args = harness.argparse.Namespace(dry_run=False, adopt=True, adopt_codex=False, print_only=False)
        self.assertEqual(harness.cmd_sync(args), 0)
        native = self.home / ".claude" / "agents" / "designer.md"
        self.assertFalse(native.is_symlink())
        # No cost row names the designer, so it renders exactly as the committed projection.
        self.assertEqual(native.read_text(encoding="utf-8"), AGENT.read_text(encoding="utf-8"))
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse(native.exists() or native.is_symlink())


if __name__ == "__main__":
    unittest.main()
