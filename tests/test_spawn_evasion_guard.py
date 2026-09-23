# SPDX-License-Identifier: MIT
"""Confinement survives the name the model chose: a refused brief stays refused, and a brief
that declares its role is refused however it is spawned. What a brief is recognised as on its
content alone belongs to `test_framework_spawn_confinement.py`; these cases use work no
descriptor classifies, so the memory and the marker are the only things under test. Run: python3 -m unittest discover tests
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO, harness
from harness_core import lifecycle, workers

# Work a constrained role would be spawned for, written so no shipped integration descriptor
# classifies it: what the guards under test do must not depend on a framework recognising it.
BRIEF = ("Read notes.md and the three modules it names, then say which behaviour the notes "
         "describe that the modules do not implement, and which of them no test exercises. "
         "Read the neighbouring tests before you answer, and do not change any file. Return a "
         "short bulleted list and nothing else; if notes.md is missing, say so and stop. "
         "Name every file you read and every assumption the notes forced you to make.")
OTHER = ("Summarise the release notes under docs/ and list the three changes a new contributor "
         "would most likely trip over. Return a bulleted list and nothing else.")


def decision(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecision")


def reason(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


class SpawnGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base), "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()

    def spawn(self, prompt, role=None, session="session-one", runtime="claude-code"):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": session,
                   "tool_input": {"prompt": prompt, "subagent_type": role}}
        return lifecycle.dispatch(runtime, payload)

    # --- evade-after-deny ---

    def test_a_named_constrained_spawn_is_denied_and_remembered(self):
        result = self.spawn(BRIEF, role="reviewer")
        self.assertEqual(decision(result), "deny")
        self.assertIn("requires an isolated worker", reason(result))
        remembered = lifecycle.denied_spawns("session-one")
        self.assertEqual([entry["role"] for entry in remembered], ["reviewer"])
        self.assertEqual(remembered[0]["prompt"], lifecycle.fingerprint(BRIEF))

    def test_the_same_brief_respawned_without_a_role_is_denied_with_the_evasion_reason(self):
        self.spawn(BRIEF, role="reviewer")
        for role in (None, "general-purpose", "worker-a"):
            with self.subTest(role=role):
                result = self.spawn(BRIEF, role=role)
                self.assertEqual(decision(result), "deny")
                self.assertIn("refused as a native reviewer spawn in this session", reason(result))
                self.assertIn("dropping or changing the role name does not change that", reason(result))
                self.assertIn("harness role run reviewer", reason(result))

    def test_a_reworded_brief_is_still_the_same_refused_work(self):
        self.spawn(BRIEF, role="spec-reviewer")
        edited = BRIEF + " Also flag any test that asserts nothing."
        self.assertEqual(decision(self.spawn(edited)), "deny")
        self.assertIn("refused as a native spec-reviewer spawn", reason(self.spawn(edited)))
        # Whitespace and case are not a disguise either.
        shouted = "\n\n".join(BRIEF.upper().split(". "))
        self.assertEqual(decision(self.spawn(shouted)), "deny")

    def test_unrelated_work_after_a_denial_still_runs(self):
        self.spawn(BRIEF, role="reviewer")
        self.assertNotEqual(decision(self.spawn(OTHER)), "deny")

    def test_an_unnamed_spawn_with_nothing_behind_it_runs(self):
        self.assertNotEqual(decision(self.spawn(OTHER)), "deny")

    def test_the_memory_does_not_cross_sessions(self):
        self.spawn(OTHER, role="reviewer", session="session-one")
        self.assertNotEqual(decision(self.spawn(OTHER, session="session-two")), "deny")
        self.assertNotEqual(decision(self.spawn(OTHER, session=None)), "deny")

    def test_state_that_cannot_be_read_or_written_behaves_as_it_did_before_the_guard(self):
        real = lifecycle.load

        class Broken(object):
            def __init__(self, module):
                self._module = module

            def __getattr__(self, name):
                return getattr(self._module, name)

            def read_session_record(self, *args, **kwargs):
                raise OSError("state is unreadable")

            def write_session_record(self, *args, **kwargs):
                raise OSError("state is unwritable")

        def load(name):
            return Broken(real(name)) if name == "posture" else real(name)

        with patch.object(lifecycle, "load", load):
            self.assertEqual(decision(self.spawn(OTHER, role="reviewer")), "deny")
            self.assertNotEqual(decision(self.spawn(OTHER)), "deny")

    def test_a_record_the_guard_cannot_parse_is_a_session_with_no_memory(self):
        self.spawn(OTHER, role="reviewer")
        path = lifecycle.load("posture").session_record_path("session-one")
        path.write_text("{ not json", encoding="utf-8")
        self.assertEqual(lifecycle.denied_spawns("session-one"), [])
        self.assertNotEqual(decision(self.spawn(OTHER)), "deny")

    def test_the_memory_is_bounded_and_keeps_the_newest(self):
        for index in range(lifecycle.DENIED_MAX + 4):
            self.spawn(BRIEF + " Variation " + str(index) + ".", role="reviewer")
        remembered = lifecycle.denied_spawns("session-one")
        self.assertEqual(len(remembered), lifecycle.DENIED_MAX)
        self.assertIn("variation " + str(lifecycle.DENIED_MAX + 3), remembered[-1]["prompt"])

    def test_the_off_stance_keeps_its_own_single_refusal(self):
        with patch.dict(os.environ, {"HARNESS_STANCE_DELEGATION": "off"}):
            result = self.spawn(BRIEF, role="reviewer")
            self.assertEqual(decision(result), "deny")
            self.assertIn("Delegation is off", reason(result))
            self.assertEqual(lifecycle.denied_spawns("session-one"), [])
            self.assertEqual(decision(self.spawn(BRIEF)), "deny")

    # --- role marker ---

    def test_a_declared_role_is_enforced_whatever_the_spawn_calls_itself(self):
        marked = "harness-role: reviewer\n" + BRIEF
        for role in (None, "general-purpose", "worker-b", "builder"):
            with self.subTest(role=role):
                result = self.spawn(marked, role=role, session="marker-" + str(role))
                self.assertEqual(decision(result), "deny")
                self.assertIn("requires an isolated worker", reason(result))
                self.assertIn("harness role run reviewer", reason(result))

    def test_a_marker_naming_no_constrained_role_says_nothing(self):
        for line in ("harness-role: no-such-role", "harness-role: builder", "harness-role: Reviewer",
                     "the brief says harness-role: reviewer inline", "harness-role: ../reviewer"):
            with self.subTest(line=line):
                self.assertNotEqual(decision(self.spawn(line + "\n" + OTHER, session="m")), "deny")

    def test_the_shipped_review_layers_carry_the_marker_their_launch_sentence_protects(self):
        text = (REPO / "templates/bmad/custom/bmad-code-review.user.toml").read_text(encoding="utf-8")
        self.assertEqual(text.count("keep the brief's first line unchanged"), 4)
        self.assertEqual(text.count("\nharness-role: reviewer\n"), 3)
        self.assertEqual(text.count("\nharness-role: spec-reviewer\n"), 1)
        for name in lifecycle.ROLE_MARKER.findall(text):
            self.assertIsNotNone(lifecycle.constrained_role(name))

    def test_a_worker_run_accepts_a_brief_that_carries_its_marker(self):
        prompt_file = self.base / "brief.md"
        prompt_file.write_text("harness-role: reviewer\n" + BRIEF, encoding="utf-8")
        seen = {}

        def run(root, config, runtime, name, workspace, prompt, state_root, **kwargs):
            seen["prompt"] = prompt
            return {"status": "completed", "id": "fixture"}

        args = harness.argparse.Namespace(
            action="run", name="reviewer", runtime="codex", workspace=str(self.base),
            prompt_file=str(prompt_file), model=None, artifact=None, timeout=300, read_dir=[])
        with patch.object(workers, "run", run), patch.dict(os.environ, {"HARNESS_QUIET": "1"}):
            self.assertEqual(harness.cmd_role(args), 0)
        self.assertTrue(seen["prompt"].startswith("harness-role: reviewer\n"))


class MatchingTests(unittest.TestCase):
    def test_fingerprints_normalise_whitespace_case_and_length(self):
        self.assertEqual(lifecycle.fingerprint("  A\tB\n\nC "), "a b c")
        self.assertEqual(lifecycle.fingerprint(None), "")
        self.assertEqual(len(lifecycle.fingerprint("word " * 3000)), lifecycle.FINGERPRINT_MAX)

    def test_matching_covers_equality_long_containment_and_similarity(self):
        base = lifecycle.fingerprint(BRIEF)
        self.assertTrue(lifecycle.same_work(base, base))
        self.assertTrue(lifecycle.same_work(base, lifecycle.fingerprint("Preamble. " + BRIEF + " Tail.")))
        self.assertTrue(lifecycle.same_work(base, lifecycle.fingerprint(BRIEF + " One more sentence.")))
        self.assertFalse(lifecycle.same_work(base, lifecycle.fingerprint(OTHER)))
        self.assertFalse(lifecycle.same_work(base, ""))
        # A short brief is never matched by containment alone; similarity has to carry it.
        self.assertFalse(lifecycle.same_work("review it", lifecycle.fingerprint(OTHER) + " review it"))


if __name__ == "__main__":
    unittest.main()
