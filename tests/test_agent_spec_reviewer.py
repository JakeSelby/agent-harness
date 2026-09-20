# SPDX-License-Identifier: MIT
"""Unit tests for the spec-reviewer agent and the two-pass review command.
Run: python3 -m unittest discover tests"""
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

AGENT = REPO / "claude" / "agents" / "spec-reviewer.md"
REVIEW = REPO / "claude" / "commands" / "review.md"
REQUIRED_KEYS = {"name", "description", "model", "tools", "effort"}
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "Agent"}
MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
BODY_CAP = 40


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


class SpecReviewerFileTests(unittest.TestCase):
    def test_it_declares_the_five_frontmatter_keys(self):
        fields, _ = frontmatter(AGENT)
        self.assertEqual(REQUIRED_KEYS - set(fields), set())
        self.assertEqual(fields["name"], "spec-reviewer")
        self.assertTrue(fields["description"])

    def test_model_and_effort_are_values_the_tool_accepts(self):
        fields, _ = frontmatter(AGENT)
        self.assertIn(fields["model"], MODELS)
        self.assertIn(fields["effort"], {"low", "medium", "high", "xhigh", "max"})

    def test_the_tool_list_is_read_only_and_cannot_re_delegate(self):
        fields, _ = frontmatter(AGENT)
        tools = {t.strip() for t in fields["tools"].split(",")}
        self.assertTrue(tools)
        self.assertEqual(tools & WRITE_TOOLS, set())
        self.assertNotIn("Bash", tools)

    def test_the_body_stays_short_enough_to_read(self):
        _, body = frontmatter(AGENT)
        self.assertLessEqual(len([l for l in body if l.strip()]), BODY_CAP)

    def test_the_body_names_the_three_lists_it_returns(self):
        body = "\n".join(frontmatter(AGENT)[1]).lower()
        self.assertIn("not asked for", body)
        self.assertIn("asked for but not done", body)
        self.assertIn("acceptance criterion", body)

    def test_the_body_refuses_the_quality_pass_and_any_edit(self):
        body = "\n".join(frontmatter(AGENT)[1]).lower()
        self.assertIn("`reviewer` agent", body)
        self.assertIn("no fixes, no edits", body)


class ReviewCommandTests(unittest.TestCase):
    def _body(self):
        text = REVIEW.read_text(encoding="utf-8")
        return text[4:].partition("\n---\n")[2]

    def test_the_scope_pass_is_spawned_before_the_quality_pass(self):
        body = self._body()
        self.assertIn("`spec-reviewer`", body)
        self.assertIn("`reviewer`", body)
        self.assertLess(body.index("`spec-reviewer`"), body.index("`reviewer`"))

    def test_it_reports_a_scope_section_then_a_quality_section(self):
        body = self._body()
        self.assertIn("**Scope**", body)
        self.assertIn("**Quality**", body)
        self.assertLess(body.index("**Scope**"), body.index("**Quality**"))

    def test_the_argument_hint_mentions_the_optional_spec(self):
        fields, _ = frontmatter(REVIEW)
        self.assertIn("spec", fields["argument-hint"])


class SpecReviewerSyncTests(unittest.TestCase):
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

    def test_sync_links_the_agent_and_uninstall_removes_it(self):
        self.assertEqual(self._sync(adopt=True), 0)
        link = self.home / ".claude" / "agents" / "spec-reviewer.md"
        self.assertTrue(link.is_symlink(), msg=str(link))
        self.assertEqual(link.resolve(), AGENT.resolve())
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse(link.exists() or link.is_symlink())


if __name__ == "__main__":
    unittest.main()
