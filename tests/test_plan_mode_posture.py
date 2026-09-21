# SPDX-License-Identifier: MIT
"""Plan mode investigates at the permission posture the user already selected.

Native plan mode prompts on every command the read-only grammar cannot prove, which turns a
`bypass` or `auto` posture into a prompt for each script, scratch redirect and test run taken
while planning. The coordinator answers those instead, and only those: a remote-mutating command
is execution rather than planning, an unreadable config is no posture at all, `manual` and
`inherit` keep today's behaviour, and Codex is untouched because its client rejects `allow`.

Every case writes its own configuration under a temporary home, so no test reads the real one.

Run: python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import harness  # noqa: F401  (puts `lib` on the path the way its siblings do)
from harness_core import lifecycle

CWD = "/work/repo"
# One command per grade, each taken from the grade-bash fixtures.
READ_ONLY = "git status"
LOCAL_WRITE = "python3 -m unittest discover tests"
REMOTE_WRITE = "gh issue create --title x --body y"
IRREVERSIBLE = "git push --force origin main"


class PlanModePostureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def configure(self, text=None, **keys):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(keys) if text is None else text, encoding="utf-8")

    def decide(self, tool="Bash", command=None, mode="plan", runtime="claude-code", **inputs):
        if command is not None:
            inputs["command"] = command
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": CWD,
                 "permission_mode": mode, "tool_input": inputs}
        env = {"HOME": str(self.home), "HARNESS_HOME": str(self.home)}
        with patch.dict(os.environ, env):
            out = lifecycle.dispatch(runtime, event)
        block = out.get("hookSpecificOutput", {})
        return block.get("permissionDecision"), block.get("permissionDecisionReason", "")

    # ------------------------------------------------------------------ bash, by grade

    def test_an_open_posture_answers_the_grades_plan_mode_would_prompt_on(self):
        for posture in ("bypass", "auto"):
            self.configure(permissions=posture)
            self.assertEqual(self.decide(command=READ_ONLY)[0], "allow", posture)
            decision, reason = self.decide(command=LOCAL_WRITE)
            self.assertEqual(decision, "allow", posture)
            self.assertIn("Plan-mode investigation", reason)

    def test_a_remote_mutating_command_is_execution_rather_than_planning(self):
        self.configure(permissions="bypass")
        decision, reason = self.decide(command=REMOTE_WRITE)
        self.assertEqual(decision, "ask")
        self.assertIn("execution rather than planning", reason)

    def test_the_irreversible_grade_is_unchanged_by_the_posture(self):
        answers = []
        for posture in ("bypass", "manual"):
            self.configure(permissions=posture)
            answers.append(self.decide(command=IRREVERSIBLE))
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[0][0], "ask")
        self.assertNotIn("Plan-mode", answers[0][1])

    def test_a_closed_posture_keeps_todays_behaviour(self):
        for posture in ("manual", "inherit"):
            self.configure(permissions=posture)
            for command in (LOCAL_WRITE, REMOTE_WRITE):
                self.assertIsNone(self.decide(command=command)[0], posture + " " + command)
            self.assertEqual(self.decide(command=READ_ONLY)[0], "allow", posture)

    def test_a_configuration_with_no_posture_at_all_is_a_closed_one(self):
        self.configure(stances={"autonomy": "execute"})
        self.assertIsNone(self.decide(command=LOCAL_WRITE)[0])

    def test_an_unreadable_configuration_widens_nothing(self):
        # The dispatcher already refuses the whole call on a config it cannot parse; what this
        # pins is that the posture question never answers "open" on a file nobody could read.
        self.configure(text="{not json")
        with patch.dict(os.environ, {"HOME": str(self.home), "HARNESS_HOME": str(self.home)}):
            self.assertFalse(lifecycle.investigating("claude-code", {"permission_mode": "plan"}))
            self.assertFalse(lifecycle.plan_allowed_tool("mcp__cortex__memory_search"))

    def test_nothing_changes_outside_plan_mode(self):
        self.configure(permissions="bypass")
        for mode in ("default", "acceptEdits"):
            self.assertIsNone(self.decide(command=LOCAL_WRITE, mode=mode)[0], mode)

    def test_codex_is_left_alone_because_its_client_rejects_allow(self):
        self.configure(permissions="bypass")
        self.assertIsNone(self.decide(command=LOCAL_WRITE, runtime="codex")[0])
        self.assertIsNone(self.decide(command=READ_ONLY, runtime="codex")[0])

    def test_a_stance_that_already_asks_outranks_the_plan_mode_allowance(self):
        self.configure(permissions="bypass", stances={"autonomy": "ask"})
        decision, reason = self.decide(command=LOCAL_WRITE)
        self.assertEqual(decision, "ask")
        self.assertNotIn("Plan-mode investigation", reason)

    def test_a_confirmed_remote_command_is_not_asked_about_twice(self):
        self.configure(permissions="bypass")
        marker = lifecycle.load("grade-bash").MARKER
        self.assertIsNone(self.decide(command=marker + " " + REMOTE_WRITE)[0])

    # ------------------------------------------------------------------ the tool glob list

    def test_a_listed_tool_is_allowed_and_an_unlisted_one_is_not(self):
        self.configure(permissions="bypass", plan_allow_tools=["mcp__cortex__memory_*"])
        decision, reason = self.decide(tool="mcp__cortex__memory_search", query="x")
        self.assertEqual(decision, "allow")
        self.assertIn("plan_allow_tools", reason)
        self.assertIsNone(self.decide(tool="mcp__cortex__action_log")[0])

    def test_the_list_is_empty_until_the_user_fills_it(self):
        self.configure(permissions="bypass")
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search")[0])
        self.configure(permissions="bypass", plan_allow_tools=[])
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search")[0])

    def test_the_posture_gate_and_plan_mode_both_bind_the_list(self):
        self.configure(permissions="manual", plan_allow_tools=["mcp__cortex__*"])
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search")[0])
        self.configure(permissions="bypass", plan_allow_tools=["mcp__cortex__*"])
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search", mode="default")[0])
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search", runtime="codex")[0])

    def test_entries_that_are_not_globs_are_ignored_rather_than_fatal(self):
        self.configure(permissions="bypass", plan_allow_tools=[3, None, "  ", {"a": 1}, "mcp__cortex__*"])
        self.assertEqual(self.decide(tool="mcp__cortex__memory_search")[0], "allow")
        self.configure(permissions="bypass", plan_allow_tools="mcp__cortex__*")
        self.assertIsNone(self.decide(tool="mcp__cortex__memory_search")[0])

    def test_the_list_never_reopens_a_tool_the_coordinator_already_governs(self):
        self.configure(permissions="bypass", plan_allow_tools=["*"])
        # Bash keeps its grades and Agent keeps its delegation guard; a wildcard is not a bypass.
        self.assertEqual(self.decide(command=REMOTE_WRITE)[0], "ask")
        with patch.object(lifecycle, "selected", return_value="off"):
            self.assertEqual(self.decide(tool="Agent", prompt="work")[0], "deny")

    # ------------------------------------------------------------------ the config reader

    def test_the_reader_reports_the_posture_and_the_globs(self):
        posture = lifecycle.load("posture")
        env = {"HARNESS_HOME": str(self.home)}
        self.assertEqual(posture.permissions(env), "inherit")
        self.assertEqual(posture.plan_allow_tools(env), [])
        self.configure(permissions=" bypass ", plan_allow_tools=[" mcp__x__y "])
        self.assertEqual(posture.permissions(env), "bypass")
        self.assertEqual(posture.plan_allow_tools(env), ["mcp__x__y"])



class ConfigSetTests(unittest.TestCase):
    def test_a_json_array_of_globs_is_stored_trimmed(self):
        self.assertEqual(harness.coerce_config_value("plan_allow_tools", '["mcp__docs__* ", "Grep"]'),
                         ["mcp__docs__*", "Grep"])

    def test_anything_else_is_refused_with_the_expected_shape(self):
        for value in ("mcp__docs__*", '"mcp__docs__*"', '["ok", 3]', '[""]', "{}"):
            with self.subTest(value=value), self.assertRaises(SystemExit) as cm:
                harness.coerce_config_value("plan_allow_tools", value)
            self.assertIn("JSON array", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
