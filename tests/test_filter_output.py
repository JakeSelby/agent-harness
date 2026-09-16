# SPDX-License-Identifier: MIT
"""Unit tests for the filter-output hook and its line filter.
Run: python3 -m unittest discover tests
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "filter-output.py"
FILTER = REPO / "claude" / "hooks" / "filter-lines.py"
TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())


def run_hook(payload):
    out = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )
    return out


def rewritten(command, **extra):
    tool_input = {"command": command}
    tool_input.update(extra)
    out = run_hook({"tool_name": "Bash", "tool_input": tool_input})
    if not out.stdout.strip():
        return None
    return json.loads(out.stdout)["hookSpecificOutput"]["updatedInput"]


def run_filter(text):
    out = subprocess.run([sys.executable, str(FILTER)], input=text, capture_output=True, text=True)
    return out.stdout


class RewriteTests(unittest.TestCase):
    def test_test_and_build_commands_are_rewritten(self):
        for command in ("pytest -q", "cargo test --release -p x", "cd sub && npm test"):
            with self.subTest(command=command):
                updated = rewritten(command)
                self.assertIsNotNone(updated)
                self.assertIn("set -o pipefail", updated["command"])
                self.assertIn("( %s )" % command, updated["command"])
                self.assertIn("filter-lines.py", updated["command"])

    def test_other_commands_are_left_alone(self):
        for command in ("git status", "pytest | tail -5", "pytest --watch", "cargo test > out.txt"):
            with self.subTest(command=command):
                self.assertIsNone(rewritten(command))

    def test_an_already_filtered_command_is_not_wrapped_twice(self):
        once = rewritten("pytest -q")["command"]
        self.assertIsNone(rewritten(once))

    def test_updated_input_preserves_the_other_keys(self):
        updated = rewritten("go test ./...", description="Run the suite", timeout=600)
        self.assertEqual(updated["description"], "Run the suite")
        self.assertEqual(updated["timeout"], 600)
        self.assertNotEqual(updated["command"], "go test ./...")

    def test_no_permission_decision_is_emitted(self):
        out = run_hook({"tool_name": "Bash", "tool_input": {"command": "pytest -q"}})
        self.assertNotIn("permissionDecision", out.stdout)

    def test_other_tools_and_malformed_input_are_ignored(self):
        for payload in ('{"tool_name":"Read","tool_input":{"command":"pytest"}}', "not json", "{}"):
            with self.subTest(payload=payload):
                out = subprocess.run(
                    [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
                )
                self.assertEqual(out.returncode, 0)
                self.assertEqual(out.stdout.strip(), "")


def pytest_run(passes=290):
    lines = [
        "tests/test_%03d.py::test_case_%03d PASSED                              [ %02d%%]"
        % (i, i, i * 100 // passes)
        for i in range(passes)
    ]
    lines += [
        "=================================== FAILURES ===================================",
        "_________________________________ test_broken __________________________________",
        "Traceback (most recent call last):",
        '  File "tests/test_broken.py", line 12, in test_broken',
        "    assert compute() == 4",
        "AssertionError: assert 3 == 4",
        "=========================== short test summary info ============================",
        "FAILED tests/test_broken.py::test_broken - AssertionError: assert 3 == 4",
        "======================== 1 failed, %d passed in 1.23s =========================" % passes,
    ]
    return "\n".join(lines) + "\n"


class FilterTests(unittest.TestCase):
    def test_failures_and_summary_survive_and_passes_do_not(self):
        out = run_filter(pytest_run())
        self.assertIn("FAILED tests/test_broken.py::test_broken", out)
        self.assertIn("1 failed, 290 passed", out)
        self.assertIn("AssertionError: assert 3 == 4", out)
        self.assertIn('File "tests/test_broken.py", line 12', out)
        self.assertNotIn("tests/test_000.py", out)
        self.assertLess(len(out.splitlines()), 100)

    def test_short_output_passes_through_unchanged(self):
        text = "building\nlinking\ndone\n"
        self.assertEqual(run_filter(text), text)

    def test_empty_input_produces_no_output(self):
        self.assertEqual(run_filter(""), "")

    def test_long_output_is_capped_with_a_marker(self):
        out = run_filter("\n".join("ERROR line %d" % i for i in range(400)) + "\n")
        lines = out.splitlines()
        self.assertEqual(len(lines), 201)
        self.assertIn("[filter-lines: 200 lines omitted]", lines)


@unittest.skipUnless(shutil.which("bash"), "bash is not available")
class PipelineTests(unittest.TestCase):
    def _run(self, command):
        updated = rewritten(command)
        self.assertIsNotNone(updated)
        return subprocess.run(
            ["bash", "-c", updated["command"]], capture_output=True, text=True, cwd=str(REPO)
        )

    def test_a_failing_command_keeps_its_non_zero_status(self):
        out = self._run("python3 -m unittest no_such_module_here")
        self.assertNotEqual(out.returncode, 0)

    def test_a_passing_command_keeps_status_zero(self):
        out = self._run("python3 -m unittest --help")
        self.assertEqual(out.returncode, 0)


class RegistrationTests(unittest.TestCase):
    def test_the_hook_is_registered_under_pre_tool_use(self):
        entries = [
            e for e in TEMPLATE["hooks"]["PreToolUse"]
            if any("# harness:filter-output" in h["command"] for h in e["hooks"])
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "Bash")
        self.assertEqual(len(entries[0]["hooks"]), 1)
        self.assertIn("filter-output.py", entries[0]["hooks"][0]["command"])

    def test_ownership_claims_the_hook_id(self):
        spec = OWNERSHIP["claude"]["hook_ids"]["filter-output"]
        self.assertEqual(spec, {"event": "PreToolUse", "always": True})


if __name__ == "__main__":
    unittest.main()
