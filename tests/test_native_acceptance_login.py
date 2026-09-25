"""The acceptance runner links the Codex session login only when asked, and never records it.

No test launches a client. A fake login file stands in for `auth.json`, and every value in it is
checked to be absent from each observation, the durable progress log and the printed record.
"""
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO


def load():
    path = REPO / "scripts" / "native_acceptance.py"
    spec = importlib.util.spec_from_file_location("native_acceptance_login", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load()
CODEX = "codex-cli-macos"
CLAUDE = "claude-code-cli-macos"
ACCESS = "eyJhbGciOiJSUzI1NiJ9-fake_access.part-two_x"
REFRESH = "rt_fake-refresh-value-0042"
ACCOUNT = "acct-fixture-7731"
LOGIN = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
         "tokens": {"access_token": ACCESS, "refresh_token": REFRESH, "account_id": ACCOUNT}}
SECRETS = (ACCESS, REFRESH, ACCOUNT)


class LoginFixture(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(tempfile.mkdtemp(prefix="login-test-"))
        self.addCleanup(shutil.rmtree, str(self.scratch), True)
        self.source = self.scratch / "operator-codex"
        self.source.mkdir()
        (self.source / "auth.json").write_text(json.dumps(LOGIN))
        self.homes = []

    def stub_init(self, home, spec, label, model, keep=False):
        home.spec, home.runtime, home.command = spec, spec["runtime"], spec["command"]
        home.home_var, home.model, home.keep = spec["home_var"], model, keep
        home.root = self.scratch / ("home-" + label + "-%d" % len(self.homes))
        home.root.mkdir()
        home.project = home.root / "project"
        home.client_dir = home.root / spec["home_dir"]
        home.launched, home.last_code, home.keychain_error = 0, 0, None
        self.homes.append(home)

    def probe(self, case, client=CODEX, login=None):
        fixture = self

        def init(home, *args, **kwargs):
            fixture.stub_init(home, *args, **kwargs)
        with patch.dict(MODULE.CASES, {"installation": (case, "canned")}), \
                patch.object(MODULE.Home, "__init__", init), \
                patch.object(MODULE.Home, "discard", lambda self: None):
            return MODULE.probe(client, "installation", "cheapest", False, [CODEX],
                                login=login)

    def assertNoSecret(self, text):
        for secret in SECRETS:
            self.assertNotIn(secret, text)


class LinkTests(LoginFixture):
    def test_without_the_flag_the_home_receives_no_login(self):
        seen = []
        outcome = self.probe(lambda home: seen.append(home.client_dir) or "ran")
        self.assertEqual(outcome["result"], "passed")
        self.assertFalse((seen[0] / "auth.json").exists())
        self.assertFalse((seen[0] / "auth.json").is_symlink())

    def test_with_the_flag_the_home_points_at_the_login_and_holds_no_copy(self):
        seen = []

        def case(home):
            link = home.client_dir / "auth.json"
            seen.append((link.is_symlink(), Path(str(link.resolve())),
                         json.loads(link.read_text())))
            return "ran"
        outcome = self.probe(case, login=self.source)
        self.assertEqual(outcome["result"], "passed")
        linked, target, data = seen[0]
        self.assertTrue(linked)
        self.assertEqual(target, (self.source / "auth.json").resolve())
        self.assertEqual(data, LOGIN)

    def test_a_claude_code_home_refuses_a_login_as_unverified(self):
        outcome = self.probe(lambda home: "ran", client=CLAUDE, login=self.source)
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("only a Codex client", outcome["observation"])

    def test_a_missing_login_file_is_unverified_not_a_pass(self):
        (self.source / "auth.json").unlink()
        outcome = self.probe(lambda home: "ran", login=self.source)
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("run codex login", outcome["observation"])


class RedactionTests(LoginFixture):
    def test_a_passing_observation_that_echoes_the_login_is_redacted(self):
        outcome = self.probe(lambda home: "client said " + " and ".join(SECRETS),
                             login=self.source)
        self.assertNoSecret(json.dumps(outcome))
        self.assertIn(MODULE.REDACTED, outcome["observation"])

    def test_a_failed_assertion_that_echoes_the_login_is_redacted(self):
        def case(home):
            raise AssertionError("expected nothing, read " + (home.client_dir / "auth.json")
                                 .read_text())
        outcome = self.probe(case, login=self.source)
        self.assertEqual(outcome["result"], "failed")
        self.assertNoSecret(json.dumps(outcome))

    def test_an_unexpected_error_that_echoes_the_login_is_redacted(self):
        def case(home):
            raise RuntimeError("stderr: " + REFRESH + " " + ACCESS)
        outcome = self.probe(case, login=self.source)
        self.assertEqual(outcome["result"], "unverified")
        self.assertNoSecret(json.dumps(outcome))

    def test_redact_removes_a_literal_secret_whatever_its_shape(self):
        self.assertEqual(MODULE.redact("a short-ish tok3n here", secrets=["short-ish tok3n"]),
                         "a " + MODULE.REDACTED + " here")
        self.assertEqual(MODULE.redact("unchanged text"), "unchanged text")

    def test_login_secrets_reads_every_long_string_and_tolerates_a_bad_file(self):
        found = MODULE.login_secrets(self.source / "auth.json")
        self.assertEqual(sorted(found), sorted(SECRETS))
        (self.source / "auth.json").write_text("not json")
        self.assertEqual(MODULE.login_secrets(self.source / "auth.json"), [])
        self.assertEqual(MODULE.login_secrets(self.source / "absent.json"), [])

    def test_the_progress_log_and_printed_record_carry_no_credential(self):
        fixture = self
        progress = self.scratch / "round.partial.jsonl"
        out = self.scratch / "record.json"

        def init(home, *args, **kwargs):
            fixture.stub_init(home, *args, **kwargs)

        def case(home):
            return "echo " + (home.client_dir / "auth.json").read_text()
        buffer = io.StringIO()
        with patch.dict(MODULE.CASES, {"installation": (case, "canned")}), \
                patch.dict("os.environ", {"CODEX_HOME": str(self.source)}), \
                patch.object(MODULE.Home, "__init__", init), \
                patch.object(MODULE.Home, "discard", lambda self: None), \
                patch.object(MODULE, "host_mismatch", return_value=""), \
                patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else "a" * 40), \
                redirect_stdout(buffer):
            MODULE.main(["--client", CODEX, "--cases", "installation", "--codex-session-login",
                         "--home-confirmed", CODEX, "--progress", str(progress),
                         "--out", str(out)])
        self.assertTrue(self.homes and (self.homes[0].client_dir / "auth.json").is_symlink())
        for text in (progress.read_text(), out.read_text(), buffer.getvalue()):
            self.assertNoSecret(text)
        self.assertIn(MODULE.REDACTED, out.read_text())


