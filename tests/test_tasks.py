"""Continuation across runtime names preserves data and rejects stale writers."""
import json
from pathlib import Path
import unittest
import test_stop_gate as gate_fixture
from test_harness import harness
from harness_core import tasks


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
