# SPDX-License-Identifier: MIT
"""The `spawn-confinement` brief: a model must attempt the spawn, and the spawn must still classify.

A brief that handed the descriptor's sentences over bare ("read that file, ...") read to the
orchestrator as instructions aimed at it, and a model asked which file was meant instead of
calling the Agent tool, so the confinement was never exercised. No test here launches a client.
"""
import unittest

from test_native_acceptance import MODULE


class SpawnBriefTests(unittest.TestCase):

    def setUp(self):
        self.data, self.spawn = MODULE.descriptor_spawn()
        self.corroboration = int(self.data.get("corroboration") or 2)
        self.prompt = MODULE.framework_prompt(self.spawn, self.corroboration)
        self.brief = MODULE.framework_brief(self.spawn, self.corroboration)

    def classify(self, text):
        return MODULE.frameworks.classify(text, None, directory=MODULE.INTEGRATIONS)

    def test_the_spawn_prompt_still_classifies_as_the_declared_spawn_with_no_type(self):
        match = self.classify(self.prompt)
        self.assertIsNotNone(match)
        self.assertEqual(match["spawn"], self.spawn["id"])
        self.assertEqual(match["role"], self.spawn["role"])

    def test_the_spawn_prompt_carries_the_descriptors_own_sentences_verbatim(self):
        for phrase in self.spawn["phrases"][:self.corroboration]:
            self.assertIn(phrase, self.prompt)

    def test_the_subject_sentence_adds_no_signal_of_its_own(self):
        self.assertIsNone(self.classify(MODULE.SPAWN_SUBJECT))

    def test_the_subject_gives_the_descriptors_file_reference_a_referent(self):
        self.assertTrue(self.prompt.startswith(MODULE.SPAWN_SUBJECT))
        self.assertIn("notes.md", MODULE.SPAWN_SUBJECT)

    def test_the_brief_quotes_the_prompt_whole_and_names_no_subagent_type(self):
        self.assertIn('"' + self.prompt + '"', self.brief)
        self.assertEqual(self.brief.count("subagent_type"), 1)
        self.assertIn("no subagent_type", self.brief)

    def test_the_brief_tells_the_orchestrator_the_sentences_are_not_addressed_to_it(self):
        self.assertIn("addressed to the subagent, not to you", self.brief)
        self.assertIn("as your first action", self.brief)

    def test_too_few_phrases_to_corroborate_is_unverified_at_the_prompt_too(self):
        with self.assertRaises(MODULE.Unverified):
            MODULE.framework_prompt({"id": "thin", "phrases": ["only one"]}, 3)


if __name__ == "__main__":
    unittest.main()
