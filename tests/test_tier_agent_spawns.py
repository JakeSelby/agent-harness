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

    # --- the top tier is a role's to declare, never a spawn's to request ---
    def test_an_unnamed_spawn_asking_for_the_top_tier_runs_one_class_below_it(self):
        for session in ("claude-fable-5-1", "claude-opus-5", None):
            with self.subTest(session=session):
                self.write_transcript(*([record("assistant", session)] if session else [record("user")]))
                for kind in ({}, {"subagent_type": "general-purpose"}):
                    out = self.run_hook(self.spawn(prompt="x", model="fable", **kind))
                    self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["model"], "opus")
                    self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["prompt"], "x")
                    self.assertIn("role that declares it", out["systemMessage"])

    def agent(self, root, name, model):
        d = root / ".claude" / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / (name + ".md")).write_text(f"---\nname: {name}\ndescription: model: fable is not this line\nmodel: {model}\n---\n\nmodel: fable\n")

    def test_a_named_agent_asked_onto_the_top_tier_gets_the_model_its_definition_names(self):
        self.write_transcript(record("assistant", "claude-fable-5-1"))
        self.agent(self.home, "reviewer", "opus")
        self.agent(self.home, "spec-reviewer", "sonnet")
        self.agent(self.home, "inheritor", "inherit")
        # No definition to read (a built-in agent), one that inherits, and a name that is not a file name
        # all land on the class below the top. The request is rewritten, never removed.
        for kind, expected in (("reviewer", "opus"), ("spec-reviewer", "sonnet"), ("inheritor", "opus"),
                               ("Explore", "opus"), ("../reviewer", "opus")):
            with self.subTest(kind=kind):
                out = self.run_hook(self.spawn(prompt="x", subagent_type=kind, model="fable"))
                updated = out["hookSpecificOutput"]["updatedInput"]
                self.assertEqual(updated["model"], expected)
                self.assertEqual(updated["subagent_type"], kind)
                self.assertIn(expected, out["systemMessage"])

    def test_a_role_that_declares_the_top_tier_keeps_it_and_the_project_definition_wins(self):
        self.write_transcript(record("assistant", "claude-fable-5-1"))
        self.agent(self.home, "design-judge", "fable")
        self.assertIsNone(self.run_hook(self.spawn(prompt="x", subagent_type="design-judge", model="fable")))
        project = self.home / "project"
        self.agent(self.home, "designer", "opus")
        self.agent(project, "designer", "fable")
        payload = dict(self.spawn(prompt="x", subagent_type="designer", model="fable"), cwd=str(project))
        self.assertIsNone(self.run_hook(payload))
        self.assertEqual(self.rewritten(self.spawn(prompt="x", subagent_type="designer", model="fable")), "opus")

    def test_the_top_tier_request_stands_under_the_session_model_stance(self):
        self.write_transcript(record("assistant", "claude-fable-5-1"))
        self.assertIsNone(self.run_hook(self.spawn(prompt="x", model="fable"),
                                        env={"HARNESS_STANCE_DELEGATION": "session-model"}))

    def test_the_ladder_is_the_claude_adapters_tier_table(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tier_agent_spawns", HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        sys.path.insert(0, str(REPO / "lib"))
        from harness_core import catalog
        tiers = json.loads((REPO / "adapters" / "claude-code" / "bindings.json").read_text())["tiers"]
        self.assertEqual(hook.LADDER, [tiers[name] for name in catalog.TIER_CLASSES])

    def test_a_session_model_off_the_ladder_is_left_alone_out_loud(self):
        self.write_transcript(record("assistant", "claude-opus-5"), record("assistant", "claude-nova-7"))
        out = self.run_hook(self.spawn(prompt="x"))
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("claude-nova-7", out["systemMessage"])
        self.assertIn("not on the ladder", out["systemMessage"])
        # A placeholder record is not a model: the real one behind it still decides.
        self.write_transcript(record("assistant", "claude-opus-5"), record("assistant", "<synthetic>"))
        self.assertEqual(self.rewritten(self.spawn(prompt="x")), "sonnet")

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

    # --- framework repositories ---
    def framework(self, *parts):
        root = self.home / "repo"
        root.joinpath(*parts).mkdir(parents=True, exist_ok=True)
        return root

    def test_a_framework_repo_is_tiered_like_any_other(self):
        self.write_transcript(record("assistant", "claude-fable-5-1"))
        for marker in (("_bmad", "scripts"), ("_bmad", "core"), ("_bmad", "custom")):
            with self.subTest(marker=marker):
                nested = self.framework(*marker) / "crates" / "core"
                nested.mkdir(parents=True, exist_ok=True)
                self.assertEqual(self.rewritten(dict(self.spawn(prompt="x"), cwd=str(nested))), "opus")

    def test_a_missing_or_malformed_cwd_is_tiered_as_usual(self):
        self.write_transcript(record("assistant", "claude-opus-5"))
        for cwd in (str(self.home / "nowhere"), 42, None):
            with self.subTest(cwd=cwd):
                self.assertEqual(self.rewritten(dict(self.spawn(prompt="x"), cwd=cwd)), "sonnet")

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
