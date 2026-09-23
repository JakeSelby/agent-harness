# SPDX-License-Identifier: MIT
"""A framework's spawn is classified from its declared integration descriptor, not from the name
the client's model chose, so a review layer spawned as an unnamed subagent is refused exactly as a
named one is. Run: python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO
from harness_core import frameworks, lifecycle, compatibility

# The blind-hunter layer as a client actually re-issues it: no `harness-role:` line, no role name,
# the sentences rewritten, the framework's own nouns kept. This is the spawn #291 was filed for.
PARAPHRASED_LAYER = (
    "You are an adversarial code reviewer. The content under review is the unified diff at "
    "/tmp/review/diff.patch — open it first, then read the changed files around each hunk. "
    "Look for what the change forgot as hard as you look for what it got wrong, and come back "
    "with a list of findings in Markdown and nothing besides. Work alone: do not spawn subagents "
    "of your own."
)
ACCEPTANCE_LAYER = (
    "Act as an acceptance auditor. Read the spec at /tmp/review/spec.md together with every "
    "context document it names, then read the unified diff at /tmp/review/diff.patch. Judge the "
    "diff against the spec only: what it does that the spec did not ask for, what the spec asks "
    "for that it does not do, and which acceptance criteria the diff and its tests do not prove."
)
BUILDER = (
    "Implement issue #412 in the worktree at /tmp/work. Read AGENTS.md first, add the migration "
    "and its test, run the gate, and commit once. Return the branch, the SHA and the gate tail."
)
MENTIONS_REVIEW = (
    "Read docs/releasing.md and summarise how a release is cut. The section on review is the one "
    "I care about: say who reviews what, and flag anything a first-time contributor would have to "
    "guess. Return a short bulleted list."
)
ONE_PHRASE = (
    "Apply the patch in /tmp/patch.diff to the worktree, then tell me whether the unified diff "
    "applied cleanly and which files it touched. Return a bulleted list."
)


def decision(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecision")


def reason(result):
    return result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


class ClassifiedSpawnTests(unittest.TestCase):
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

    def test_a_paraphrased_review_layer_spawned_unnamed_is_denied_with_the_role_instruction(self):
        for role in (None, "general-purpose", "worker-a"):
            with self.subTest(role=role):
                result = self.spawn(PARAPHRASED_LAYER, role=role, session="unnamed-" + str(role))
                self.assertEqual(decision(result), "deny")
                self.assertIn("BMad Method 6.12.0 `code-review-layer`", reason(result))
                self.assertIn("whatever the spawn called itself", reason(result))
                self.assertIn("harness role run reviewer", reason(result))

    def test_the_layer_name_alone_is_enough_when_the_brief_is_only_a_path(self):
        # Observed natively: some spawns carry a path to the routed prompt and nothing else, which
        # a PreToolUse hook cannot read. The framework's own layer name still travels with them.
        result = self.spawn("Follow /tmp/review/prompts/edge-case-hunter.md.", role="edge-case-hunter")
        self.assertEqual(decision(result), "deny")
        self.assertIn("harness role run reviewer", reason(result))

    def test_the_acceptance_layer_maps_to_its_own_role_not_the_review_one(self):
        result = self.spawn(ACCEPTANCE_LAYER)
        self.assertEqual(decision(result), "deny")
        self.assertIn("`acceptance-auditor`", reason(result))
        self.assertIn("harness role run spec-reviewer", reason(result))
        self.assertNotIn("harness role run reviewer", reason(result))

    def test_the_marker_line_is_an_optimisation_and_not_the_enforcement(self):
        marked = self.spawn("harness-role: reviewer\n" + PARAPHRASED_LAYER, session="marked")
        bare = self.spawn(PARAPHRASED_LAYER, session="bare")
        self.assertEqual(decision(marked), "deny")
        self.assertEqual(decision(bare), "deny")
        for result in (marked, bare):
            self.assertIn("harness role run reviewer", reason(result))

    def test_a_builder_brief_runs(self):
        for role in (None, "general-purpose", "builder"):
            with self.subTest(role=role):
                self.assertNotEqual(decision(self.spawn(BUILDER, role=role)), "deny")

    def test_a_brief_that_only_mentions_review_or_one_framework_noun_runs(self):
        for prompt in (MENTIONS_REVIEW, ONE_PHRASE):
            with self.subTest(prompt=prompt[:40]):
                self.assertNotEqual(decision(self.spawn(prompt)), "deny")

    def test_a_classified_refusal_is_remembered_so_the_next_rewording_is_refused_too(self):
        self.spawn(PARAPHRASED_LAYER)
        remembered = lifecycle.denied_spawns("session-one")
        self.assertEqual([entry["role"] for entry in remembered], ["reviewer"])
        # A classified refusal was not remembered before this change, so a re-spawn the descriptor
        # no longer recognises used to run. With the classifier blinded, the memory carries it.
        edited = PARAPHRASED_LAYER + " Also flag any test that asserts nothing."
        with patch.object(frameworks, "classify", lambda *args, **kwargs: None):
            result = self.spawn(edited)
        self.assertEqual(decision(result), "deny")
        self.assertIn("refused as a native reviewer spawn in this session", reason(result))

    def test_the_off_stance_still_answers_once_and_remembers_nothing(self):
        with patch.dict(os.environ, {"HARNESS_STANCE_DELEGATION": "off"}):
            result = self.spawn(PARAPHRASED_LAYER)
            self.assertEqual(decision(result), "deny")
            self.assertIn("Delegation is off", reason(result))
            self.assertNotIn("BMad", reason(result))
            self.assertEqual(lifecycle.denied_spawns("session-one"), [])

    def test_a_descriptor_that_cannot_be_read_leaves_the_spawn_as_it_was(self):
        def broken(*args, **kwargs):
            raise OSError("descriptors are unreadable")

        with patch.object(frameworks, "descriptors", broken):
            self.assertNotEqual(decision(self.spawn(PARAPHRASED_LAYER)), "deny")


class DescriptorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def write(self, name, data):
        (self.dir / name).write_text(json.dumps(data), encoding="utf-8")

    def test_every_shipped_descriptor_validates_and_maps_to_a_constrained_role(self):
        paths = sorted((REPO / "policy" / "integrations").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(descriptor=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(frameworks.problems(data), [])
                self.assertEqual(path.stem, data["id"])
                self.assertTrue((REPO / data["doc"]).is_file())
                for spawn in data["spawns"]:
                    self.assertIsNotNone(lifecycle.constrained_role(spawn["role"]),
                                         msg=spawn["id"] + " maps to an unconstrained role")

    def test_the_bmad_descriptor_agrees_with_the_shipped_override_templates(self):
        data = json.loads((REPO / "policy/integrations/bmad.json").read_text(encoding="utf-8"))
        template = (REPO / "templates/bmad/custom/bmad-code-review.user.toml").read_text(encoding="utf-8")
        agents = set(sum((spawn["agents"] for spawn in data["spawns"]), []))
        roles = {}
        for spawn in data["spawns"]:
            for agent in spawn["agents"]:
                roles[agent] = spawn["role"]
        for line in template.splitlines():
            if line.startswith("id = "):
                layer = line.split('"')[1]
                self.assertIn(layer, agents, msg=layer + " is not declared in the descriptor")
                self.assertIn("harness role run " + roles[layer], template)
        # The pin is the one the repository installs; a descriptor read from another release
        # would map layers that are not there.
        self.assertIn("BMAD_VERSION=" + data["version"]["pinned"],
                      (REPO / "docs" / "bmad.md").read_text(encoding="utf-8"))

    def test_a_descriptor_recognised_only_by_ordinary_wording_is_rejected(self):
        data = {"schema_version": 1, "id": "loose", "name": "Loose", "doc": "docs/bmad.md",
                "version": {"pinned": "1.0"},
                "spawns": [{"id": "layer", "role": "reviewer", "phrases": ["review the code"]}]}
        self.assertIn("declares no identifier", " ".join(frameworks.problems(data)))

    def test_an_invalid_or_unparsable_descriptor_is_skipped_not_raised(self):
        (self.dir / "broken.json").write_text("{ not json", encoding="utf-8")
        self.write("wrong-schema.json", {"schema_version": 99, "id": "x", "name": "X",
                                         "version": {"pinned": "1"}, "spawns": []})
        self.assertEqual(frameworks.descriptors(self.dir), [])
        self.assertIsNone(frameworks.classify(PARAPHRASED_LAYER, None, self.dir))

    def test_corroboration_is_what_separates_a_framework_brief_from_a_borrowed_phrase(self):
        data = json.loads((REPO / "policy/integrations/bmad.json").read_text(encoding="utf-8"))
        self.write("bmad.json", data)
        self.assertIsNone(frameworks.classify(ONE_PHRASE, None, self.dir))
        self.assertEqual(frameworks.classify(PARAPHRASED_LAYER, None, self.dir)["role"], "reviewer")
        raised = dict(data, corroboration=9)
        self.write("bmad.json", raised)
        self.assertIsNone(frameworks.classify(PARAPHRASED_LAYER, None, self.dir))

    def test_input_roots_are_declaration_and_never_a_signal(self):
        data = json.loads((REPO / "policy/integrations/bmad.json").read_text(encoding="utf-8"))
        self.assertIn("_bmad", data["input_roots"])
        self.assertIsNone(frameworks.classify(
            "Edit _bmad/custom/config.toml so the output folder points at _bmad-output, then "
            "rerun the installer and report what changed.", None))


class QualificationTests(unittest.TestCase):
    """The enforced boundary is a native claim, so the catalog has to carry a case for it."""

    def setUp(self):
        self.catalog = compatibility.catalog(REPO)

    def test_the_spawn_confinement_case_is_required(self):
        self.assertIn("spawn-confinement", self.catalog["required_cases"])

    def test_the_procedure_names_the_case_observables_including_the_false_positive_check(self):
        procedure = (REPO / "docs" / "compatibility.md").read_text(encoding="utf-8")
        step = procedure[procedure.index("\n9. "):procedure.index("\nStore a redacted")]
        step = " ".join(step.split())
        for needle in ("names no role", "isolated worker", "false positive", "descriptor",
                       "worker state", "harness role run"):
            self.assertIn(needle, step, msg=needle)

    def test_a_limitation_records_what_the_descriptor_still_cannot_recognise(self):
        entries = [line for line in self.catalog["limitations"] if "#291" in line]
        self.assertTrue(entries)
        current = entries[-1]
        self.assertIn("descriptor", current)
        self.assertIn("0.13.0", current)


if __name__ == "__main__":
    unittest.main()
