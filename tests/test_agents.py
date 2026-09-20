# SPDX-License-Identifier: MIT
"""Unit tests for the shipped subagent definitions. Run: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

AGENTS = REPO / "claude" / "agents"
SHIPPED = ["gatherer", "log-compressor", "reviewer"]
REQUIRED_KEYS = {"name", "description", "model", "tools", "effort"}
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "Agent", "Bash"}
MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
BODY_CAP = 30


def frontmatter(path):
    """The leading --- block as a flat mapping; values stay strings."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"{path.name} has no frontmatter block")
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, lines[end + 1:]


class AgentFileTests(unittest.TestCase):
    def test_the_three_shipped_agents_are_present(self):
        self.assertLessEqual(set(SHIPPED), {p.stem for p in AGENTS.glob("*.md")})

    def test_every_agent_declares_the_five_frontmatter_keys(self):
        for name in SHIPPED:
            fields, _ = frontmatter(AGENTS / f"{name}.md")
            self.assertEqual(REQUIRED_KEYS - set(fields), set(), msg=name)
            self.assertEqual(fields["name"], name)
            self.assertTrue(fields["description"], msg=name)

    def test_tool_lists_carry_no_write_tool(self):
        for name in SHIPPED:
            fields, _ = frontmatter(AGENTS / f"{name}.md")
            tools = {t.strip() for t in fields["tools"].split(",")}
            self.assertTrue(tools, msg=name)
            self.assertEqual(tools & WRITE_TOOLS, set(), msg=name)

    def test_models_and_effort_are_values_the_tool_accepts(self):
        for name in SHIPPED:
            fields, _ = frontmatter(AGENTS / f"{name}.md")
            self.assertIn(fields["model"], MODELS, msg=name)
            self.assertIn(fields["effort"], {"low", "medium", "high", "xhigh", "max"}, msg=name)

    def test_bodies_stay_short_enough_to_read(self):
        for name in SHIPPED:
            _, body = frontmatter(AGENTS / f"{name}.md")
            self.assertLessEqual(len([l for l in body if l.strip()]), BODY_CAP, msg=name)


class AgentSyncTests(unittest.TestCase):
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

    def _sync(self, adopt=False):
        return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=adopt, adopt_codex=False, print_only=False))

    def test_sync_renders_every_agent_and_uninstall_removes_them(self):
        self.assertEqual(self._sync(adopt=True), 0)
        native = self.home / ".claude" / "agents"
        for name in SHIPPED:
            path = native / f"{name}.md"
            self.assertFalse(path.is_symlink(), msg=str(path))
            self.assertEqual(path.read_text(encoding="utf-8"),
                             (AGENTS / f"{name}.md").read_text(encoding="utf-8"), msg=name)
        self.assertEqual(self._sync(), 0)
        self.assertEqual(harness._diff_lines(), [])
        harness.cmd_uninstall(harness.argparse.Namespace())
        for name in SHIPPED:
            self.assertFalse((native / f"{name}.md").exists())
            self.assertFalse((native / f"{name}.md").is_symlink())

    def test_a_hand_written_agent_is_never_replaced_without_adopt(self):
        mine = self.home / ".claude" / "agents" / "gatherer.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("mine")
        self.assertEqual(self._sync(), 2)
        self.assertEqual(mine.read_text(), "mine")
        # Adopting moves the user's file aside, as it did when agents were linked.
        self.assertEqual(self._sync(adopt=True), 0)
        self.assertEqual(mine.read_text(), (AGENTS / "gatherer.md").read_text(encoding="utf-8"))
        moved = list((self.home / ".local/state/agent-harness/pre-harness").rglob("gatherer.md"))
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].read_text(), "mine")
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertEqual(mine.read_text(), "mine")


if __name__ == "__main__":
    unittest.main()
