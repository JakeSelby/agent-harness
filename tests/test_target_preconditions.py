# SPDX-License-Identifier: MIT
"""The smoke tier refuses a round at once when a target's client, login or Docker daemon is missing.

A Codex target runs on the ChatGPT session login in its configuration home, and a Linux target
runs in a container on a host that is not Linux. Either missing is otherwise found part-way through
a paid round, so the probe names the target and the reason before any client is launched.
"""
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from harness_core import target_preconditions as probe

# Placeholder, never a credential: presence is the whole test.
PRESENT = "placeholder-value"


def on_path(*names):
    return lambda command, path=None: "/usr/bin/" + command if command in names else None


class Daemon:
    """A stand-in for `subprocess.run` that answers `docker info` and counts the questions."""

    def __init__(self, code=0, raises=None):
        self.code, self.raises, self.calls = code, raises, []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(args, self.code)


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def login(self, folder=None):
        path = Path(folder or self.home / ".codex") / "auth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")

    def check(self, targets, env=None, host="Darwin", which=None, run=None):
        return probe.problems(targets, env or {}, str(self.home), host,
                              which or on_path("codex", "claude", "docker"), run or Daemon())

    def test_a_codex_target_with_a_session_login_can_start(self):
        self.login()
        self.assertEqual(self.check(["codex-cli-macos"]), [])

    def test_a_missing_codex_login_is_named_before_the_round(self):
        [(target, reason)] = self.check(["codex-cli-macos"])
        self.assertEqual(target, "codex-cli-macos")
        self.assertIn("no Codex login", reason)
        self.assertIn("codex login", reason)

    def test_the_login_is_read_from_a_moved_codex_home(self):
        moved = self.home / "elsewhere"
        self.login(moved)
        self.assertEqual(self.check(["codex-cli-macos"], {"CODEX_HOME": str(moved)}), [])
        self.assertTrue(self.check(["codex-cli-macos"],
                                   {"CODEX_HOME": str(self.home / "empty")}))

    def test_an_api_key_stands_in_for_the_session_login(self):
        self.assertEqual(self.check(["codex-cli-macos"], {"OPENAI_API_KEY": PRESENT}), [])

    def test_a_client_off_path_is_named(self):
        self.login()
        [(_, reason)] = self.check(["codex-cli-macos"], which=on_path("docker"))
        self.assertIn("`codex` is not on PATH", reason)

    def test_a_claude_code_target_keeps_the_credential_probe_answer(self):
        self.assertEqual(self.check(["claude-code-cli-macos"], {"ANTHROPIC_API_KEY": PRESENT}), [])
        [(_, reason)] = self.check(["claude-code-cli-macos"])
        self.assertIn("no API key", reason)

    def test_a_linux_target_on_a_mac_needs_only_the_docker_daemon(self):
        daemon = Daemon()
        self.assertEqual(self.check(["codex-cli-linux", "claude-code-cli-linux"], run=daemon), [])
        self.assertEqual(daemon.calls, [["docker", "info", "--format", "{{.ServerVersion}}"]])

    def test_a_stopped_daemon_fails_every_linux_target_after_one_question(self):
        daemon = Daemon(code=1)
        found = self.check(["codex-cli-linux", "claude-code-cli-linux"], run=daemon)
        self.assertEqual([target for target, _ in found],
                         ["codex-cli-linux", "claude-code-cli-linux"])
        self.assertIn("Docker daemon is not running", found[0][1])
        self.assertEqual(len(daemon.calls), 1)

    def test_a_daemon_that_does_not_answer_is_bounded(self):
        daemon = Daemon(raises=subprocess.TimeoutExpired("docker", probe.DOCKER_TIMEOUT))
        [(_, reason)] = self.check(["codex-cli-linux"], run=daemon)
        self.assertIn("did not answer within", reason)

    def test_no_docker_on_path_is_named_without_asking_a_daemon(self):
        daemon = Daemon()
        [(_, reason)] = self.check(["codex-cli-linux"], which=on_path("codex"), run=daemon)
        self.assertIn("`docker` is not on PATH", reason)
        self.assertEqual(daemon.calls, [])

    def test_inside_the_container_a_linux_target_checks_its_client_and_login(self):
        daemon = Daemon()
        [(_, reason)] = self.check(["codex-cli-linux"], host="Linux", run=daemon)
        self.assertIn("no Codex login", reason)
        self.assertEqual(daemon.calls, [])

    def test_a_macos_target_is_refused_off_a_mac(self):
        self.login()
        [(_, reason)] = self.check(["codex-cli-macos"], host="Linux")
        self.assertIn("runs only on a macos host", reason)

    def test_an_unknown_target_is_named_rather_than_skipped(self):
        [(target, reason)] = self.check(["cursor"])
        self.assertEqual(target, "cursor")
        self.assertIn("not a target this probe knows", reason)


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def run_main(self, targets, env):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.dict(
                os.environ, {"HOME": str(self.home)}), patch.object(
                probe.platform, "system", return_value="Darwin"), patch.object(
                probe.shutil, "which", on_path("codex")):
            with redirect_stdout(out), redirect_stderr(err):
                code = probe.main(["--targets", targets])
        return code, out.getvalue(), err.getvalue()

    def test_a_missing_login_exits_nonzero_naming_the_target(self):
        code, out, err = self.run_main("codex-cli-macos", {})
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("preconditions: codex-cli-macos: no Codex login", err)

    def test_a_ready_host_exits_zero_and_prints_no_value(self):
        code, out, err = self.run_main("codex-cli-macos", {"OPENAI_API_KEY": PRESENT})
        self.assertEqual(code, 0)
        self.assertNotIn(PRESENT, out + err)
        self.assertNotIn("OPENAI_API_KEY", out + err)


def smoke_tier():
    path = REPO / "scripts" / "smoke_tier.py"
    spec = importlib.util.spec_from_file_location("smoke_tier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeTierTests(unittest.TestCase):
    def setUp(self):
        self.module = smoke_tier()

    def credentials(self, targets=None):
        [step] = [item for item in self.module.steps(Path("/tmp/unused"), targets)
                  if item["name"] == "credentials"]
        return step

    def test_the_credentials_check_covers_every_runner_target_by_default(self):
        argv = self.credentials()["argv"]
        self.assertIn("harness_core.target_preconditions", argv)
        self.assertEqual(argv[-1], ",".join(sorted(self.module.CLIENTS)))

    def test_the_round_can_name_only_the_targets_it_runs(self):
        self.assertEqual(self.credentials(["codex-cli-linux"])["argv"][-1], "codex-cli-linux")

    def test_an_unknown_target_is_refused_before_anything_runs(self):
        with patch.object(self.module.subprocess, "Popen",
                          side_effect=AssertionError("a check ran")):
            with self.assertRaises(SystemExit) as caught:
                self.module.main(["--targets", "cursor", "--only", "credentials"])
        self.assertIn("unknown target: cursor", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
