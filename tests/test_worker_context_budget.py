"""An isolated worker is mounted what its policy cites, not the harness checkout.

Run: python3 -m unittest discover tests
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import CFG, REPO, harness
from harness_core import catalog, lifecycle, reconcile, workers

SKILLS = REPO / "primitives" / "skills"
PLAN = """# Fixture plan

> Build the requested fixture. Keep the change scoped.

## At a glance
- Outcome: a verified fixture.

## System design
```text
A ──▶ *B
```

## Steps
1. Implement the fixture.
   *Exit:* tests pass.

## Decisions for the reviewer
None.

## Risks
- A failed check blocks publication.

---
# Addendum
Fixture details.
"""


def work_dir(command):
    """The worker's private directory, from whichever path this runtime's launch carries."""
    if "--append-system-prompt-file" in command:
        return Path(command[command.index("--append-system-prompt-file") + 1]).parent
    return Path(command[command.index("--cd") + 1]).parent


def system_text(command):
    """The system instructions the adapter wrote for a launch, wherever that runtime puts them."""
    if "--append-system-prompt-file" in command:
        return (work_dir(command) / "instructions.md").read_text()
    config = work_dir(command) / "codex" / "config.toml"
    return reconcile.tomlkit.parse(config.read_text())["developer_instructions"]


def broken_role_root(case, role, old, new):
    """A temporary harness root whose copy of `role` has `old` replaced by `new`.

    Every top-level entry and every `primitives` entry but `roles` is a symlink to the checkout;
    the role tree is a copy, so the edit never reaches a tracked file.
    """
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    root = Path(temp.name).resolve()
    for entry in REPO.iterdir():
        if entry.name != "primitives":
            (root / entry.name).symlink_to(entry)
    (root / "primitives").mkdir()
    for entry in (REPO / "primitives").iterdir():
        if entry.name != "roles":
            (root / "primitives" / entry.name).symlink_to(entry)
    shutil.copytree(REPO / "primitives" / "roles", root / "primitives" / "roles")
    path = root / "primitives" / "roles" / (role + ".md")
    text = path.read_text()
    case.assertIn(old, text)
    path.write_text(text.replace(old, new))
    return root


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = copy.deepcopy(CFG)

    def resolve(self, role, runtime="claude-code"):
        return workers.resolution(REPO, self.cfg, runtime, role, model="fixture-model")

    def test_a_worker_is_mounted_every_skill_and_document_its_policy_cites(self):
        ready = self.resolve("reviewer")
        text = ready["instructions"]
        for path in ready["skills"]:
            self.assertRegex(text, r"\b" + path.name + r"\b")
        self.assertTrue(ready["skills"])
        self.assertIn(REPO / "docs" / "preferences.md", ready["docs"])
        # The licensing stance names both, and a worker told to invoke a skill it cannot open is
        # being asked to obey a policy it cannot read.
        self.assertIn(SKILLS / "licensing-review", ready["skills"])

    def test_nothing_the_policy_never_mentions_is_mounted(self):
        ready = self.resolve("reviewer")
        unused = [p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file() and p not in ready["skills"]]
        self.assertTrue(unused)
        for path in unused:
            with self.subTest(skill=path.name):
                self.assertNotRegex(ready["instructions"], r"\b" + path.name + r"\b")

    def test_a_role_adds_what_its_body_assumes_and_the_planner_adds_every_skill(self):
        self.assertIn(SKILLS / "design-loop", self.resolve("design-judge")["skills"])
        shipped = [p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()]
        self.assertEqual(sorted(self.resolve("planner")["skills"]), sorted(shipped))

    def test_every_constrained_role_stays_inside_the_recorded_budget(self):
        for path in sorted((REPO / "primitives" / "roles").glob("*.md")):
            fields, _ = catalog.role_contract(REPO, path.stem)
            if fields["authority"] == "workspace-write":
                continue
            with self.subTest(role=path.stem):
                context = self.resolve(path.stem)["context"]
                self.assertLess(context["total_tokens"], workers.CONTEXT_BUDGET_TOKENS)
                # Each figure is rounded on its own, so the parts may miss the total by one.
                self.assertAlmostEqual(context["total_tokens"],
                                       context["policy_tokens"] + context["reference_tokens"], delta=1)

    def test_a_review_role_is_mounted_far_less_than_the_checkout_it_used_to_get(self):
        # The figure this change is claimed on, and it counts what is mounted, not what a run
        # reads: `--add-dir` took the repository root, and the skill corpus was the authority.
        checkout = workers.est_tokens(workers.text_size([REPO]))
        corpus = workers.est_tokens(workers.text_size([SKILLS]))
        total = self.resolve("reviewer")["context"]["total_tokens"]
        self.assertGreater(checkout, 20 * total)
        self.assertLess(total, corpus + 5000)

    def test_the_estimate_uses_the_same_approximation_the_lint_cap_does(self):
        self.assertEqual(workers.CHARS_PER_TOKEN, harness.CHARS_PER_TOKEN)
        self.assertEqual(workers.est_tokens(4000), harness.est_tokens(4000))

    def test_a_role_naming_an_unshipped_skill_fails_to_resolve(self):
        for declared in ("no-such-skill", "../rules"):
            with self.subTest(declared=declared), self.assertRaises(ValueError):
                catalog.role_skills(REPO, {"skills": declared})


class GuardTests(unittest.TestCase):
    """A contract the guard cannot read is treated as constrained, never waved through."""

    def test_a_role_whose_declared_skill_was_renamed_is_still_refused_natively(self):
        broken = ValueError("role declares an unknown skill: design-loop")
        with patch.object(catalog, "role_contract", side_effect=broken):
            fields = lifecycle.constrained_role("design-judge")
        self.assertIsNotNone(fields)
        self.assertTrue(fields["unresolved"])
        self.assertEqual(fields["authority"], "read-only")
        reason = lifecycle.role_deny("claude-code", "design-judge", fields)["hookSpecificOutput"]
        self.assertEqual(reason["permissionDecision"], "deny")
        # No class was read, so no model was mapped: the refusal asks for the session's.
        self.assertIn("--model <session-model>", reason["permissionDecisionReason"])

    def test_a_renamed_skill_directory_refuses_the_spawn_and_fails_the_run(self):
        # The broken role lives in a temporary root that links every other entry back to the
        # checkout, so the real role file is never rewritten while other processes read it.
        root = broken_role_root(self, "design-judge", "skills: design-loop", "skills: design-loupe")
        with patch.object(lifecycle, "ROOT", root):
            self.assertIsNotNone(lifecycle.constrained_role("design-judge"))
            self.assertIsNone(lifecycle.constrained_role("builder"))
        with self.assertRaisesRegex(ValueError, "unknown skill"):
            workers.resolution(root, copy.deepcopy(CFG), "codex", "design-judge", model="m")
        self.assertIn("skills: design-loop\n", (REPO / "primitives" / "roles" / "design-judge.md").read_text())


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

    def run_worker(self, role, runtime, output="findings", **kwargs):
        def execute(command, prompt, env, cwd, run_dir, timeout):
            # The worker's private directory is removed when the run returns, so the text it was
            # given and the copies mounted beside it are read here, inside the launch.
            self.command, self.prompt = command, prompt
            self.given = system_text(command)
            self.copied = sorted(p.name for p in (work_dir(command) / "policy-reference").glob("*"))
            if "--output-format" in command:
                (run_dir / "stdout.log").write_text(
                    json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": output}))
            else:
                Path(command[command.index("-o") + 1]).write_text(output)
            return 0
        with patch.object(workers.shutil, "which", return_value="/native/cli"), \
             patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
             patch.object(workers, "execute", side_effect=execute):
            return workers.run(REPO, self.cfg, runtime, role, self.workspace, "Review the diff",
                               self.state, model="fixture-model", read_dirs=[str(self.extra)], **kwargs)

    def added(self):
        return [self.command[i + 1] for i, part in enumerate(self.command) if part == "--add-dir"]

    def test_the_claude_worker_is_given_no_path_into_the_harness_checkout(self):
        record = self.run_worker("reviewer", "claude-code")
        self.assertEqual(record["status"], "completed", record)
        roots = self.added()
        self.assertEqual(roots[0], str(self.workspace))
        self.assertEqual(roots[-1], str(self.extra))
        self.assertNotIn(str(REPO), roots)
        for root in roots:
            self.assertFalse(root == str(SKILLS), "the whole corpus is mounted again")

    def test_the_cited_documents_are_mounted_as_copies_beside_the_worker(self):
        self.run_worker("reviewer", "claude-code")
        self.assertIn("preferences.md", self.copied)
        self.assertIn("how-it-works.md", self.copied)
        self.assertIn("policy-reference", self.given)
        self.assertNotIn(str(REPO / "docs"), self.added())

    def test_a_planner_run_publishes_its_plan_and_records_its_roots(self):
        record = self.run_worker("planner", "claude-code", output=PLAN, artifact="plan.md")
        self.assertEqual(record["status"], "completed", record)
        self.assertEqual(Path(record["artifact"]).read_text(), PLAN)
        self.assertEqual(record["read_roots"][0], str(self.workspace))
        self.assertIn(str(SKILLS / "plan-authoring"), record["read_roots"])
        self.assertIn(str(SKILLS / "design-loop"), record["read_roots"])
        self.assertEqual(record["read_roots"][-1], str(self.extra))
        self.assertNotIn(str(REPO), record["read_roots"])

    def test_the_developer_instructions_name_what_is_mounted_and_no_corpus(self):
        for runtime in workers.RUNTIMES:
            with self.subTest(runtime=runtime):
                self.run_worker("reviewer", runtime)
                text = self.given
                self.assertIn("the skills this role may read: ", text)
                self.assertIn("Project to inspect (read-only): " + str(self.workspace), text)
                # The line this change removed; if it returns, the corpus is mounted again.
                self.assertNotIn("Shared skill authority", text)
                self.assertNotIn(str(SKILLS) + ",", text)
                self.assertNotIn(str(SKILLS) + "\n", text)

    def test_the_record_publishes_what_the_run_was_shown(self):
        record = self.run_worker("reviewer", "codex")
        self.assertEqual(record["context"]["budget_tokens"], workers.CONTEXT_BUDGET_TOKENS)
        self.assertLess(record["context"]["total_tokens"], workers.CONTEXT_BUDGET_TOKENS)
        self.assertGreater(record["context"]["reference_tokens"], 0)
        self.assertEqual(workers.status(self.state, record["id"])[0]["context"], record["context"])


if __name__ == "__main__":
    unittest.main()
