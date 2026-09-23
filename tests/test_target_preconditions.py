# SPDX-License-Identifier: MIT
"""The smoke tier refuses a round at once when a target's client, login or Docker daemon is missing.

A Codex target runs on the ChatGPT session login in its configuration home, and a Linux target
runs in a container on a host that is not Linux. Either missing is otherwise found part-way through
a paid round, so the probe names the target and the reason before any client is launched.
"""
import importlib.util
import io
import json
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


def on_path(*names, folder="/usr/bin"):
    """A `shutil.which` stand-in that finds `names` only when the PATH it is given holds `folder`.

    A PATH of `None` is the process's own, as it is for `shutil.which`.
    """
    def which(command, path=None):
        path = os.environ.get("PATH", "") if path is None else path
        if command in names and folder in path.split(os.pathsep):
            return folder + "/" + command
        return None
    return which


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
        env = dict({"PATH": "/usr/bin"}, **(env or {}))
        return probe.problems(targets, env, str(self.home), host,
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

    def test_the_client_is_looked_up_on_the_path_the_round_passes(self):
        self.login()
        which = on_path("codex", folder="/opt/clients")
        [(_, reason)] = self.check(["codex-cli-macos"], which=which)
        self.assertIn("`codex` is not on PATH", reason)
        self.assertEqual(self.check(["codex-cli-macos"], {"PATH": "/usr/bin:/opt/clients"},
                                    which=which), [])

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

    def test_a_surface_that_is_not_a_cli_is_refused(self):
        self.login()
        for target in ("codex-desktop-macos", "codex-vscode-macos", "claude-code-vscode-macos",
                       "claude-code-plugin-marketplace"):
            [(_, reason)] = self.check([target])
            self.assertIn("not a target this probe knows", reason, msg=target)


class DefaultTargetTests(unittest.TestCase):
    def test_the_default_list_is_the_runners_cli_targets(self):
        clients = smoke_tier().CLIENTS
        self.assertEqual(sorted(probe.DEFAULT_TARGETS), sorted(clients))

    def test_a_mac_runs_every_target_and_skips_none(self):
        run, skipped = probe.by_default("Darwin")
        self.assertEqual(sorted(run), sorted(probe.DEFAULT_TARGETS))
        self.assertEqual(skipped, [])

    def test_a_linux_host_skips_the_macos_targets_rather_than_failing_them(self):
        run, skipped = probe.by_default("Linux")
        self.assertEqual(run, ["claude-code-cli-linux", "codex-cli-linux"])
        self.assertEqual([target for target, _ in skipped],
                         ["claude-code-cli-macos", "codex-cli-macos"])
        self.assertIn("runs only on a macos host", skipped[0][1])


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def run_main(self, targets, env, host="Darwin"):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.dict(
                os.environ, {"HOME": str(self.home), "PATH": "/usr/bin"}), patch.object(
                probe.platform, "system", return_value=host), patch.object(
                probe.shutil, "which", on_path("codex", "claude")):
            with redirect_stdout(out), redirect_stderr(err):
                code = probe.main(["--targets", targets] if targets else [])
        return code, out.getvalue(), err.getvalue()

    def test_a_ready_linux_host_passes_the_default_and_names_what_it_skipped(self):
        env = {"OPENAI_API_KEY": PRESENT, "ANTHROPIC_API_KEY": PRESENT}
        code, out, err = self.run_main(None, env, host="Linux")
        self.assertEqual(code, 0, err)
        self.assertIn("codex-cli-macos: skipped, runs only on a macos host", out)
        self.assertIn("claude-code-cli-macos: skipped", out)
        self.assertEqual(err, "")

    def test_a_macos_target_named_on_a_linux_host_is_still_a_failure(self):
        code, _, err = self.run_main("codex-cli-macos", {"OPENAI_API_KEY": PRESENT}, host="Linux")
        self.assertEqual(code, 1)
        self.assertIn("runs only on a macos host", err)

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

    def test_with_no_targets_the_probe_chooses_the_hosts_own_default(self):
        argv = self.credentials()["argv"]
        self.assertEqual(argv[-1], "harness_core.target_preconditions")
        self.assertNotIn("--targets", argv)

    def test_the_round_can_name_only_the_targets_it_runs(self):
        self.assertEqual(self.credentials(["codex-cli-linux"])["argv"][-1], "codex-cli-linux")

    def test_an_unknown_target_is_refused_before_anything_runs(self):
        with patch.object(self.module.subprocess, "Popen",
                          side_effect=AssertionError("a check ran")):
            with self.assertRaises(SystemExit) as caught:
                self.module.main(["--targets", "cursor", "--only", "credentials"])
        self.assertIn("unknown target: cursor", str(caught.exception))


def round_driver():
    path = REPO / "scripts" / "qualification_round.py"
    spec = importlib.util.spec_from_file_location("qualification_round_targets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.driver = round_driver()

    def argv(self, targets):
        with patch.object(self.driver.subprocess, "run") as run:
            self.driver.smoke("/round/clone", {}, targets)
        return run.call_args[0][0]

    def test_the_round_checks_only_the_targets_it_runs(self):
        argv = self.argv(["claude-code-cli-macos"])
        self.assertEqual(argv[-2:], ["--targets", "claude-code-cli-macos"])

    def test_the_round_passes_its_target_list_to_the_tier(self):
        with tempfile.TemporaryDirectory() as directory:
            round_dir = Path(directory)
            (round_dir / "clone").mkdir()
            (round_dir / "provision.json").write_text(json.dumps(
                {"clone": str(round_dir / "clone"), "records": str(round_dir / "records"),
                 "source_commit": "0" * 40}))
            seen = []
            with patch.object(self.driver, "smoke",
                              side_effect=lambda clone, env, targets=(): seen.append(targets)), \
                    patch.object(self.driver.subprocess, "run", return_value=None):
                self.driver.run_round(round_dir, ["claude-code-cli-macos"], None, [])
        self.assertEqual(seen, [["claude-code-cli-macos"]])


if __name__ == "__main__":
    unittest.main()
