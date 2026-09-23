# SPDX-License-Identifier: MIT
"""The generic replacement for the framework-workflow qualification case.

No framework is installed and no client is launched: the case builds its recipe out of whatever
`policy/integrations/` declares and drives the real spawn hook with it, so what a release claims
about framework layering costs a release one cheap turn instead of an hour.
Run: python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from test_native_acceptance import MODULE
from harness_core import lifecycle, compatibility, frameworks


def descriptors():
    """Every shipped descriptor the hook would actually classify against."""
    found = [json.loads(path.read_text(encoding="utf-8"))
             for path in sorted((REPO / "policy" / "integrations").glob("*.json"))]
    return [data for data in found if data.get("spawns") and not frameworks.problems(data)]


class CaseRegistrationTests(unittest.TestCase):
    def test_the_catalog_requires_the_generic_case_and_no_framework_workflow(self):
        required = compatibility.catalog(REPO)["required_cases"]
        self.assertIn("framework-spawn-routing", required)
        self.assertNotIn("bmad-workflow", required)

    def test_the_runner_automates_it(self):
        self.assertIn("framework-spawn-routing", MODULE.CASES)

    def test_the_procedure_step_describes_what_it_observes(self):
        procedure = (REPO / "docs" / "compatibility.md").read_text()
        step = " ".join(procedure[procedure.index("\n6. "):procedure.index("\n7. ")].split())
        for needle in ("policy/integrations/", "isolated-worker instruction", "input roots",
                       "default band worker", "budget sentence", "null variant"):
            self.assertIn(needle, step, msg=needle)


class RecipeTests(unittest.TestCase):
    def test_the_recipe_is_built_from_the_descriptor_and_names_no_framework_in_the_runner(self):
        source = (REPO / "scripts" / "native_acceptance.py").read_text()
        self.assertNotIn("bmad", source.casefold())
        self.assertTrue(descriptors())
        for data in descriptors():
            layer, role, roots, recipe = MODULE.descriptor_recipe(data)
            with self.subTest(descriptor=data["id"]):
                self.assertEqual(layer, data["spawns"][0]["id"])
                self.assertEqual(role, data["spawns"][0]["role"])
                self.assertEqual(roots, data["input_roots"])
                for phrase in data["spawns"][0]["phrases"][:2]:
                    self.assertIn(phrase, recipe)

    def test_a_descriptor_with_too_little_text_is_unverified_rather_than_passed(self):
        thin = dict(descriptors()[0])
        thin["spawns"] = [dict(thin["spawns"][0], phrases=["only one whole sentence of text"])]
        with self.assertRaises(MODULE.Unverified):
            MODULE.descriptor_recipe(thin)


class HookAssertionTests(unittest.TestCase):
    """What the case asserts with zero model turns, driven through the same policy the hook runs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": self.temp.name, "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()

    def answer(self, prompt, subagent_type, session):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": session,
                   "tool_input": {"prompt": prompt, "subagent_type": subagent_type}}
        out = lifecycle.dispatch("claude-code", payload).get("hookSpecificOutput", {})
        return out.get("permissionDecision", ""), out.get("permissionDecisionReason", "")

    def test_the_fixture_recipe_is_refused_however_the_spawn_is_named(self):
        self.assertTrue(descriptors())
        for data in descriptors():
            _, role, roots, recipe = MODULE.descriptor_recipe(data)
            for named_as in (None, "general-purpose", "worker-a"):
                with self.subTest(descriptor=data["id"], named_as=named_as):
                    decision, why = self.answer(recipe, named_as, "r-%s" % named_as)
                    self.assertEqual(decision, "deny")
                    self.assertIn("harness role run " + role, why)
                    self.assertEqual(MODULE.offered_roots(why), set(roots))

    def test_the_offered_read_roots_are_compared_as_a_set_not_by_substring(self):
        """`_bmad` is a prefix of `_bmad-output`, so containment would pass on the wrong list."""
        data = descriptors()[0]
        _, _, roots, recipe = MODULE.descriptor_recipe(data)
        _, why = self.answer(recipe, None, "roots")
        self.assertEqual(MODULE.offered_roots(why), set(roots))
        short = min(roots, key=len)
        longer = [root for root in roots if root != short and root.startswith(short)]
        self.assertTrue(longer, roots)
        partial = why.replace("read roots: " + ", ".join(roots),
                              "read roots: " + ", ".join(longer))
        self.assertNotEqual(MODULE.offered_roots(partial), set(roots))


class DescriptorSelectionTests(unittest.TestCase):
    def test_a_descriptor_the_hook_would_ignore_is_not_the_one_the_case_builds_on(self):
        """The runner and the hook have to agree on which descriptors are in force."""
        broken = dict(descriptors()[0])
        broken["schema_version"] = 99
        self.assertTrue(frameworks.problems(broken))
        self.assertNotIn(broken, descriptors())


if __name__ == "__main__":
    unittest.main()
