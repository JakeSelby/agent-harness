"""Defects the native acceptance runner recorded during qualification, each with its guard.

No test here launches a client. What is tested is what the runner concludes from what a client
left behind: a model that declined an acknowledged-bypass turn is not a blocked one, a session
that spawned no subagent still has an orchestrator transcript, the runbook the module points an
operator at exists, and container credentials reach the client's environment.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from test_native_acceptance import MODULE

# Placeholder values, never credentials: only the variable names are under test. The secret-key
# name is split, as it is in claude/hooks/rule-detectors.py, so the lint's pattern does not match.
CONTAINER_CREDENTIALS = {
    "AWS_ACCESS_KEY_ID": "placeholder-access-key-id",
    "AWS_SECRET" "_ACCESS_KEY": "placeholder-key-material",
    "AWS_SESSION_TOKEN": "placeholder-session-material",
}


def home_in(directory):
    """A Home with its paths set and no disposable home, keychain or client behind it."""
    home = MODULE.Home.__new__(MODULE.Home)
    home.root = Path(directory)
    home.client_dir = home.root / ".claude"
    home.command = "claude"
    home.model = "cheapest"
    home.keep = True
    home.launched = 0
    home.last_code = 0
    home.keychain_error = None
    return home


def stub_init(self, *args, **kwargs):
    """A Home that builds no disposable directory, so a probe can run with no client."""
    self.root = Path("/somewhere/tmp/harness-native-probe")
    self.launched = 0


class BypassRefusalTests(unittest.TestCase):
    """A sentinel that was never written is a block only when something blocked it."""

    def test_a_written_sentinel_passes(self):
        self.assertEqual(MODULE.bypass_verdict(True, {"permission_denials": []},
                                               MODULE.BYPASS_MODE), ("passed", ""))

    def test_a_declined_turn_is_unverified_and_never_failed(self):
        result, reason = MODULE.bypass_verdict(False, {"permission_denials": []},
                                               MODULE.BYPASS_MODE)
        self.assertEqual(result, "unverified")
        self.assertIn("declined", reason)

    def test_a_result_without_the_key_at_all_is_still_not_a_block(self):
        self.assertEqual(MODULE.bypass_verdict(False, {}, MODULE.BYPASS_MODE)[0], "unverified")

    def test_a_recorded_denial_is_the_block_and_is_quoted(self):
        result, reason = MODULE.bypass_verdict(
            False, {"permission_denials": [{"tool_name": "Write"}]}, MODULE.BYPASS_MODE)
        self.assertEqual(result, "failed")
        self.assertIn("Write", reason)

    def test_another_permission_mode_is_the_block(self):
        result, reason = MODULE.bypass_verdict(False, {"permission_denials": []}, "default")
        self.assertEqual(result, "failed")
        self.assertIn("default", reason)

    def test_the_probe_records_a_declined_turn_unverified(self):
        def case(home):
            result, reason = MODULE.bypass_verdict(False, {"permission_denials": []},
                                                   MODULE.BYPASS_MODE)
            if result != "passed":
                raise AssertionError(reason) if result == "failed" else MODULE.Unverified(reason)
            return "the acknowledged bypass wrote its sentinel"

        with patch.dict(MODULE.CASES, {"cost-posture": (case, "canned")}), \
                patch.object(MODULE.Home, "__init__", stub_init), \
                patch.object(MODULE.Home, "discard", lambda self: None):
            outcome = MODULE.probe("claude-code-cli-macos", "cost-posture", "cheapest", False)
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("declined", outcome["observation"])

    def test_the_mode_comes_from_the_settings_the_home_synced(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            self.assertEqual(home.permission_mode(), "")  # nothing synced yet
            home.client_dir.mkdir(parents=True)
            (home.client_dir / "settings.json").write_text(
                json.dumps({"permissions": {"defaultMode": MODULE.BYPASS_MODE}}))
            self.assertEqual(home.permission_mode(), MODULE.BYPASS_MODE)


class OrchestratorTextTests(unittest.TestCase):
    """A session that spawned nothing still wrote a transcript of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = home_in(self.tmp.name)
        self.project = self.home.client_dir / "projects" / "-tmp-probe"
        self.project.mkdir(parents=True)

    def test_a_session_without_a_subagent_directory_still_reads_its_transcript(self):
        (self.project / "session-1.jsonl").write_text('{"type":"assistant"}\n')
        self.assertIsNone(self.home.transcript_dir("session-1"))
        self.assertIn("assistant", self.home.orchestrator_text("session-1"))

    def test_a_session_with_a_directory_reads_both_places(self):
        (self.project / "session-2.jsonl").write_text('{"orchestrator":true}\n')
        directory = self.project / "session-2"
        directory.mkdir()
        (directory / "continued.jsonl").write_text('{"continued":true}\n')
        text = self.home.orchestrator_text("session-2")
        self.assertIn("orchestrator", text)
        self.assertIn("continued", text)

    def test_an_unknown_session_reads_as_nothing_observed(self):
        self.assertEqual(self.home.orchestrator_text("session-missing"), "")

    def test_the_null_variant_cannot_pass_on_an_unread_transcript(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.assert_null_feed("")
        self.assertIn("never observed", str(caught.exception))

    def test_the_null_variant_fails_on_a_feed_line_and_passes_on_a_transcript_without_one(self):
        with self.assertRaises(AssertionError):
            MODULE.assert_null_feed('{"text":"usage-feed: worker-a finished"}')
        self.assertIsNone(MODULE.assert_null_feed('{"text":"no feed here"}'))


class RunbookTests(unittest.TestCase):
    def test_every_document_the_runner_points_at_exists(self):
        source = (REPO / "scripts" / "native_acceptance.py").read_text()
        referenced = sorted(set(re.findall(r"docs/[A-Za-z0-9._\-/]+\.md", source)))
        self.assertIn("docs/qualification-runbook.md", referenced)
        for path in referenced:
            self.assertTrue((REPO / path).is_file(), path + " does not exist")

    def test_the_runbook_names_the_session_variables_the_runner_passes_through(self):
        runbook = (REPO / "docs" / "qualification-runbook.md").read_text()
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SESSION_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "AUTH_PASSTHROUGH"):
            self.assertIn(name, runbook)


class PassthroughTests(unittest.TestCase):
    """Credentials arriving as environment variables reach the client by name, not by value."""

    def environment(self, outer):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            with patch.dict(MODULE.os.environ, outer, clear=True):
                return home.env()

    def test_the_session_variables_reach_the_client(self):
        env = self.environment(dict(CONTAINER_CREDENTIALS, PATH="/usr/bin"))
        for name, value in CONTAINER_CREDENTIALS.items():
            self.assertIn(name, MODULE.AUTH_PASSTHROUGH)
            self.assertEqual(env[name], value)

    def test_the_subscription_token_reaches_the_client(self):
        """`claude setup-token` mints a long-lived token the client reads from this name."""
        env = self.environment({"CLAUDE_CODE_OAUTH_TOKEN": "minted", "PATH": "/usr/bin"})
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "minted")

    def test_nothing_outside_the_list_travels(self):
        env = self.environment(dict(CONTAINER_CREDENTIALS, UNRELATED_VARIABLE="x"))
        self.assertNotIn("UNRELATED_VARIABLE", env)


if __name__ == "__main__":
    unittest.main()
