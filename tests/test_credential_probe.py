# SPDX-License-Identifier: MIT
"""The credential probe reports an unauthenticatable environment as an error, and does it at once.

The failure it exists to catch is a container whose only login is an interactive session: the
client then waits for a login it will never receive and the run ends as a 300-second timeout
instead of naming the missing credential.
"""
import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from harness_core import credentials

# Placeholders, never credentials: the probe tests presence and never reads a value.
PRESENT = "placeholder-value"
ANSWERS_WITHIN_SECONDS = 5.0


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def unreachable(self, env, home=None):
        with self.assertRaises(credentials.Unreachable) as caught:
            credentials.reachable(env, home if home is not None else self.home)
        return str(caught.exception)

    def test_an_api_key_in_the_environment_is_the_reachable_credential(self):
        for name in credentials.API_KEY_VARS:
            self.assertEqual(credentials.reachable({name: PRESENT}, self.home), name)

    def test_an_empty_value_does_not_count_as_a_credential(self):
        self.assertIn("no API key", self.unreachable({"ANTHROPIC_API_KEY": ""}))

    def test_a_cloud_profile_with_a_file_pointer_is_reachable(self):
        path = self.home / "credentials-file"
        path.touch()
        env = {"AWS_PROFILE": "acceptance", "AWS_SHARED_CREDENTIALS_FILE": str(path)}
        self.assertEqual(credentials.reachable(env, self.home), "AWS_PROFILE")

    def test_a_cloud_profile_with_no_file_pointer_is_unreachable(self):
        message = self.unreachable({"AWS_PROFILE": "acceptance"})
        self.assertIn("AWS_PROFILE is set but neither", message)

    def test_a_pointer_to_a_file_that_does_not_exist_names_the_variable(self):
        env = {"ANTHROPIC_API_KEY": PRESENT,
               "AWS_CONFIG_FILE": str(self.home / "absent" / "config")}
        message = self.unreachable(env)
        self.assertIn("AWS_CONFIG_FILE names a file that does not exist", message)

    def test_a_service_account_file_that_exists_is_reachable(self):
        path = self.home / "service-account.json"
        path.write_text("{}\n")
        env = {"GOOGLE_APPLICATION_CREDENTIALS": str(path)}
        self.assertEqual(credentials.reachable(env, self.home),
                         "GOOGLE_APPLICATION_CREDENTIALS")

    def test_a_home_holding_only_a_session_login_is_reported_as_the_error_it_is(self):
        login = self.home / ".claude" / ".credentials.json"
        login.parent.mkdir()
        login.write_text("{}\n")
        message = self.unreachable({})
        self.assertIn(".claude/.credentials.json", message)
        self.assertIn("does not travel into the disposable home", message)

    def test_a_codex_session_login_is_reported_too(self):
        login = self.home / ".codex" / "auth.json"
        login.parent.mkdir()
        login.write_text("{}\n")
        self.assertIn(".codex/auth.json", self.unreachable({}))

    def test_an_environment_with_nothing_at_all_says_the_client_would_wait(self):
        self.assertIn("wait on a login prompt until the turn timeout", self.unreachable({}))

    def test_it_answers_at_once_rather_than_hanging(self):
        started = time.time()
        self.unreachable({})
        self.assertLess(time.time() - started, ANSWERS_WITHIN_SECONDS)

    def test_it_imports_nothing_that_could_block_on_a_process_or_a_socket(self):
        blocking = ("subprocess", "socket", "ssl", "urllib", "urllib.request", "http.client")
        imported = [name for name, value in vars(credentials).items()
                    if getattr(value, "__name__", "") in blocking]
        self.assertEqual(imported, [])


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def run_main(self, env):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.dict(
                os.environ, {"HOME": str(self.home)}):
            with redirect_stdout(out), redirect_stderr(err):
                code = credentials.main()
        return code, out.getvalue(), err.getvalue()

    def test_an_unreachable_environment_exits_nonzero_with_the_reason(self):
        code, _, err = self.run_main({})
        self.assertEqual(code, 1)
        self.assertIn("credentials: unreachable:", err)

    def test_a_reachable_environment_exits_zero(self):
        code, out, _ = self.run_main({"ANTHROPIC_API_KEY": PRESENT})
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "credentials: reachable")

    def test_the_output_never_names_which_variable_was_found(self):
        """Which variable answered is derived from the environment; `reachable` returns it instead."""
        pointer = self.home / "credentials-file"
        pointer.write_text("{}\n")
        for var in credentials.REPORTABLE_VARS:
            if var == "AWS_PROFILE":
                env = {var: "acceptance", "AWS_CONFIG_FILE": str(pointer)}
            elif var == "GOOGLE_APPLICATION_CREDENTIALS":
                env = {var: str(pointer)}
            else:
                env = {var: PRESENT}
            code, out, err = self.run_main(env)
            self.assertEqual(code, 0, msg=var)
            self.assertNotIn(var, out + err, msg=var)
        self.assertEqual(credentials.reachable({"ANTHROPIC_API_KEY": PRESENT}), "ANTHROPIC_API_KEY")

    def test_only_a_known_variable_name_is_ever_printed(self):
        for name in credentials.REPORTABLE_VARS:
            self.assertIn(name, ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY",
                                 "AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS"))
        with patch.object(credentials, "reachable", return_value="SOME_OTHER_VALUE"):
            code, out, err = self.run_main({"ANTHROPIC_API_KEY": PRESENT})
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("not a reportable variable", err)
        self.assertNotIn("SOME_OTHER_VALUE", err)

    def test_the_probe_is_additive_and_records_no_qualification(self):
        before = sorted(p.name for p in (REPO / "compatibility" / "evidence").iterdir())
        self.run_main({})
        self.assertEqual(sorted(p.name for p in (REPO / "compatibility" / "evidence").iterdir()),
                         before)
        catalog = (REPO / "compatibility" / "catalog.json").read_text()
        self.assertNotIn("credentials", catalog)


if __name__ == "__main__":
    unittest.main()
