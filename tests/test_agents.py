# SPDX-License-Identifier: MIT
"""Unit tests for the shipped subagent definitions. Run: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from isolation import isolate_home

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
        isolate_home(self.home)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_environ)
        self.tmp.cleanup()

    def _sync(self, adopt=False):
        return harness.cmd_sync(harness.argparse.Namespace(dry_run=False, adopt=adopt, adopt_codex=False, print_only=False))

    def test_sync_links_every_agent_and_uninstall_removes_them(self):
        self.assertEqual(self._sync(adopt=True), 0)
        links = self.home / ".claude" / "agents"
        for name in SHIPPED:
            link = links / f"{name}.md"
            self.assertTrue(link.is_symlink(), msg=str(link))
            self.assertEqual(link.resolve(), (AGENTS / f"{name}.md").resolve())
        self.assertEqual(self._sync(), 0)
        self.assertEqual(harness._diff_lines(), [])
        harness.cmd_uninstall(harness.argparse.Namespace())
        for name in SHIPPED:
            self.assertFalse((links / f"{name}.md").exists())
            self.assertFalse((links / f"{name}.md").is_symlink())

    def test_a_hand_written_agent_is_never_replaced_without_adopt(self):
        mine = self.home / ".claude" / "agents" / "gatherer.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("mine")
        self.assertEqual(self._sync(), 2)
        self.assertEqual(mine.read_text(), "mine")
        self.assertEqual(self._sync(adopt=True), 0)
        self.assertTrue(mine.is_symlink())
        moved = list((self.home / ".local/state/agent-harness/pre-harness").rglob("gatherer.md"))
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].read_text(), "mine")


if __name__ == "__main__":
    unittest.main()
