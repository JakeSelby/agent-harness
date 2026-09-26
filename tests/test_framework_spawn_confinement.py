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

# The standing preamble a coordinator puts at the head of every brief it sends, review and build
# alike. Over 400 characters, so any two briefs that carry it are the same work to `same_work`.
PREAMBLE = (
    "Work in the assigned worktree and nowhere else. Read the repository's AGENTS.md before you "
    "touch anything, follow the commit convention it names, and run the gate it names before you "
    "say you are finished. Never push, never open a pull request, never bypass a hook. Keep to "
    "the files the task names; anything outside them is a conflict with whoever else is working "
    "right now. Report what you did, what you could not do, and what only the owner can decide. "
)
# The blind-hunter layer as a client re-issues it: the launch sentence and the `harness-role:`
# line are gone, the framing is rewritten, and the layer's own instructions are kept. This is the
# spawn #291 was filed for.
PARAPHRASED_LAYER = PREAMBLE + (
    "You are an adversarial reviewer. The change is at /tmp/review/diff.patch. Read that file, it "
    "is the content under review, then read the changed files around the hunks. Hunt for what is "
    "missing as well as what is wrong, and come back with a Markdown list and nothing else. Do "
    "not invoke any skill and do not spawn subagents of your own."
)
ACCEPTANCE_LAYER = (
    "Act as an acceptance auditor. The spec is /tmp/review/spec.md; read it, with any context "
    "documents it names. The diff is at /tmp/review/diff.patch; read that file, it is the change "
    "under review. Judge the diff against the spec only: what it does that the spec did not ask "
    "for, what the spec asks for that it does not do, and which acceptance criteria the diff and "
    "its tests do not prove."
)
# Same preamble, different work: allowed, and the test that the classified refusal above was not
# written into the session's memory, where prefix matching would have caught this too.
BUILDER = PREAMBLE + (
    "Implement issue #412: add the migration and its test, run the gate, and commit once. Return "
    "the branch, the SHA and the gate tail."
)
# The ordinary brief that follows a review. It says every generic noun a review says, which is
# why those nouns are not signals.
FIX_UP = (
    "Read the list of findings in /tmp/review.md, fix each one in the worktree, and return the "
    "unified diff of what you changed together with the gate output."
)
# Work on the framework's own files, which necessarily quotes the paths the descriptor identifies.
TEMPLATE_EDIT = (
    "Edit templates/bmad/custom/bmad-code-review.user.toml so the edge-case layer points at "
    "review-prompts/edge-case-hunter.md rather than the old path, then run harness bmad check."
)
# One sentence of the template, quoted in passing. One is a coincidence; the classifier says so.
QUOTED_SENTENCE = (
    "The layer text ends with `do not invoke any skill and do not spawn subagents of your own`. "
    "Tell me whether that sentence is still accurate now that the layers run as isolated workers, "
    "and where else in the docs it is repeated."
)
MENTIONS_REVIEW = (
    "Read docs/releasing.md and summarise how a release is cut. The section on review is the one "
    "I care about: say who reviews what, and flag anything a first-time contributor would have to "
    "guess. Return a short bulleted list."
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

    def test_the_briefs_a_review_leaves_behind_all_run(self):
        """Generic review nouns, the framework's own files, and one quoted sentence: none of these
        is the framework's work, and refusing any of them would cost more than it caught."""
        for prompt in (MENTIONS_REVIEW, FIX_UP, TEMPLATE_EDIT, QUOTED_SENTENCE):
            with self.subTest(prompt=prompt[:40]):
                self.assertNotEqual(decision(self.spawn(prompt)), "deny")

    def test_a_classified_refusal_is_not_written_into_the_session_memory(self):
        # `same_work` matches on a 400-character prefix or 0.85 similarity, so a remembered
        # inference would refuse every later brief that shares a standing preamble with it.
        denied = self.spawn(PARAPHRASED_LAYER)
        self.assertEqual(decision(denied), "deny")
        self.assertEqual(lifecycle.denied_spawns("session-one"), [])
        self.assertTrue(lifecycle.same_work(lifecycle.fingerprint(PARAPHRASED_LAYER),
                                            lifecycle.fingerprint(BUILDER)))
        self.assertNotEqual(decision(self.spawn(BUILDER)), "deny")

    def test_a_named_or_marked_refusal_is_still_remembered(self):
        self.spawn(BUILDER, role="reviewer")
        self.assertEqual([e["role"] for e in lifecycle.denied_spawns("session-one")], ["reviewer"])
        self.spawn("harness-role: spec-reviewer\n" + MENTIONS_REVIEW, session="marked")
        self.assertEqual([e["role"] for e in lifecycle.denied_spawns("marked")], ["spec-reviewer"])

    def test_the_refusal_names_the_read_roots_the_isolated_worker_will_need(self):
        result = self.spawn(PARAPHRASED_LAYER)
        self.assertIn("input roots as read roots", reason(result))
        for root in ("_bmad", "_bmad-output", ".claude/skills"):
            self.assertIn(root, reason(result))

    def test_a_descriptor_that_cannot_be_used_is_announced_once_a_session(self):
        integrations = self.base / "integrations"
        integrations.mkdir()
        (integrations / "broken.json").write_text("{ not json", encoding="utf-8")
        with patch.object(frameworks, "DESCRIPTORS", integrations):
            first = self.spawn(PARAPHRASED_LAYER)
            second = self.spawn(BUILDER)
        self.assertIn("harness:integrations: ignored broken.json", first.get("systemMessage", ""))
        self.assertNotIn("integrations", second.get("systemMessage", ""))
        # Nothing was classified, so nothing was refused: the notice is the only signal there is.
        self.assertNotEqual(decision(first), "deny")

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
                self.assertIn("citizen role run " + roles[layer], template)
        # The pin is the one the repository installs; a descriptor read from another release
        # would map layers that are not there.
        self.assertIn("BMAD_VERSION=" + data["version"]["pinned"],
                      (REPO / "docs" / "bmad.md").read_text(encoding="utf-8"))

    def test_every_declared_phrase_is_a_sentence_of_the_framework_s_own_prompt_text(self):
        """A phrase invented for the descriptor recognises nothing; only the shipped text does."""
        data = json.loads((REPO / "policy/integrations/bmad.json").read_text(encoding="utf-8"))
        template = frameworks.normalise(
            (REPO / "templates/bmad/custom/bmad-code-review.user.toml").read_text(encoding="utf-8"))
        for spawn in data["spawns"]:
            for phrase in spawn["phrases"]:
                with self.subTest(phrase=phrase):
                    self.assertIn(frameworks.normalise(phrase), template)

    def test_a_descriptor_whose_signals_are_too_slight_to_identify_anything_is_rejected(self):
        base = {"schema_version": 1, "id": "loose", "name": "Loose", "doc": "docs/bmad.md",
                "version": {"pinned": "1.0"}, "input_roots": ["_bmad"]}
        cases = [
            ({"id": "layer", "role": "reviewer", "phrases": ["unified diff", "list of findings"]},
             "too slight"),
            ({"id": "layer", "role": "reviewer", "identifiers": ["_bmad/custom"],
              "phrases": ["read that file, it is the content under review"]}, "input root"),
            ({"id": "layer", "role": "builder",
              "phrases": ["read that file, it is the content under review"]}, "isolated worker"),
            ({"id": "layer", "role": "reviewer", "identifiers": ["review-prompts/blind-hunter.md"]},
             "declares no phrases"),
        ]
        for spawn, needle in cases:
            with self.subTest(needle=needle):
                found = " ".join(frameworks.problems(dict(base, spawns=[spawn])))
                self.assertIn(needle, found)

    def test_an_invalid_or_unparsable_descriptor_is_skipped_and_the_reason_is_kept(self):
        (self.dir / "broken.json").write_text("{ not json", encoding="utf-8")
        self.write("wrong-schema.json", {"schema_version": 99, "id": "x", "name": "X",
                                         "version": {"pinned": "1"}, "spawns": []})
        self.assertEqual(frameworks.descriptors(self.dir), [])
        self.assertIsNone(frameworks.classify(PARAPHRASED_LAYER, None, self.dir))
        reasons = dict(frameworks.ignored(self.dir))
        self.assertEqual(sorted(reasons), ["broken.json", "wrong-schema.json"])
        self.assertIn("JSONDecodeError", reasons["broken.json"])
        self.assertIn("schema_version", reasons["wrong-schema.json"])

    def test_an_edited_descriptor_is_reread_rather_than_served_from_the_cache(self):
        data = json.loads((REPO / "policy/integrations/bmad.json").read_text(encoding="utf-8"))
        self.write("bmad.json", data)
        self.assertIsNotNone(frameworks.classify(PARAPHRASED_LAYER, None, self.dir))
        self.write("bmad.json", dict(data, corroboration=9))  # same size is not the same bytes
        self.assertIsNone(frameworks.classify(PARAPHRASED_LAYER, None, self.dir))

    def test_an_identifier_needs_a_phrase_beside_it_and_a_layer_name_does_not(self):
        self.assertIsNone(frameworks.classify(TEMPLATE_EDIT, None))
        self.assertEqual(frameworks.classify(
            TEMPLATE_EDIT + " Then hunt for what is missing as well as what is wrong.",
            None)["role"], "reviewer")
        self.assertEqual(frameworks.classify(TEMPLATE_EDIT, "edge-case-hunter")["role"], "reviewer")

    def test_a_match_the_guard_would_not_constrain_never_outscores_one_it_would(self):
        seen = []
        frameworks.classify(PARAPHRASED_LAYER, None, accept=lambda role: seen.append(role) or False)
        self.assertIn("reviewer", seen)
        self.assertIsNone(frameworks.classify(PARAPHRASED_LAYER, None, accept=lambda role: False))

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
                       "worker state", "citizen role run"):
            self.assertIn(needle, step, msg=needle)

    def test_a_limitation_records_what_the_descriptor_still_cannot_recognise(self):
        entries = [line for line in self.catalog["limitations"] if "#291" in line]
        self.assertTrue(entries)
        current = entries[-1]
        self.assertIn("descriptor", current)
        self.assertIn("0.13.0", current)


if __name__ == "__main__":
    unittest.main()
