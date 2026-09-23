# SPDX-License-Identifier: MIT
"""Unit tests for the allow-plan-webfetch PreToolUse hook.

The hook approves WebFetch only while `permission_mode` is `plan`, and only for
http/https URLs. Every other case stays silent and falls through. It never denies.

Run: python3 -m unittest discover tests
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "allow-plan-webfetch.py"
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())


def run(payload):
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    ).stdout.strip()


def decision(url=None, mode="plan", tool="WebFetch", **extra):
    payload = {"tool_name": tool, "permission_mode": mode, "tool_input": {}}
    if url is not None:
        payload["tool_input"]["url"] = url
    payload.update(extra)
    out = run(payload)
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class PlanWebFetchTests(unittest.TestCase):
    def test_https_and_http_are_approved_in_plan_mode(self):
        for url in ("https://docs.example.com/x", "http://example.org/page"):
            with self.subTest(url=url):
                self.assertEqual(decision(url=url), "allow")

    def test_other_modes_fall_through(self):
        for mode in ("default", "acceptEdits", "auto", "bypassPermissions", "dontAsk", None):
            with self.subTest(mode=mode):
                self.assertIsNone(decision(url="https://example.com", mode=mode))

    def test_missing_mode_field_falls_through(self):
        out = run({"tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}})
        self.assertEqual(out, "")

    def test_non_web_schemes_fall_through(self):
        for url in ("file:///etc/passwd", "data:text/plain,hi", "ftp://x/y", "", "not-a-url"):
            with self.subTest(url=url):
                self.assertIsNone(decision(url=url))

    def test_other_tools_and_malformed_payloads_are_ignored(self):
        self.assertIsNone(decision(url="https://x", tool="Bash"))
        for payload in ("not json", "{}", ""):
            with self.subTest(payload=payload):
                self.assertEqual(
                    subprocess.run(
                        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
                    ).stdout.strip(),
                    "",
                )

    def test_hook_never_denies(self):
        # A disallowed case yields no decision, never a deny.
        self.assertIsNone(decision(url="file:///x"))

    def test_ownership_claims_the_hook_id(self):
        self.assertEqual(
            OWNERSHIP["claude"]["hook_ids"]["plan-webfetch"],
            {"event": "PreToolUse", "always": True},
        )


if __name__ == "__main__":
    unittest.main()
