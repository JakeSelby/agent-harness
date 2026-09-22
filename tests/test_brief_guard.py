# SPDX-License-Identifier: MIT
"""Unit tests for the `brief-guard` PreToolUse hook.

Run: python3 -m unittest discover tests
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "brief-guard.py"


def detectors():
    spec = importlib.util.spec_from_file_location(
        "harness_rule_detectors", str(REPO / "claude" / "hooks" / "rule-detectors.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self, delegation):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"stances": {"delegation": delegation}}))

    def run_hook(self, payload, env_extra=None):
        env = without_harness_vars()
        env["HOME"] = str(self.home)
        env.update(env_extra or {})
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    @staticmethod
    def spawn(prompt, subagent_type=None):
        tool_input = {"prompt": prompt}
        if subagent_type:
            tool_input["subagent_type"] = subagent_type
        return {"tool_name": "Agent", "tool_input": tool_input}


class AppendsTheBound(HookRun):
    def test_a_brief_with_no_cap_gets_one(self):
        self.write_config("tiered")
        out = self.run_hook(self.spawn("Find every call site of parse_row."))
        self.assertIsNotNone(out, "the hook should have rewritten this brief")
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("Find every call site of parse_row.", prompt)
        self.assertIn("at most 400 words", prompt)

    def test_the_appended_bound_satisfies_the_detector(self):
        """A bound the detector cannot see is not a bound, and the metric would never move."""
        self.write_config("tiered")
        out = self.run_hook(self.spawn("do a thing"))
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertTrue(detectors().WORD_CAP_RE.search(prompt),
                        "brief-guard appended text that rule-detectors still counts as uncapped")

    def test_other_fields_are_preserved(self):
        self.write_config("tiered")
        payload = self.spawn("do a thing", "general-purpose")
        payload["tool_input"]["model"] = "sonnet"
        out = self.run_hook(payload)
        updated = out["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "sonnet")
        self.assertEqual(updated["subagent_type"], "general-purpose")


class LeavesAlone(HookRun):
    def test_a_brief_that_already_states_a_cap(self):
        self.write_config("tiered")
        for prompt in ("Summarize it in at most 200 words.", "Return a 300 word cap summary.",
                       "Reply with no more than 50 words."):
            with self.subTest(prompt=prompt):
                self.assertIsNone(self.run_hook(self.spawn(prompt)))

    def test_an_agent_whose_definition_carries_a_cap(self):
        # The definition states the bound, so the brief never repeats it. A budget is a separate
        # question: a priced role still gets its spend sentence, which `test_brief_budget` holds.
        self.write_config("tiered")
        for kind in sorted(detectors().CAPPED_AGENTS):
            with self.subTest(agent=kind):
                out = self.run_hook(self.spawn("do a thing", kind))
                prompt = "" if out is None else out["hookSpecificOutput"]["updatedInput"]["prompt"]
                self.assertNotIn("400 words", prompt)

    def test_delegation_off_is_a_no_op(self):
        self.write_config("off")
        self.assertIsNone(self.run_hook(self.spawn("do a thing")))

    def test_the_env_override_also_turns_it_off(self):
        self.write_config("tiered")
        self.assertIsNone(self.run_hook(self.spawn("do a thing"),
                                        {"HARNESS_STANCE_DELEGATION": "off"}))

    def test_a_non_agent_tool(self):
        self.write_config("tiered")
        self.assertIsNone(self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_an_empty_or_missing_prompt(self):
        self.write_config("tiered")
        self.assertIsNone(self.run_hook({"tool_name": "Agent", "tool_input": {"prompt": "  "}}))
        self.assertIsNone(self.run_hook({"tool_name": "Agent", "tool_input": {}}))

    def test_a_missing_config_still_guards(self):
        self.assertIsNotNone(self.run_hook(self.spawn("do a thing")))


class MalformedInput(HookRun):
    def test_garbage_does_not_raise(self):
        self.write_config("tiered")
        env = without_harness_vars()
        env["HOME"] = str(self.home)
        for payload in ("", "not json", "[]", '{"tool_name": "Agent", "tool_input": []}'):
            with self.subTest(payload=payload):
                out = subprocess.run([sys.executable, str(HOOK)], input=payload,
                                     capture_output=True, text=True, env=env)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertNotIn("Traceback", out.stderr)


class Registration(unittest.TestCase):
    def test_registered_on_the_agent_event(self):
        s = json.loads((REPO / "claude" / "settings.template.json").read_text())
        cmds = [h["command"] for g in s["hooks"]["PreToolUse"]
                if g.get("matcher") == "Agent" for h in g["hooks"]]
        self.assertTrue(any("brief-guard.py # harness:brief-guard" in c for c in cmds), cmds)

    def test_declared_in_ownership(self):
        o = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())
        entry = o["claude"]["hook_ids"].get("brief-guard")
        self.assertEqual(entry, {"event": "PreToolUse", "always": True})

    def test_the_hook_is_executable(self):
        self.assertTrue(os.access(HOOK, os.X_OK))


if __name__ == "__main__":
    unittest.main()
