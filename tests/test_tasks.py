"""Continuation across runtime names preserves data and rejects stale writers."""
import importlib.util
import json
from pathlib import Path
import unittest
import test_stop_gate as gate_fixture
from test_harness import harness
from harness_core import tasks

_spec = importlib.util.spec_from_file_location(
    "stage_user_files", Path(__file__).resolve().parent.parent / "policy" / "hooks" / "stage-user-files.py")
stage_user_files = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stage_user_files)


class TaskTests(unittest.TestCase):
    setUp = gate_fixture.StopGateTests.setUp
    trust = gate_fixture.StopGateTests.trust
    env = gate_fixture.StopGateTests.env
    git = gate_fixture.StopGateTests.git
    def test_bidirectional_runtime_handoff_and_stale_revision(self):
        self.repo = self.repo.resolve()
        first = tasks.save(self.repo, {"objective": "Complete the fixture", "next_steps": ["Inspect files"]}, "claude-code")
        self.assertEqual(first["status"], "current")
        self.assertEqual(first["verification"]["status"], "unverified")
        second = tasks.save(self.repo, {"objective": "Continue the fixture", "verification": "passed"}, "codex", 1)
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["verification"]["status"], "unverified")
        with self.assertRaisesRegex(ValueError, "revision changed"):
            tasks.save(self.repo, {"objective": "Stale writer"}, "claude-code", 1)
        (self.repo / "file.txt").write_text("changed")
        self.assertEqual(tasks.read(self.repo)["status"], "stale")

    def test_authority_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid task"):
            tasks.save(self.repo, {"objective": "work", "permissions": "bypass"}, "codex")

    def test_symlink_storage_is_rejected(self):
        (self.repo / ".agent-harness").symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            tasks.save(self.repo, {"objective": "work"}, "codex")

    def test_ignored_shared_plan_and_progress_changes_invalidate_handoff(self):
        self.repo = self.repo.resolve()
        (self.repo / ".gitignore").write_text(".agent-harness/\n")
        directory = self.repo / ".agent-harness"
        plans = directory / "plans"
        plans.mkdir(parents=True)
        plan = plans / "work.md"
        plan.write_text("original")
        tasks.save(self.repo, {"objective": "Plan the work"}, "codex")
        self.assertEqual(tasks.read(self.repo)["status"], "current")
        plan.write_text("revised scope")
        self.assertEqual(tasks.read(self.repo)["status"], "stale")
        tasks.save(self.repo, {"objective": "Continue"}, "claude-code", 1)
        (directory / "progress.md").write_text("New findings")
        self.assertEqual(tasks.read(self.repo)["status"], "stale")

    def test_files_staged_for_a_remote_control_client_leave_the_handoff_current(self):
        self.repo = self.repo.resolve()
        tasks.save(self.repo, {"objective": "Show the render"}, "claude-code")
        render = self.home / "render.png"
        render.write_bytes(b"png")
        result = stage_user_files.decide({"tool_name": "SendUserFile", "cwd": str(self.repo),
                                          "tool_input": {"files": [str(render)]}})
        self.assertTrue(Path(result["hookSpecificOutput"]["updatedInput"]["files"][0]).is_file())
        self.assertEqual(tasks.read(self.repo)["status"], "current")

    def test_tracked_task_bookkeeping_does_not_invalidate_its_own_save(self):
        self.repo = self.repo.resolve()
        tasks.save(self.repo, {"objective": "First"}, "codex")
        self.git("add", ".agent-harness/task.json")
        self.git("commit", "-qm", "Record task fixture")
        updated = tasks.save(self.repo, {"objective": "Second"}, "claude-code", 1)
        self.assertEqual(updated["status"], "current")

    def test_read_rejects_symlink_storage(self):
        (self.repo / ".agent-harness").symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            tasks.read(self.repo)

    def test_untracked_filename_whitespace_is_preserved(self):
        self.repo = self.repo.resolve()
        file = self.repo / " leading and trailing "
        file.write_text("old")
        tasks.save(self.repo, {"objective": "Inspect input"}, "codex")
        file.write_text("new")
        self.assertEqual(tasks.read(self.repo)["status"], "stale")
