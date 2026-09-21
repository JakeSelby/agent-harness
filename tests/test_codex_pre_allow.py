# SPDX-License-Identifier: MIT
"""Codex PreToolUse envelopes stay silent where the client's default already allows.

A Codex client lists `allow` as an unsupported `permissionDecision` and discards the whole hook
output when it sees one, reporting `hook: PreToolUse Failed` on every permitted call and masking
the failures that matter. Absence of a decision is that client's default allow, so the harness
says nothing unless it is denying or sending a rewrite, which Codex only applies under `allow`.
Claude Code's envelope is unchanged.

Run: python3 -m unittest discover tests
"""
import unittest
from harness_core import lifecycle


def encode(runtime, original, results):
    return lifecycle.encode_pre(runtime, original, lifecycle.normalize(original), results)


class CodexPreAllowTests(unittest.TestCase):
    def test_codex_plain_approval_emits_no_permission_decision(self):
        original = {"tool_name": "exec_command", "tool_input": {"cmd": "ls"}}
        result = encode("codex", original, [{"hookSpecificOutput": {"permissionDecision": "allow"}}, {}])
        self.assertEqual(result, {})

    def test_codex_deny_and_ask_are_unchanged(self):
        original = {"tool_name": "exec_command", "tool_input": {"cmd": "git push"}}
        denied = encode("codex", original, [{"hookSpecificOutput": {
            "permissionDecision": "deny", "permissionDecisionReason": "pushes are gated"}}])
        self.assertEqual(denied, {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                        "permissionDecision": "deny",
                                                        "permissionDecisionReason": "pushes are gated"}})
        asked = encode("codex", original, [{"hookSpecificOutput": {
            "permissionDecision": "ask", "permissionDecisionReason": "confirm"}}])
        self.assertEqual(asked["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_codex_rewrite_still_carries_allow(self):
        original = {"tool_name": "exec_command", "tool_input": {"cmd": "make"}}
        result = encode("codex", original, [{"hookSpecificOutput": {
            "permissionDecision": "allow", "updatedInput": {"command": "make | filter"}}}])
        fields = result["hookSpecificOutput"]
        self.assertEqual(fields["permissionDecision"], "allow")
        self.assertEqual(fields["updatedInput"], {"cmd": "make | filter"})

    def test_claude_code_approval_is_unchanged(self):
        original = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        self.assertEqual(encode("claude-code", original, [{"hookSpecificOutput": {
            "permissionDecision": "allow", "permissionDecisionReason": "read-only"}}]),
            {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                    "permissionDecisionReason": "read-only"}})


if __name__ == "__main__":
    unittest.main()
