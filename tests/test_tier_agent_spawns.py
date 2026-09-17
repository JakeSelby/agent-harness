# SPDX-License-Identifier: MIT
"""Unit tests for the tier-agent-spawns PreToolUse hook.

The hook runs as a subprocess with HOME pointed at a temporary directory carrying the config
and settings each case needs, and a transcript file standing in for the session's.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())


def record(kind, model=None, sidechain=False):
    message = {"role": kind}
    if model:
        message["model"] = model
    entry = {"type": kind, "message": message}
    if sidechain:
        entry["isSidechain"] = True
    return json.dumps(entry)


class TierSpawnsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "session.jsonl"
        self.config("tiered")

    def config(self, delegation):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"stances": {"delegation": delegation}}))

    def settings(self, model):
        d = self.home / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps({"model": model}))

    def write_transcript(self, *lines):
        self.transcript.write_text("\n".join(lines) + "\n")

    def run_hook(self, payload, env=None):
        merged = dict(os.environ)
        merged.pop("HARNESS_STANCE_DELEGATION", None)
        merged["HOME"] = str(self.home)
        merged.update(env or {})
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        out = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True,
                             text=True, env=merged)
        self.assertEqual(out.returncode, 0, out.stderr)
        if not out.stdout.strip():
            return None
        return json.loads(out.stdout)

    def spawn(self, **tool_input):
        return {"tool_name": "Agent", "transcript_path": str(self.transcript), "tool_input": tool_input}

    def rewritten(self, payload, env=None):
        out = self.run_hook(payload, env)
        return out["hookSpecificOutput"]["updatedInput"]["model"] if out else None

    # --- tiered ---
    def test_bare_spawn_runs_one_tier_below_the_session(self):
        cases = (("claude-fable-5-1", "opus"), ("claude-opus-5", "sonnet"), ("claude-sonnet-5", "haiku"))
        for session, below in cases:
            with self.subTest(session=session):
                self.write_transcript(record("user"), record("assistant", session))
                out = self.run_hook(self.spawn(prompt="x", description="d"))
                updated = out["hookSpecificOutput"]["updatedInput"]
                self.assertEqual(updated["model"], below)
                self.assertEqual(updated["prompt"], "x")
                self.assertEqual(updated["description"], "d")
                self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
                self.assertIn(below, out["systemMessage"])

    def test_general_purpose_counts_as_bare(self):
        self.write_transcript(record("assistant", "claude-opus-5"))
        self.assertEqual(self.rewritten(self.spawn(prompt="x", subagent_type="general-purpose")), "sonnet")

    def test_named_agent_and_explicit_model_are_left_alone(self):
        self.write_transcript(record("assistant", "claude-opus-5"))
        for tool_input in ({"subagent_type": "reviewer"}, {"subagent_type": "Explore"},
                           {"model": "opus"}, {"subagent_type": "general-purpose", "model": "haiku"}):
            with self.subTest(tool_input=tool_input):
                self.assertIsNone(self.run_hook(self.spawn(prompt="x", **tool_input)))

    def test_haiku_is_the_floor(self):
        self.write_transcript(record("assistant", "claude-haiku-4-5-20251001"))
        self.assertIsNone(self.run_hook(self.spawn(prompt="x")))

    def test_newest_main_line_assistant_record_wins(self):
        self.write_transcript(
            record("assistant", "claude-fable-5-1"),
            record("assistant", "claude-haiku-4-5-20251001", sidechain=True),
            record("assistant", "<synthetic>"),
            record("user"),
        )
        self.assertEqual(self.rewritten(self.spawn(prompt="x")), "opus")

    def test_no_assistant_record_means_untouched_whatever_settings_say(self):
        # The settings model is a default the session may not be running on; guessing from it
        # would mis-tier the first spawn of a session started with --model or switched with /model.
        self.settings("opus")
        self.write_transcript(record("user"))
        self.assertIsNone(self.run_hook(self.spawn(prompt="x")))

    def test_missing_transcript_falls_through(self):
        payload = self.spawn(prompt="x")
        payload["transcript_path"] = str(self.home / "absent.jsonl")
        self.assertIsNone(self.run_hook(payload))
        del payload["transcript_path"]
        self.assertIsNone(self.run_hook(payload))

    # --- other stances ---
    def test_session_model_stance_never_rewrites(self):
        self.config("session-model")
        self.write_transcript(record("assistant", "claude-opus-5"))
        self.assertIsNone(self.run_hook(self.spawn(prompt="x")))

    def test_off_asks_before_every_spawn(self):
        self.config("off")
        self.write_transcript(record("assistant", "claude-opus-5"))
        for tool_input in ({}, {"subagent_type": "gatherer"}, {"model": "opus"}):
            with self.subTest(tool_input=tool_input):
                out = self.run_hook(self.spawn(prompt="x", **tool_input))["hookSpecificOutput"]
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertNotIn("updatedInput", out)

    def test_env_override_beats_config(self):
        self.write_transcript(record("assistant", "claude-opus-5"))
        self.assertIsNone(self.run_hook(self.spawn(prompt="x"),
                                        env={"HARNESS_STANCE_DELEGATION": "session-model"}))
        out = self.run_hook(self.spawn(prompt="x"), env={"HARNESS_STANCE_DELEGATION": "off"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_missing_config_defaults_to_tiered(self):
        (self.home / ".config" / "agent-harness" / "config.json").unlink()
        self.write_transcript(record("assistant", "claude-opus-5"))
        self.assertEqual(self.rewritten(self.spawn(prompt="x")), "sonnet")

    # --- robustness ---
    def test_other_tools_and_malformed_payloads_are_ignored(self):
        self.write_transcript(record("assistant", "claude-opus-5"))
        self.assertIsNone(self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        for raw in ("not json", "{}", "", "[]", '{"tool_name":"Agent","tool_input":"x"}'):
            with self.subTest(raw=raw):
                self.assertIsNone(self.run_hook(raw))

    def test_settings_template_registers_the_hook(self):
        entries = [
            e for e in TEMPLATE["hooks"]["PreToolUse"]
            if any("# harness:tier-spawns" in h["command"] for h in e["hooks"])
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "Agent")
        self.assertIn("tier-agent-spawns.py", entries[0]["hooks"][0]["command"])

    def test_ownership_claims_the_hook_id(self):
        self.assertEqual(OWNERSHIP["claude"]["hook_ids"]["tier-spawns"],
                         {"event": "PreToolUse", "always": True})


if __name__ == "__main__":
    unittest.main()
