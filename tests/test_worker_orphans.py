"""A worker whose process died without reporting reads as orphaned, and a live one never does."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import CFG, REPO
from harness_core import workers

RECORD = {"schema_version": 1, "role": "reviewer", "runtime": "codex", "mode": "isolated-cli",
          "status": "running", "started_at": 1.0}


class OrphanedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "workers"
        self.state.mkdir()

    def write(self, worker_id, **fields):
        run_dir = self.state / worker_id
        run_dir.mkdir()
        record = dict(RECORD, id=worker_id, **fields)
        (run_dir / "status.json").write_text(json.dumps(record, indent=2) + "\n")
        return run_dir

    def dead_pid(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    def test_a_live_process_is_still_running(self):
        run_dir = self.write("a" * 32, pid=os.getpid(), pid_start=workers.process_start(os.getpid()))
        self.assertEqual(workers.status(self.state, "a" * 32)[0]["status"], "running")
        self.assertEqual(json.loads((run_dir / "status.json").read_text())["status"], "running")

    def test_a_dead_process_with_no_result_is_orphaned_and_persisted(self):
        run_dir = self.write("b" * 32, pid=self.dead_pid(), pid_start="1234567890", workspace="/project")
        record = workers.status(self.state, "b" * 32)[0]
        self.assertEqual(record["status"], "orphaned")
        self.assertEqual(record["error"], workers.ORPHANED)
        stored = json.loads((run_dir / "status.json").read_text())
        self.assertEqual(stored["status"], "orphaned")
        self.assertEqual(stored["workspace"], "/project")
        self.assertEqual(stored["started_at"], 1.0)
        self.assertEqual(sorted(p.name for p in run_dir.iterdir()), ["status.json"])

    def test_a_dead_process_that_reported_keeps_its_finished_state(self):
        run_dir = self.write("c" * 32, pid=self.dead_pid(), pid_start="1234567890", status="completed")
        (run_dir / "result.md").write_text("findings")
        self.assertEqual(workers.status(self.state, "c" * 32)[0]["status"], "completed")
        pid = self.dead_pid()
        late = self.write("d" * 32, pid=pid, pid_start="1234567890",
                          result_path=str(self.state / ("d" * 32) / "result.md"))
        (late / "result.md").write_text("findings")
        self.assertEqual(workers.status(self.state, "d" * 32)[0]["status"], "running")

    def test_a_record_without_a_pid_stays_running(self):
        run_dir = self.write("e" * 32)
        self.assertEqual(workers.status(self.state, "e" * 32)[0]["status"], "running")
        self.assertNotIn("pid", json.loads((run_dir / "status.json").read_text()))
        self.assertIsNone(workers.running(None, None))
        self.assertIsNone(workers.running(0, "token"))

    def test_a_reused_pid_with_a_different_start_is_orphaned(self):
        token = workers.process_start(os.getpid())
        self.write("f" * 32, pid=os.getpid(), pid_start="not-this-incarnation")
        expected = "running" if token is None else "orphaned"
        self.assertEqual(workers.status(self.state, "f" * 32)[0]["status"], expected)
        self.assertTrue(workers.running(os.getpid(), None))

    def test_a_launched_worker_records_the_pid_that_supervises_it(self):
        workspace = Path(self.temp.name) / "project"
        workspace.mkdir()
        def execute(command, prompt, env, cwd, run_dir, timeout):
            (run_dir / "stdout.log").write_text(json.dumps(
                {"type": "result", "subtype": "success", "is_error": False, "result": "findings"}))
            return 0
        with patch.dict(os.environ, {"HOME": str(Path(self.temp.name) / "user"), "PATH": os.environ["PATH"]}, clear=True), \
             patch.object(workers.shutil, "which", return_value="/native/cli"), \
             patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
             patch.object(workers, "execute", side_effect=execute):
            record = workers.run(REPO, copy.deepcopy(CFG), "claude-code", "reviewer", workspace,
                                 "Inspect the fixture", self.state, model="fixture-model")
        self.assertEqual(record["status"], "completed", record)
        self.assertEqual(record["pid"], os.getpid())
        self.assertEqual(record["pid_start"], workers.process_start(os.getpid()))
        self.assertEqual(workers.status(self.state, record["id"])[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