class FlagTests(LoginFixture):
    def test_record_passes_a_login_only_when_one_is_given(self):
        calls = []

        def runner(client, name, model, keep, confirmed=(), **extra):
            calls.append(extra)
            return {"case": name, "result": "passed", "observation": "ok"}
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else "a" * 40):
            MODULE.record(CODEX, ["installation"], "cheapest", False, runner=runner)
            MODULE.record(CODEX, ["installation"], "cheapest", False, runner=runner,
                          login=self.source)
        self.assertEqual(calls, [{}, {"login": self.source}])

    def test_the_login_source_is_codex_home_then_the_real_home(self):
        self.assertEqual(MODULE.login_source({"CODEX_HOME": "/x/codex", "HOME": "/y"}),
                         Path("/x/codex"))
        self.assertEqual(MODULE.login_source({"HOME": "/y"}), Path("/y/.codex"))

    def test_session_login_refuses_a_claude_client_and_a_missing_login(self):
        with self.assertRaises(SystemExit) as caught:
            MODULE.session_login(CLAUDE, {"CODEX_HOME": str(self.source)})
        self.assertIn("for a Codex client", str(caught.exception))
        with self.assertRaises(SystemExit) as caught:
            MODULE.session_login(CODEX, {"CODEX_HOME": str(self.scratch / "nowhere")})
        self.assertIn("no auth.json", str(caught.exception))
        self.assertEqual(MODULE.session_login(CODEX, {"CODEX_HOME": str(self.source)}),
                         self.source)

    def test_the_flag_is_off_by_default_and_named_in_the_plan_when_on(self):
        def dry(*extra):
            buffer = io.StringIO()
            with patch.dict("os.environ", {"CODEX_HOME": str(self.source)}), \
                    patch.object(MODULE, "probe", side_effect=AssertionError("a case ran")), \
                    redirect_stdout(buffer):
                self.assertEqual(MODULE.main(["--client", CODEX, "--dry-plan"] + list(extra)), 0)
            return buffer.getvalue()
        self.assertNotIn("login:", dry())
        planned = dry("--codex-session-login")
        self.assertIn("login: " + MODULE.LOGIN_NOTE, planned)
        self.assertNoSecret(planned)

    def test_the_flag_on_a_claude_client_stops_before_any_case(self):
        with patch.object(MODULE, "probe", side_effect=AssertionError("a case ran")), \
                self.assertRaises(SystemExit):
            MODULE.main(["--client", CLAUDE, "--codex-session-login", "--dry-plan"])


if __name__ == "__main__":
    unittest.main()
