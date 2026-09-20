# SPDX-License-Identifier: MIT
"""Unit tests for the design-judge subagent. Run: python3 -m unittest discover tests"""
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

AGENT = REPO / "claude" / "agents" / "design-judge.md"
SKILL = REPO / "claude" / "skills" / "design-loop" / "SKILL.md"
JUDGE = REPO / "claude" / "skills" / "design-loop" / "references" / "judge.md"
REQUIRED_KEYS = {"name", "description", "model", "tools", "effort"}
FORBIDDEN_TOOLS = {"Edit", "Write", "NotebookEdit", "Agent", "Bash"}
MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
GATES = ["accessibility", "design tokens", "runtime", "asset licensing"]
BODY_CAP = 50


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


class DesignJudgeFileTests(unittest.TestCase):
    def test_it_declares_the_five_frontmatter_keys(self):
        fields, _ = frontmatter(AGENT)
        self.assertEqual(REQUIRED_KEYS - set(fields), set())
        self.assertEqual(fields["name"], "design-judge")
        self.assertTrue(fields["description"])

    def test_model_and_effort_are_values_the_tool_accepts(self):
        fields, _ = frontmatter(AGENT)
        self.assertIn(fields["model"], MODELS)
        self.assertIn(fields["effort"], {"low", "medium", "high", "xhigh", "max"})

    def test_it_can_neither_edit_nor_re_delegate_nor_shell_out(self):
        fields, _ = frontmatter(AGENT)
        tools = {t.strip() for t in fields["tools"].split(",")}
        self.assertTrue(tools)
        self.assertEqual(tools & FORBIDDEN_TOOLS, set())
        self.assertIn("Read", tools)

    def test_the_body_stays_short_enough_to_read(self):
        _, body = frontmatter(AGENT)
        self.assertLessEqual(len([l for l in body if l.strip()]), BODY_CAP)

    def test_the_body_points_at_both_rubrics(self):
        text = AGENT.read_text(encoding="utf-8")
        self.assertIn("rubric-ui.md", text)
        self.assertIn("rubric-scene.md", text)

    def test_the_body_names_every_hard_gate_and_the_fix_list(self):
        text = AGENT.read_text(encoding="utf-8").lower()
        for gate in GATES:
            self.assertIn(gate, text, msg=gate)
        self.assertIn("top fixes", text)

    def test_the_loop_names_the_agent_instead_of_pasting_a_rubric(self):
        for path in (SKILL, JUDGE):
            self.assertIn("design-judge", path.read_text(encoding="utf-8"), msg=path.name)


class DesignJudgeSyncTests(unittest.TestCase):
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
        native = self.home / ".claude" / "agents" / "design-judge.md"
        self.assertFalse(native.is_symlink())
        self.assertEqual(native.read_text(encoding="utf-8"), AGENT.read_text(encoding="utf-8"))
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse(native.exists())
        self.assertFalse(native.is_symlink())


if __name__ == "__main__":
    unittest.main()
