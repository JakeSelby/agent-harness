# SPDX-License-Identifier: MIT
"""A Claude worker launched from inside a token-only Claude Code session is refused up front.

Claude Code strips `CLAUDE_CODE_OAUTH_TOKEN` from its tool subprocesses, so `harness role run` run
from a session's Bash tool hands a token-only login nothing, and the worker used to launch and fail
with "Not logged in" (issue #759). The adapter now asks the client's own `auth status` under the
worker's environment first and refuses, naming the missing token, before any worker state exists.
"""
import copy
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_harness import CFG, REPO, harness
from harness_core import workers

FAKE_CLAUDE = """#!/bin/sh
# A stand-in client: answers --version and auth status, and records any other launch.
case "$1" in
  --version) echo "2.1.280 (Claude Code)"; exit 0 ;;
  auth) if [ -n "$CLAUDE_CODE_OAUTH_TOKEN" ]; then echo '{"loggedIn": true}'; exit 0; fi
        echo '{"loggedIn": false, "authMethod": "none"}'; exit 1 ;;
esac
touch "$(dirname "$0")/launched"
echo '{"type":"result","subtype":"success","is_error":false,"result":"done"}'
exit 0
"""


def completed(stdout, code=0):
    return subprocess.CompletedProcess(["claude"], code, stdout=stdout)


class RefusalTests(unittest.TestCase):
    """`workers.run` with the adapter's `auth status` call stubbed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.state = self.base / "state"
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base / "user"), "PATH": os.environ["PATH"],
                                "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s-1"},
                   clear=True).start()
        self.launched = []

    def execute(self, command, prompt, env, cwd, run_dir, timeout):
        self.launched.append(env)
        (run_dir / "stdout.log").write_text(json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": "done"}))
        return 0

    def run_worker(self, status):
        auth = Mock(side_effect=status)
        load = workers.adapter

        def adapter(root, runtime):
            # Only the adapter's own `auth status` call is stubbed; keychain setup runs as usual.
            module = load(root, runtime)
            module.subprocess = SimpleNamespace(run=auth, DEVNULL=subprocess.DEVNULL,
                                                PIPE=subprocess.PIPE,
                                                SubprocessError=subprocess.SubprocessError)
            return module

        with patch.object(workers.shutil, "which", return_value="/native/claude"), \
                patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
                patch.object(workers, "execute", side_effect=self.execute), \
                patch.object(workers, "adapter", side_effect=adapter):
            try:
                return workers.run(REPO, copy.deepcopy(CFG), "claude-code", "reviewer",
                                   self.workspace, "Inspect the fixture", self.state,
                                   model="fixture-model"), auth
            except ValueError as refused:
                return refused, auth

    def test_a_session_with_no_login_is_refused_before_any_state_exists(self):
        result, auth = self.run_worker(lambda *a, **k: completed('{"loggedIn": false}', 1))
        self.assertIsInstance(result, ValueError)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", str(result))
        self.assertIn("refused before launch", str(result))
        self.assertEqual(auth.call_args[0][0], ["/native/claude", "auth", "status", "--json"])
        self.assertEqual(self.launched, [])
        self.assertFalse(self.state.exists())

    def test_a_session_with_a_stored_login_launches(self):
        result, auth = self.run_worker(lambda *a, **k: completed('{"loggedIn": true}'))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(self.launched), 1)

    def test_the_check_sees_the_worker_credentials_and_home_and_not_the_session(self):
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "token-fixture"
        os.environ["USER"] = "operator"
        result, auth = self.run_worker(lambda *a, **k: completed('{"loggedIn": true}'))
        env = auth.call_args[1]["env"]
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "token-fixture")
        self.assertEqual(env["HOME"], str(self.base / "user"))
        self.assertEqual(env["USER"], "operator")
        self.assertNotIn("CLAUDECODE", env)
        self.assertNotIn("CLAUDE_CODE_SESSION_ID", env)
        self.assertEqual(auth.call_args[1]["stderr"], subprocess.DEVNULL)

    def test_the_check_runs_from_an_empty_directory_and_not_the_caller_project(self):
        seen = []

        def status(*a, **k):
            seen.append((k["cwd"], os.listdir(k["cwd"])))
            return completed('{"loggedIn": true}')
        self.run_worker(status)
        cwd, entries = seen[0]
        self.assertTrue(os.path.basename(cwd).startswith("harness-worker-auth-"))
        self.assertNotEqual(os.path.realpath(cwd), os.path.realpath(os.getcwd()))
        self.assertEqual(entries, [])
        self.assertFalse(os.path.exists(cwd))

    def test_a_check_that_cannot_run_or_answer_refuses(self):
        def missing(*a, **k):
            raise FileNotFoundError("claude")
        for status in (missing, lambda *a, **k: completed("not json"),
                       lambda *a, **k: completed("[]"), lambda *a, **k: completed('{"loggedIn": "yes"}')):
            result, _ = self.run_worker(status)
            self.assertIsInstance(result, ValueError)
            self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", str(result))
        self.assertEqual(self.launched, [])

    def test_outside_a_session_or_on_a_cloud_provider_nothing_is_checked(self):
        del os.environ["CLAUDECODE"]
        result, auth = self.run_worker(lambda *a, **k: completed('{"loggedIn": false}', 1))
        self.assertEqual(result["status"], "completed")
        auth.assert_not_called()
        os.environ["CLAUDECODE"] = "1"
        os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
        result, auth = self.run_worker(lambda *a, **k: completed('{"loggedIn": false}', 1))
        self.assertEqual(result["status"], "completed")
        auth.assert_not_called()

    def test_codex_workers_are_not_checked(self):
        native = workers.adapter(REPO, "codex")
        self.assertIsNone(getattr(native, "refusal", None))


class CommandTests(unittest.TestCase):
    """`harness role run` end to end, with a stand-in `claude` on PATH and nothing else stubbed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        client = self.bin / "claude"
        client.write_text(FAKE_CLAUDE)
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
        self.home = base / "user"
        self.home.mkdir()
        self.workspace = base / "project"
        self.workspace.mkdir()
        self.brief = base / "brief.md"
        self.brief.write_text("Inspect the fixture")
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.home), "CLAUDECODE": "1",
                                "PATH": str(self.bin) + os.pathsep + os.environ["PATH"]},
                   clear=True).start()

    def role_run(self):
        err = io.StringIO()
        with patch.object(harness, "load_config", return_value=copy.deepcopy(CFG)), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = harness.main(["role", "run", "reviewer", "--runtime", "claude-code",
                                 "--prompt-file", str(self.brief), "--workspace", str(self.workspace)])
        return code, err.getvalue()

    def test_a_token_only_session_is_refused_with_the_missing_token_named(self):
        code, err = self.role_run()
        self.assertEqual(code, 1)
        self.assertIn("role worker: refused before launch", err)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", err)
        self.assertFalse((self.bin / "launched").exists())
        self.assertFalse((self.home / ".local/state/agent-harness/workers").exists())

    def test_an_exported_token_passes_the_check_and_the_worker_launches(self):
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "token-fixture"
        code, err = self.role_run()
        self.assertEqual(code, 0, err)
        self.assertTrue((self.bin / "launched").exists())
        self.assertNotIn("refused before launch", err)
        self.assertNotIn("token-fixture", err)


if __name__ == "__main__":
    unittest.main()
