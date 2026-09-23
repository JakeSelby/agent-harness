# SPDX-License-Identifier: MIT
"""The gate-invalidation case reads the stop-gate hook's own state record.

The hook keys that record on the repository root as git prints it, which is the resolved path. A
disposable home under a symlinked temporary directory, such as `/var/folders` or `/tmp` on macOS,
must still lead the case to the record the hook wrote. Each test drives the real hook through the
Claude Code lifecycle entrypoint, with no client behind it.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in

CLIENT = "claude-code-cli-macos"


class GateStateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        real = Path(tmp.name) / "real"
        real.mkdir()
        link = Path(tmp.name) / "link"
        os.symlink(str(real), str(link))
        self.home = home_in(link)
        spec = MODULE.CLIENTS[CLIENT]
        self.home.spec = spec
        self.home.runtime = spec["runtime"]
        self.home.home_var = spec["home_var"]
        self.home.client_dir = self.home.root / spec["home_dir"]
        self.home.client_dir.mkdir()
        self.assertNotEqual(str(self.home.root), str(self.home.root.resolve()))

    def gate_repo(self, files):
        repo = self.home.root / "gate-repo"
        repo.mkdir()
        for name, body in files.items():
            (repo / name).write_text(body)
        MODULE.probe_repo(repo, self.home)
        (self.home.client_dir / ".claude.json").write_text(json.dumps(
            {"projects": {str(repo): {"hasTrustDialogAccepted": True}}}))
        return repo

    def test_a_symlinked_home_finds_the_record_the_hook_wrote(self):
        repo = self.gate_repo({"AGENTS.md": "# probe\n\n## Gate\n\n```sh\ntrue\n```\n"})
        MODULE.stop_turn(self.home, repo, "probe-green")
        written = sorted((self.home.root / ".local" / "state" / "agent-harness"
                          / "stop-gate").glob("*.json"))
        self.assertEqual(len(written), 1)
        self.assertEqual(json.loads(written[0].read_text()).get("status"), "passed")
        self.assertEqual(MODULE.gate_state(self.home, repo).get("status"), "passed")

    def test_the_case_gate_records_a_pass_once(self):
        repo = self.gate_repo(MODULE.GATE_REPO_FILES)
        MODULE.stop_turn(self.home, repo, "probe-green")
        self.assertEqual(MODULE.gate_runs(repo), 1)
        self.assertEqual(MODULE.gate_state(self.home, repo).get("status"), "passed")
        MODULE.stop_turn(self.home, repo, "probe-green")
        self.assertEqual(MODULE.gate_runs(repo), 1)


if __name__ == "__main__":
    unittest.main()
