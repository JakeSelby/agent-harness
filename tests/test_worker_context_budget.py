"""An isolated worker carries its role, the stances and its declared skills, not the corpus.

Run: python3 -m unittest discover tests
"""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import CFG, REPO, harness
from harness_core import catalog, reconcile, workers

SKILLS = REPO / "primitives" / "skills"


def system_text(command):
    """The system instructions the adapter wrote for a launch, wherever that runtime puts them."""
    if "--append-system-prompt-file" in command:
        return Path(command[command.index("--append-system-prompt-file") + 1]).read_text()
    home = Path(command[command.index("--cd") + 1]).parent / "codex"
    return reconcile.tomlkit.parse((home / "config.toml").read_text())["developer_instructions"]


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(CFG)

    def resolve(self, role, runtime="claude-code"):
        return workers.resolution(REPO, self.cfg, runtime, role, model="fixture-model")

    def test_a_review_role_is_pointed_at_no_skill_and_carries_only_shared_policy(self):
        ready = self.resolve("reviewer")
        self.assertEqual(ready["skills"], [])
        self.assertEqual(ready["context"]["skill_tokens"], 0)
        self.assertEqual(ready["context"]["total_tokens"], ready["context"]["policy_tokens"])
        text = ready["instructions"]
        self.assertIn(catalog.role_contract(REPO, "reviewer")[1], text)
        self.assertIn((REPO / "primitives/stances/testing/required.md").read_text(), text)
        self.assertNotIn(str(SKILLS), text)

    def test_a_role_that_needs_a_skill_names_exactly_that_one(self):
        for role, skill in (("planner", "plan-authoring"), ("design-judge", "design-loop")):
            with self.subTest(role=role):
                self.assertEqual(self.resolve(role)["skills"], [SKILLS / skill])

    def test_every_constrained_role_resolves_well_inside_the_context_budget(self):
        # The saving the four-layer review round is bought with: the whole skill corpus was
        # roughly 31,600 tokens on top of the policy, and no role loads it now.
        corpus = workers.context_estimate("", [SKILLS])["skill_tokens"]
        self.assertGreater(corpus, 20000)
        for path in sorted((REPO / "primitives" / "roles").glob("*.md")):
            fields, _ = catalog.role_contract(REPO, path.stem)
            if fields["authority"] == "workspace-write":
                continue
            with self.subTest(role=path.stem):
                context = self.resolve(path.stem)["context"]
                self.assertLess(context["total_tokens"], workers.CONTEXT_BUDGET_TOKENS)
                self.assertLess(context["skill_tokens"], corpus)

    def test_the_estimate_uses_the_same_approximation_the_lint_cap_does(self):
        self.assertEqual(workers.CHARS_PER_TOKEN, harness.CHARS_PER_TOKEN)
        self.assertEqual(workers.est_tokens(4000), harness.est_tokens(4000))

    def test_a_role_naming_an_unshipped_skill_fails_to_resolve(self):
        for declared in ("no-such-skill", "../rules"):
            with self.subTest(declared=declared), self.assertRaises(ValueError):
                catalog.role_skills(REPO, {"skills": declared})


class LaunchTests(unittest.TestCase):
    """What the worker process is actually handed: read roots, and the text of its prompt."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.extra = self.base / "artifacts"
        self.extra.mkdir()
        self.state = self.base / "state"
        self.cfg = copy.deepcopy(CFG)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base / "user"), "PATH": os.environ["PATH"]}, clear=True).start()

    def run_worker(self, role, runtime, **kwargs):
        def execute(command, prompt, env, cwd, run_dir, timeout):
            # The worker's private directory is removed when the run returns, so the text it was
            # given is read here, inside the launch, rather than from the record afterwards.
            self.command, self.prompt = command, prompt
            self.given = system_text(command)
            if "--output-format" in command:
                (run_dir / "stdout.log").write_text(
                    json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "findings"}))
            else:
                Path(command[command.index("-o") + 1]).write_text("findings")
            return 0
        with patch.object(workers.shutil, "which", return_value="/native/cli"), \
             patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
             patch.object(workers, "execute", side_effect=execute):
            return workers.run(REPO, self.cfg, runtime, role, self.workspace, "Review the diff",
                               self.state, model="fixture-model", read_dirs=[str(self.extra)], **kwargs)

    def test_the_claude_worker_is_given_no_path_into_the_harness_checkout(self):
        record = self.run_worker("reviewer", "claude-code")
        self.assertEqual(record["status"], "completed", record)
        added = [self.command[i + 1] for i, part in enumerate(self.command) if part == "--add-dir"]
        self.assertEqual(added, [str(self.workspace), str(self.extra)])
        self.assertEqual(record["read_roots"], [str(self.workspace), str(self.extra)])

    def test_a_skill_the_role_declares_is_the_only_checkout_path_a_worker_gets(self):
        record = self.run_worker("planner", "claude-code", artifact="plan.md")
        added = [self.command[i + 1] for i, part in enumerate(self.command) if part == "--add-dir"]
        self.assertEqual(added, [str(self.workspace), str(SKILLS / "plan-authoring"), str(self.extra)])
        self.assertNotIn(str(REPO / "primitives" / "rules"), added)

    def test_the_developer_instructions_name_the_declared_skills_and_no_corpus(self):
        for runtime in workers.RUNTIMES:
            with self.subTest(runtime=runtime):
                self.run_worker("reviewer", runtime)
                text = self.given
                self.assertIn("This role reads no skill authority", text)
                self.assertNotIn(str(SKILLS), text)
                self.assertIn("Project to inspect (read-only): " + str(self.workspace), text)

    def test_a_declaring_role_is_told_which_skills_it_may_read(self):
        self.run_worker("planner", "codex", artifact="plan.md")
        text = self.given
        self.assertIn("the only skills this role reads: " + str(SKILLS / "plan-authoring"), text)
        self.assertNotIn(str(SKILLS / "design-loop"), text)

    def test_the_record_publishes_what_the_run_may_load(self):
        record = self.run_worker("reviewer", "codex")
        self.assertEqual(record["context"]["skill_tokens"], 0)
        self.assertEqual(record["context"]["budget_tokens"], workers.CONTEXT_BUDGET_TOKENS)
        self.assertLess(record["context"]["total_tokens"], workers.CONTEXT_BUDGET_TOKENS)
        self.assertEqual(workers.status(self.state, record["id"])[0]["context"], record["context"])



if __name__ == "__main__":
    unittest.main()
