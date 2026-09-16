# SPDX-License-Identifier: MIT
"""Unit tests for the planner agent. Run: python3 -m unittest discover tests"""
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

AGENT = REPO / "claude" / "agents" / "planner.md"
COMMAND = REPO / "claude" / "commands" / "plan.md"
SKILL = REPO / "claude" / "skills" / "plan-authoring" / "SKILL.md"
REQUIRED_KEYS = {"name", "description", "model", "tools", "effort"}
BANNED_TOOLS = {"Agent", "Edit", "NotebookEdit"}
MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
BODY_CAP = 70
CARD_SECTIONS = [
    "`# <title>`",
    "**Verdict blockquote**",
    "## At a glance",
    "## System design",
    "## Steps",
    "## Decisions for the reviewer",
    "## Risks",
]
CLOSING = "*Reply **build** to proceed, or keep refining.*"


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


class PlannerFrontmatterTests(unittest.TestCase):
    def test_it_declares_the_five_frontmatter_keys(self):
        fields, _ = frontmatter(AGENT)
        self.assertEqual(REQUIRED_KEYS - set(fields), set())
        self.assertEqual(fields["name"], "planner")
        self.assertTrue(fields["description"])

    def test_model_and_effort_are_values_the_tool_accepts(self):
        fields, _ = frontmatter(AGENT)
        self.assertEqual(fields["model"], "inherit")
        self.assertEqual(fields["effort"], "high")
        self.assertIn(fields["model"], MODELS)

    def test_it_can_write_the_plan_file_and_nothing_else(self):
        fields, _ = frontmatter(AGENT)
        tools = {t.strip() for t in fields["tools"].split(",")}
        self.assertIn("Write", tools)
        self.assertEqual(tools & BANNED_TOOLS, set())

    def test_the_only_writable_path_is_named(self):
        _, body = frontmatter(AGENT)
        self.assertIn(".claude/plans/", "\n".join(body))


class PlannerBodyTests(unittest.TestCase):
    def setUp(self):
        _, self.body = frontmatter(AGENT)
        self.text = "\n".join(self.body)

    def test_the_body_stays_short_enough_to_read(self):
        self.assertLessEqual(len([l for l in self.body if l.strip()]), BODY_CAP)

    def test_it_names_all_seven_card_sections_in_order(self):
        found = [s for s in CARD_SECTIONS if s in self.text]
        self.assertEqual(found, CARD_SECTIONS)
        positions = [self.text.index(s) for s in CARD_SECTIONS]
        self.assertEqual(positions, sorted(positions))

    def test_it_carries_both_card_cap_numbers(self):
        self.assertIn("70", self.text)
        self.assertIn("85", self.text)

    def test_it_forbids_tables_and_a_context_section(self):
        self.assertIn("no markdown tables", self.text.lower())
        self.assertIn("no `## Context` section", self.text)

    def test_it_carries_the_addendum_anchor_shape_and_the_self_check(self):
        self.assertIn("# Addendum", self.text)
        self.assertIn("## Step N — <title>", self.text)
        self.assertIn('awk \'/^---$/{exit} {n++} END{print n" card lines"}\'', self.text)

    def test_the_return_shape_is_the_reviewer_facing_message(self):
        shape = self.text.split("## Return the chat message", 1)[1]
        self.assertIn("## At a glance", shape)
        self.assertIn("## Decisions", shape)
        self.assertEqual(shape.count("verbatim"), 2)
        self.assertIn("workspace-relative", shape)
        self.assertIn(CLOSING, shape)

    def test_it_carries_no_table_line_and_no_deep_heading(self):
        fence = False
        for line in self.body:
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            self.assertFalse(line.lstrip().startswith("|"), msg=line)
            self.assertFalse(line.startswith("###"), msg=line)


class PlannerCallerTests(unittest.TestCase):
    def test_the_plan_command_names_the_agent_and_stays_short(self):
        lines = COMMAND.read_text(encoding="utf-8").splitlines()
        self.assertIn("planner", "\n".join(lines))
        self.assertLessEqual(len(lines), 35)

    def test_the_skill_delegates_to_the_agent_instead_of_pasting_the_template(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Delegating", text)
        delegating = text.split("## Delegating", 1)[1].split("\n## ", 1)[0]
        self.assertIn("`planner`", delegating)
        self.assertNotIn("Paste the `TEMPLATE.md`", delegating)


class PlannerSyncTests(unittest.TestCase):
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

    def test_sync_links_the_agent_into_the_home_directory(self):
        code = harness.cmd_sync(harness.argparse.Namespace(
            dry_run=False, adopt=True, adopt_codex=False, print_only=False))
        self.assertEqual(code, 0)
        link = self.home / ".claude" / "agents" / "planner.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), AGENT.resolve())


if __name__ == "__main__":
    unittest.main()
