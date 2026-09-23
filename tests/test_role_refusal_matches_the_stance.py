# SPDX-License-Identifier: MIT
"""The refusal, the `delegation` stance and the shared role descriptions say one thing.

A session that follows the stance and spawns `gatherer` or `reviewer` natively meets a refusal;
these cases hold the three texts to the same sentence, so the refusal repeats what the stance
already said instead of contradicting it, and to the claim that sentence makes about `builder`.
Run: python3 -m unittest discover tests
"""
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO
from harness_core import lifecycle

SENTENCE = lifecycle.CONFINEMENT_SENTENCE
READ_ONLY = ("gatherer", "reviewer")


def flat(text):
    """The text with every run of whitespace collapsed, so a wrapped copy still matches."""
    return re.sub(r"\s+", " ", text).strip()


class SharedSentenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": self.temp.name, "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()

    def refusal(self, name, runtime="claude-code"):
        fields = lifecycle.constrained_role(name)
        self.assertIsNotNone(fields, name + " is no longer held to an isolated worker")
        result = lifecycle.role_deny(runtime, name, fields)
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_the_refusal_for_every_read_only_role_carries_the_sentence(self):
        for name in READ_ONLY:
            for runtime in ("claude-code", "codex"):
                with self.subTest(role=name, runtime=runtime):
                    self.assertIn(SENTENCE, self.refusal(name, runtime))
                    self.assertIn("harness role run " + name, self.refusal(name, runtime))

    def test_the_delegation_stance_carries_the_same_sentence(self):
        stance = (REPO / "primitives/stances/delegation/tiered.md").read_text(encoding="utf-8")
        self.assertIn(flat(SENTENCE), flat(stance))

    def test_both_shared_role_descriptions_carry_the_same_sentence(self):
        for name in READ_ONLY:
            for path in (REPO / "primitives/roles" / (name + ".md"),
                         REPO / "claude/agents" / (name + ".md")):
                with self.subTest(path=str(path)):
                    description = [line for line in path.read_text(encoding="utf-8").splitlines()
                                   if line.startswith("description:")]
                    self.assertEqual(len(description), 1, str(path))
                    self.assertIn(SENTENCE, description[0])

    def test_builder_is_exempt_because_writing_is_not_what_the_refusal_confines(self):
        self.assertIn("`builder`", SENTENCE)
        self.assertIsNone(lifecycle.constrained_role("builder"))
        authority = Path(REPO / "primitives/roles/builder.md").read_text(encoding="utf-8")
        self.assertIn("authority: workspace-write", authority)


if __name__ == "__main__":
    unittest.main()
