# SPDX-License-Identifier: MIT
"""`stance-switch` and `custom-stance`: a communication stance, a project override, both observed.

Step 2 of the qualification procedure asks for a communication stance switched beside the
delegation one, and for a project override. The cases are driven here against a scripted home
whose client answers the way each selection says; no test launches a client.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from test_native_acceptance import MODULE

TABLE = "| type | mutable |\n|---|---|\n| list | yes |\n| tuple | no |\n| set | yes |"
PROSE = "A list is mutable and ordered.\n\n- A tuple is immutable.\n- A set is unordered."


class ScriptedHome(MODULE.Home):
    """A home whose sync links variants and whose client obeys the selection it would read."""

    def __init__(self, directory, voice=None, obey_override=True, attempt_off=True):
        self.root = Path(directory)
        self.client_dir = self.root / ".claude"
        self.primitives = self.root / "primitives"
        self.project = self.root / "project"
        self.project.mkdir(parents=True)
        self.runtime = "claude-code"
        self.home_var = "CLAUDE_CONFIG_DIR"
        self.keychain_error = None
        self.launched = 0
        self.last_code = 0
        self.data = {}
        self.voice = voice or {"scannable": TABLE, "answer-card": PROSE}
        self.obey_override = obey_override
        self.attempt_off = attempt_off
        self.turns = []

    def seed(self, stances=None, roots=(), **config):
        self.data = {"stances": dict(stances or {}), "primitive_roots": [str(r) for r in roots]}

    def config(self):
        return json.loads(json.dumps(self.data))

    def write_config(self, data):
        self.data = data

    def variant(self, dimension, name):
        base = self.primitives if dimension == "proof" else MODULE.ROOT / "primitives"
        return base / "stances" / dimension / (name + ".md")

    def harness(self, *args, **kwargs):
        expected = kwargs.pop("expected", 0)
        extra = kwargs.pop("extra", None) or {}
        if args[0] == "stances":
            stances = dict(self.data["stances"])
            if "HARNESS_PROJECT_CONFIG" in extra:
                project = json.loads(Path(extra["HARNESS_PROJECT_CONFIG"]).read_text())
                stances.update(project["stances"])
            return json.dumps({"stances": {k: {"variant": v, "behavior": ""}
                                           for k, v in stances.items()}})
        for dimension, name in self.data["stances"].items():
            if not self.variant(dimension, name).exists():
                assert expected == 1
                return "stance %s has no variant '%s'" % (dimension, name)
        links = self.client_dir / "rules" / "harness-stances"
        links.mkdir(parents=True, exist_ok=True)
        for dimension, name in self.data["stances"].items():
            link = links / (dimension + ".md")
            if os.path.lexists(str(link)):
                link.unlink()
            os.symlink(str(self.variant(dimension, name)), str(link))
        style = {"outputStyle": "Scannable"} if self.data["stances"].get("voice") == "scannable" \
            else {}
        (self.client_dir / "settings.json").write_text(json.dumps(style))
        return "sync complete"

    def session(self, prompt, tools=("Agent",), resume=None, timeout=0):
        env = self.env()
        stances = self.data["stances"]
        override = env.get("HARNESS_PROJECT_CONFIG")
        sid = "s%s" % len(self.turns)
        self.turns.append({"prompt": prompt, "cwd": self.project, "override": override, "id": sid})
        if prompt == MODULE.VOICE_PROMPT:
            reply = self.voice[stances["voice"]]
        elif prompt == MODULE.PROOF_PROMPT:
            proof = "plain" if override and self.obey_override else stances["proof"]
            reply = "OK\n" + proof.upper()
        else:
            refused = stances.get("delegation") == "off" and self.attempt_off
            reply = MODULE.DELEGATION_DENY if refused else ""
        return {"result": reply, "session_id": sid}

    def subagents(self, session_id):
        turn = [t for t in self.turns if t["id"] == session_id][0]
        return [({}, [])] if turn["prompt"] == MODULE.SPAWN_COUNT_PROMPT and \
            self.data["stances"].get("delegation") == "tiered" else []

    def transcript_path(self, session_id):
        path = self.root / (session_id + ".jsonl")
        path.write_text(json.dumps({"message": {"content": [{"type": "text", "text": "ok"}]}}))
        return path

    def orchestrator_text(self, session_id):
        turn = [t for t in self.turns if t["id"] == session_id][0]
        return MODULE.OVERRIDE_LINE if turn["override"] else ""


class Readers(unittest.TestCase):
    def test_a_markdown_table_is_told_from_prose_and_bullets(self):
        self.assertTrue(MODULE.has_table(TABLE))
        self.assertFalse(MODULE.has_table(PROSE))
        self.assertFalse(MODULE.has_table("a | b in prose\n---\n"))

    def test_the_voice_replies_pass_only_when_scannable_tables_and_answer_card_does_not(self):
        self.assertIsNone(MODULE.voice_verdict(TABLE, PROSE))
        with self.assertRaises(MODULE.Unverified):
            MODULE.voice_verdict(TABLE, TABLE)
        with self.assertRaises(MODULE.Unverified):
            MODULE.voice_verdict(PROSE, PROSE)
        with self.assertRaises(AssertionError):
            MODULE.voice_verdict(PROSE, TABLE)

    def test_each_shipped_voice_variant_names_its_own_table_rule(self):
        voice = MODULE.ROOT / "primitives" / "stances" / "voice"
        for name, rule in (("answer-card", "no tables"), ("scannable", "at most one table")):
            text = " ".join((voice / (name + ".md")).read_text().lower().split())
            self.assertIn(rule, text)

    def test_the_closing_word_is_the_last_line_bare(self):
        self.assertEqual(MODULE.closing_word("OK\n\n**Plain.**\n"), "PLAIN")
        self.assertEqual(MODULE.closing_word(""), "")

    def test_a_resolved_variant_is_read_past_any_leading_warning(self):
        output = 'warning: x\n{"stances": {"proof": {"variant": "plain"}}}'
        self.assertEqual(MODULE.resolved_variant(output, "proof"), "plain")
        self.assertEqual(MODULE.resolved_variant("not json", "proof"), "")


class Cases(unittest.TestCase):
    def home(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ScriptedHome(tmp.name, **kwargs)

    def test_stance_switch_observes_voice_and_delegation(self):
        home = self.home()
        text = MODULE.case_stance_switch(home)
        self.assertIn("scannable.md -> answer-card.md", text)
        self.assertIn("'at most one table' -> 'no tables'", text)
        self.assertIn("Scannable -> <unset>", text)
        self.assertIn("with a markdown table under scannable and with none under answer-card", text)
        self.assertIn("tiered.md -> off.md", text)

    def test_voice_replies_that_agree_are_unverified_but_delegation_is_still_read(self):
        home = self.home(voice={"scannable": PROSE, "answer-card": PROSE})
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_stance_switch(home)
        self.assertIn("without a table under both voice variants", str(caught.exception))
        self.assertIn("tiered.md -> off.md", str(caught.exception))

    def test_an_off_turn_that_never_attempts_the_spawn_is_unverified_not_failed(self):
        home = self.home(attempt_off=False)
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_stance_switch(home)
        self.assertIn("attempted no spawn", str(caught.exception))
        self.assertIn("scannable.md -> answer-card.md", str(caught.exception))

    def test_custom_stance_observes_the_project_override_inside_and_the_global_outside(self):
        home = self.home()
        text = MODULE.case_custom_stance(home)
        proof = [t for t in home.turns if t["prompt"] == MODULE.PROOF_PROMPT]
        inside, outside = proof[1], proof[2]
        self.assertEqual(inside["cwd"].name, "override-repo")
        self.assertTrue(inside["override"].endswith(MODULE.PROJECT_FILE))
        self.assertEqual(outside["cwd"], home.project)
        self.assertIsNone(outside["override"])
        self.assertEqual(home.project, outside["cwd"])
        self.assertNotIn("env", vars(home))
        self.assertIn("closed PLAIN", text)
        self.assertIn("closed TAGGED", text)
        self.assertIn("read tagged.md before and after", text)
        self.assertIn("has no variant 'nonesuch'", text)

    def test_an_override_the_turn_ignores_fails(self):
        home = self.home(obey_override=False)
        with self.assertRaisesRegex(AssertionError, "closed TAGGED like the turn outside"):
            MODULE.case_custom_stance(home)


if __name__ == "__main__":
    unittest.main()
