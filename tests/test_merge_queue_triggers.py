"""A merge queue needs every pull request check to run on its merge commit as well."""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pull_number", ROOT / ".github/scripts/pull_number.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

QUEUE_REF = "refs/heads/gh-readonly-queue/main/pr-337-0123456789abcdef0123456789abcdef01234567"


class PullNumberTests(unittest.TestCase):
    def test_a_pull_request_run_uses_its_own_number(self):
        self.assertEqual(module.pull_number({"PR_NUMBER": "12", "MERGE_GROUP_HEAD_REF": ""}), 12)

    def test_a_queue_run_recovers_the_number_from_the_queue_branch(self):
        self.assertEqual(module.pull_number({"PR_NUMBER": "", "MERGE_GROUP_HEAD_REF": QUEUE_REF}), 337)
        self.assertEqual(module.pull_number({"MERGE_GROUP_HEAD_REF": QUEUE_REF[len("refs/heads/"):]}), 337)

    def test_a_run_naming_neither_is_refused_rather_than_guessed(self):
        for env in ({}, {"PR_NUMBER": "", "MERGE_GROUP_HEAD_REF": ""},
                    {"MERGE_GROUP_HEAD_REF": "refs/heads/feature/pr-12-abc"}):
            with self.subTest(env=env):
                with self.assertRaises(KeyError):
                    module.pull_number(env)


class WorkflowTriggerTests(unittest.TestCase):
    """Every workflow that reports on a pull request also reports on a queued one."""

    def workflows(self):
        found = {}
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            trigger = re.search(r"^on:\n((?:[ #].*\n|\n)*)", text, re.MULTILINE).group(1)
            found[path.name] = (text, trigger)
        return found

    def test_each_pull_request_workflow_also_runs_on_merge_group(self):
        checked = 0
        for name, (_, trigger) in self.workflows().items():
            if re.search(r"^  pull_request:", trigger, re.MULTILINE):
                checked += 1
                with self.subTest(workflow=name):
                    self.assertRegex(trigger, r"(?m)^  merge_group:")
        self.assertGreaterEqual(checked, 3)

    def steps(self, text):
        """Each step's text, split at the `- ` that opens it under a job's `steps:`."""
        found = []
        for block in re.split(r"(?m)^    steps:\n", text)[1:]:
            body = re.split(r"(?m)^  [A-Za-z_-]+:\n|^[A-Za-z_-]+:", block)[0]
            found += [part for part in re.split(r"(?m)^(?=      - )", body) if part.strip()]
        return found

    def test_the_step_splitter_sees_every_step(self):
        for name, (text, _) in self.workflows().items():
            with self.subTest(workflow=name):
                self.assertEqual(len(self.steps(text)), len(re.findall(r"(?m)^      - ", text)))

    def test_every_step_reading_pull_request_context_also_handles_a_queue_run(self):
        pull_request_only = re.compile(r"github\.(?:event\.pull_request|head_ref|base_ref)\b")
        guarded = re.compile(r"(?m)^        if: .*github\.event_name == 'pull_request'")
        checked = 0
        for name, (text, _) in self.workflows().items():
            for step in self.steps(text):
                if not pull_request_only.search(step):
                    continue
                checked += 1
                with self.subTest(workflow=name, step=step.splitlines()[0]):
                    self.assertTrue(
                        "MERGE_GROUP_HEAD_REF: ${{ github.event.merge_group.head_ref }}" in step
                        or guarded.search(step),
                        "a step reading pull request context needs the queue ref or a guard")
        self.assertGreaterEqual(checked, 2)

if __name__ == "__main__":
    unittest.main()
