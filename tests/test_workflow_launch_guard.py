# SPDX-License-Identifier: MIT
"""A `Workflow` launch is the one call the harness sees of a script's `agent()` spawns, so the
launch is logged, refused under `delegation: off`, and refused when the script names a constrained
role. Run: python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO  # noqa: F401  (puts lib/ on the path)
from harness_core import lifecycle

BANDS_ONLY = (
    "export const meta = { title: 'fan-out' };\n"
    "const [a, b] = await parallel([\n"
    "  agent('Summarise docs/usage.md in five bullets.', { label: 'a', agentType: 'worker-a' }),\n"
    "  agent('Implement the fix and commit once.', { label: 'b', agentType: \"builder\" }),\n"
    "  agent('List every TODO under lib/.', { label: 'reviewer-notes' }),\n"
    "]);\n"
)
NAMED = "await agent('Review the diff at /tmp/d.patch.', { label: 'named', agentType: 'reviewer' });\n"
QUOTED_KEY = 'await agent("Review it.", {"agentType": "spec-reviewer"});\n'
MARKED = "await agent('harness-role: reviewer\\nReview the diff at /tmp/d.patch.', { label: 'm' });\n"
TEMPLATE_MARKED = "await agent(`\nharness-role: gatherer\nFind every caller of load().\n`);\n"
COMPUTED = ("const kinds = ['worker-b', 'reviewer'];\n"
            "for (const k of kinds) await agent('Look at it.', { agentType: k });\n")
COMPUTED_BANDS = ("const kinds = ['worker-b', 'worker-c'];\n"
                  "for (const agentType of kinds) await agent('Look at it.', { agentType });\n")
COMPOUND = "await agent('Look at it.', { agentType: 'worker-a' && 'reviewer' });\n"
INTERPOLATED = ("const role = 'reviewer';\n"
                "await agent('Look at it.', { agentType: `${role}` });\n")
PROSE = "await agent('Act as a careful reviewer of docs/releasing.md.', { label: 'reviewer' });\n"


def decision(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecision")


def reason(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


class WorkflowLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base), "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()
        module = lifecycle.decisions()
        self.assertIsNotNone(module)
        # The config is cached per process; another test's config must not switch logging off.
        patch.object(module, "_CONFIG", [{}]).start()
        self.log = self.base / ".local" / "state" / "agent-harness" / "decisions.jsonl"

    def launch(self, runtime="claude-code", cwd=None, mode=None, **inputs):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Workflow",
                   "session_id": "wf-session", "cwd": str(cwd or self.base), "tool_input": inputs}
        if mode is not None:
            payload["permission_mode"] = mode
        return lifecycle.dispatch(runtime, payload)

    def rows(self):
        if not self.log.exists():
            return []
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        return [row for row in rows if row.get("point") == lifecycle.WORKFLOW_POINT]

    def test_a_plain_launch_writes_one_allow_row(self):
        result = self.launch(script=BANDS_ONLY)
        self.assertNotEqual(decision(result), "deny")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["deterministic_answer"], "allow")
        self.assertEqual(rows[0]["session_id"], "wf-session")
        self.assertEqual(rows[0]["input"], BANDS_ONLY, "the script as the hook judged it")

    def test_delegation_off_refuses_the_launch_with_a_reason(self):
        os.environ["HARNESS_STANCE_DELEGATION"] = "off"
        result = self.launch(script=BANDS_ONLY)
        self.assertEqual(decision(result), "deny")
        self.assertIn("Delegation is off", reason(result))
        self.assertEqual([r["deterministic_answer"] for r in self.rows()], ["deny"])

    def test_a_constrained_role_in_agent_type_is_refused_with_the_agent_refusal_sentence(self):
        for script, role in ((NAMED, "reviewer"), (QUOTED_KEY, "spec-reviewer")):
            with self.subTest(role=role):
                result = self.launch(script=script)
                self.assertEqual(decision(result), "deny")
                expected = lifecycle.role_instruction("claude-code", role, lifecycle.constrained_role(role))
                self.assertIn(expected, reason(result))
                self.assertIn("names `" + role + "` in agentType", reason(result))
                self.assertIn(lifecycle.CONFINEMENT_SENTENCE, reason(result))

    def test_the_refusal_matches_the_agent_tools_own(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "agent-session",
                   "tool_input": {"prompt": "Review the diff.", "subagent_type": "reviewer"}}
        agent = reason(lifecycle.dispatch("claude-code", payload))
        workflow = reason(self.launch(script=NAMED))
        tail = lifecycle.role_deny("claude-code", "reviewer",
                                   lifecycle.constrained_role("reviewer"))["hookSpecificOutput"]
        self.assertIn(tail["permissionDecisionReason"], agent)
        self.assertTrue(workflow.endswith(tail["permissionDecisionReason"]))

    def test_a_marker_for_a_constrained_role_is_refused(self):
        for script, role in ((MARKED, "reviewer"), (TEMPLATE_MARKED, "gatherer")):
            with self.subTest(role=role):
                result = self.launch(script=script)
                self.assertEqual(decision(result), "deny")
                self.assertIn("harness-role: " + role, reason(result))
                self.assertIn("harness role run " + role, reason(result))

    def test_band_workers_and_builder_only_are_allowed(self):
        for script in (BANDS_ONLY, COMPUTED_BANDS, PROSE):
            with self.subTest(script=script[:30]):
                self.assertNotEqual(decision(self.launch(script=script)), "deny")
        self.assertEqual({r["deterministic_answer"] for r in self.rows()}, {"allow"})

    def test_a_computed_agent_type_with_a_constrained_literal_is_refused(self):
        result = self.launch(script=COMPUTED)
        self.assertEqual(decision(result), "deny")
        self.assertIn("computes agentType", reason(result))

    def test_a_literal_that_is_not_the_whole_value_counts_as_computed(self):
        for script in (COMPOUND, INTERPOLATED):
            with self.subTest(script=script[:40]):
                result = self.launch(script=script)
                self.assertEqual(decision(result), "deny")
                self.assertIn("computes agentType", reason(result))

    def test_a_script_file_past_the_read_limit_is_refused(self):
        path = self.base / "long.js"
        padding = "// " + "x" * lifecycle.WORKFLOW_SCRIPT_MAX + "\n"
        path.write_text(BANDS_ONLY + padding + NAMED, encoding="utf-8")
        result = self.launch(scriptPath=str(path))
        self.assertEqual(decision(result), "deny")
        self.assertIn("longer than", reason(result))
        self.assertIn("long.js", self.rows()[0]["input"], "the row carries the tool input")
        path.write_text(BANDS_ONLY, encoding="utf-8")
        self.assertNotEqual(decision(self.launch(scriptPath=str(path))), "deny")

    def test_plan_mode_allows_a_listed_workflow_unless_the_guard_refuses_it(self):
        config = self.base / ".config" / "agent-harness" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"permissions": "bypass", "plan_allow_tools": ["Workflow"]}),
                          encoding="utf-8")
        allowed = self.launch(mode="plan", script=BANDS_ONLY)
        self.assertEqual(decision(allowed), "allow")
        self.assertIn("plan_allow_tools", reason(allowed))
        self.assertEqual(decision(self.launch(mode="plan", script=NAMED)), "deny")
        self.assertIsNone(decision(self.launch(script=BANDS_ONLY)), "outside plan mode")
        self.assertEqual([r["deterministic_answer"] for r in self.rows()], ["allow", "deny", "allow"])

    def test_a_marker_naming_no_constrained_role_says_nothing(self):
        script = "await agent('harness-role: worker-b\\nDo the thing.');\n"
        self.assertNotEqual(decision(self.launch(script=script)), "deny")

    def test_script_path_is_read_and_takes_precedence_over_script(self):
        path = self.base / "persisted.js"
        path.write_text(NAMED, encoding="utf-8")
        result = self.launch(scriptPath=str(path), script=BANDS_ONLY)
        self.assertEqual(decision(result), "deny")
        self.assertEqual(self.rows()[0]["input"], NAMED)
        relative = self.launch(scriptPath="persisted.js")
        self.assertEqual(decision(relative), "deny", "a relative path resolves against cwd")

    def test_a_named_workflow_resolves_under_claude_workflows(self):
        project = self.base / "project"
        workflows = project / ".claude" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "review-probe.js").write_text(MARKED, encoding="utf-8")
        self.assertEqual(decision(self.launch(cwd=project, name="review-probe")), "deny")
        user = self.base / ".claude" / "workflows"
        user.mkdir(parents=True)
        (user / "user-probe.js").write_text(NAMED, encoding="utf-8")
        self.assertEqual(decision(self.launch(cwd=project, name="user-probe")), "deny")

    def test_an_unreadable_script_is_logged_with_its_tool_input(self):
        result = self.launch(scriptPath=str(self.base / "missing.js"))
        self.assertNotEqual(decision(result), "deny")
        row = self.rows()[0]
        self.assertEqual(row["deterministic_answer"], "allow")
        self.assertIn("missing.js", row["input"])

    def test_logging_off_changes_no_answer(self):
        patch.object(lifecycle.decisions(), "_CONFIG", [{"telemetry": {"decisions": False}}]).start()
        self.assertEqual(decision(self.launch(script=NAMED)), "deny")
        self.assertEqual(self.rows(), [])

    def test_codex_gets_the_same_refusal(self):
        result = self.launch(runtime="codex", script=NAMED)
        self.assertEqual(decision(result), "deny")
        self.assertIn("harness role run reviewer --runtime codex", reason(result))


if __name__ == "__main__":
    unittest.main()
