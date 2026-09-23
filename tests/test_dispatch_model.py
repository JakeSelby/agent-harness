# SPDX-License-Identifier: MIT
"""The single-coordinator dispatch model: what sync registers, and what it will not read.

Registration is generated from `lifecycle.registration`, one command per lifecycle event, so the
committed settings template carries no hooks block at all. An entry written there by hand is
discarded unread, which is a silent failure worth a test rather than a comment.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import os
import shlex
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

from harness_core import lifecycle  # noqa: E402

loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
harness = importlib.util.module_from_spec(importlib.util.spec_from_loader("harness", loader))
loader.exec_module(harness)

TEMPLATE_PATH = REPO / "claude" / "settings.template.json"
TEMPLATE = json.loads(TEMPLATE_PATH.read_text())
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())

# Each hook id the ownership manifest claims, and the policy module the coordinator reaches it by.
# Ownership still names the policies, because what a user gets is still those decisions; only the
# registration in front of them collapsed to one entry per event.
POLICIES = {
    "readonly-bash": "allow-readonly-bash.py",
    "grade-bash": "grade-bash.py",
    "filter-output": "filter-output.py",
    "plan-webfetch": "allow-plan-webfetch.py",
    "tier-spawns": "tier-agent-spawns.py",
    "brief-guard": "brief-guard.py",
    "plan-card": "validate-plan-card.py",
    "neutralize": "neutralize-tool-output.py",
    "session": "harness-session.py",
    "stop-gate": "stop-gate.py",
    "usage-log": "usage-log.py",
}


class TemplateTests(unittest.TestCase):
    def test_the_committed_template_registers_no_hooks(self):
        self.assertNotIn("hooks", TEMPLATE)

    def test_no_retired_per_hook_entry_survives_anywhere_in_the_file(self):
        text = TEMPLATE_PATH.read_text()
        for hid, module in POLICIES.items():
            self.assertNotIn("# harness:" + hid, text, msg=hid)
            self.assertNotIn(module, text, msg=module)

    def test_sync_supplies_the_registration_the_coordinator_emits(self):
        self.assertEqual(harness.runtime_template()["hooks"],
                         lifecycle.registration(REPO, "claude-code")["hooks"])

    def test_the_template_is_otherwise_carried_through_unchanged(self):
        template = harness.runtime_template()
        for key, value in TEMPLATE.items():
            self.assertEqual(template[key], value, msg=key)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.hooks = harness.runtime_template()["hooks"]

    def test_one_command_per_event_and_nothing_else(self):
        self.assertEqual(sorted(self.hooks), sorted(lifecycle.EVENTS["claude-code"]))
        for event, entries in self.hooks.items():
            self.assertEqual(len(entries), 1, msg=event)
            self.assertEqual(len(entries[0]["hooks"]), 1, msg=event)
            self.assertIn("# harness:runtime-" + event.lower(),
                          entries[0]["hooks"][0]["command"], msg=event)

    def test_every_registered_command_names_a_script_that_exists(self):
        for event, entries in self.hooks.items():
            command = entries[0]["hooks"][0]["command"]
            parts = [p for p in shlex.split(command.split(" # ", 1)[0]) if not p.startswith("-")]
            script = Path(parts[-1])
            self.assertTrue(script.is_file(), msg=event + ": " + str(script))

    def test_every_owned_hook_id_still_has_its_policy_on_disk(self):
        self.assertEqual(sorted(POLICIES), sorted(OWNERSHIP["claude"]["hook_ids"]))
        for hid, module in POLICIES.items():
            self.assertTrue((REPO / "policy" / "hooks" / module).is_file(), msg=hid)
            self.assertIn(OWNERSHIP["claude"]["hook_ids"][hid]["event"], self.hooks, msg=hid)

    def test_hook_health_finds_every_registered_command(self):
        count, problems = harness.hook_health(harness.runtime_template())
        self.assertEqual(count, len(self.hooks))
        self.assertEqual(problems, [])


class StanceTests(unittest.TestCase):
    """A stance that once decided whether an entry was written now decides inside dispatch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plan = Path(self.tmp.name) / ".agent-harness" / "plans" / "no-card.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("# A plan with no Review Card\n\nJust prose.\n", encoding="utf-8")
        self.addCleanup(self.tmp.cleanup)

    def _context(self, variant):
        event = {"hook_event_name": "PostToolUse", "tool_name": "Write",
                 "tool_input": {"file_path": str(self.plan)},
                 "tool_response": {"filePath": str(self.plan)}}
        with unittest.mock.patch.dict(os.environ, {"HARNESS_STANCE_PLAN_CEREMONY": variant}):
            result = lifecycle.dispatch("claude-code", event)
        return result.get("hookSpecificOutput", {}).get("additionalContext", "")

    def test_the_plan_card_is_checked_under_review_card_and_not_under_light(self):
        self.assertIn("Review Card", self._context("review-card"))
        self.assertEqual(self._context("light"), "")


if __name__ == "__main__":
    unittest.main()
