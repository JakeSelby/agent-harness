"""The native acceptance runner plans without a client, redacts, and never invents a pass.

No test here launches a client: every native probe costs money and would make the suite depend
on an account. What is tested is the runner's contract — the plan runs nothing, a case that
raises is never `passed`, the record validates against the repository's own evidence validator,
redaction removes home paths and credential shapes, and a dirty checkout is refused.
"""
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from harness_core import compatibility


def load():
    path = REPO / "scripts" / "native_acceptance.py"
    spec = importlib.util.spec_from_file_location("native_acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load()
CLIENT = "claude-code-cli-macos"


def stub_probe(client, name, model, keep):
    return {"case": name, "result": "passed", "observation": "A native session did the thing.",
            "seconds": 0.1, "sessions": 1}


class PlanTests(unittest.TestCase):
    def test_a_dry_plan_runs_no_client_and_no_case(self):
        buffer = io.StringIO()
        with patch.object(MODULE, "probe", side_effect=AssertionError("a case ran")), \
                patch.object(MODULE.subprocess, "run", side_effect=AssertionError("a process ran")):
            with redirect_stdout(buffer):
                self.assertEqual(MODULE.main(["--client", CLIENT, "--dry-plan"]), 0)
        printed = buffer.getvalue()
        self.assertIn("no client run", printed)
        for case in MODULE.catalog()["required_cases"]:
            self.assertIn(case, printed)

    def test_every_required_case_is_registered_and_unknown_ones_are_refused(self):
        required = MODULE.catalog()["required_cases"]
        self.assertEqual(MODULE.selected("all"), required)
        self.assertTrue(set(MODULE.CASES) <= set(required))
        with self.assertRaises(SystemExit):
            MODULE.selected("no-such-case")


class RecordTests(unittest.TestCase):
    def record(self, runner=stub_probe, names=None):
        with patch.object(MODULE, "client_version", return_value="9.9.9"), \
                patch.object(MODULE, "git", side_effect=lambda *args: "" if args[0] == "status"
                             else "a" * 40):
            return MODULE.record(CLIENT, names or list(MODULE.catalog()["required_cases"]),
                                 "cheapest", False, runner=runner)

    def test_the_record_validates_against_the_repository_evidence_validator(self):
        # Every case passing is what a complete claim looks like; the validator rejects the rest.
        automated = {case: (None, "stub") for case in MODULE.catalog()["required_cases"]}
        with patch.dict(MODULE.CASES, automated):
            data = self.record()
        self.assertEqual(sorted(data), ["cases", "client", "client_version", "harness_version",
                                        "kind", "observations", "platform", "runtime_version",
                                        "source_commit"])
        catalog = MODULE.catalog()
        data["source_commit"] = MODULE.run(["git", "-C", str(REPO), "rev-parse", "HEAD"]).stdout.strip()
        data["runtime_version"] = data["client_version"] = "2.0.0"
        rendered = json.dumps(data).encode()
        client = {"id": CLIENT, "runtime_version": "2.0.0", "client_version": "2.0.0",
                  "platform": "macos",
                  "evidence": [{"path": "compatibility/catalog.json",
                                "sha256": hashlib.sha256(rendered).hexdigest()}]}
        with patch.object(compatibility.Path, "read_bytes", return_value=rendered):
            self.assertEqual(compatibility.evidence_errors(REPO, catalog, client), [])

    def test_an_unautomated_case_is_unverified_with_its_reason(self):
        data = self.record()
        self.assertEqual(data["cases"]["migration-uninstall"], "unverified")
        self.assertIn(MODULE.NOT_AUTOMATED, data["observations"])

    def test_a_dirty_checkout_is_refused_before_any_client_runs(self):
        with patch.object(MODULE, "git", return_value=" M bin/harness"):
            with self.assertRaisesRegex(SystemExit, "clean"):
                MODULE.record(CLIENT, ["cost-posture"], "cheapest", False,
                              runner=lambda *args: self.fail("a case ran on a dirty checkout"))


HOME_PATH = "/somewhere/tmp/harness-native-cost-posture-x"


def fake_home(self, *args, **kwargs):
    self.root = Path(HOME_PATH)
    self.launched = 0


class FailureTests(unittest.TestCase):
    def outcome(self, error):
        def case(home):
            raise error
        with patch.dict(MODULE.CASES, {"cost-posture": (case, "raises")}), \
                patch.object(MODULE.Home, "__init__", fake_home), \
                patch.object(MODULE.Home, "discard", lambda self: None):
            return MODULE.probe(CLIENT, "cost-posture", "cheapest", False)

    def test_a_failed_assertion_is_recorded_failed_with_its_reason(self):
        outcome = self.outcome(AssertionError("an unnamed spawn ran as general-purpose"))
        self.assertEqual(outcome["result"], "failed")
        self.assertIn("general-purpose", outcome["observation"])

    def test_an_unobserved_case_is_unverified_and_never_passed(self):
        outcome = self.outcome(MODULE.Unverified("the client wrote no subagent transcript"))
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("no subagent transcript", outcome["observation"])

    def test_an_unexpected_error_is_unverified_and_names_its_type(self):
        outcome = self.outcome(RuntimeError("the probe home vanished"))
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("RuntimeError", outcome["observation"])


class FeedSpendTests(unittest.TestCase):
    """Canned feed lines, so the classification is tested without launching a client."""

    def test_a_measured_line_against_a_budget_satisfies_the_sub_check(self):
        for line in ("usage-feed: worker-a finished at 282 output tokens and 1 tool call "
                     "— 0.0× its budget of 10,200 / 21",
                     "usage-feed: worker-a finished at 12,400 output tokens and 30 tool calls "
                     "(so far) — 1.2× its budget of 10,200 / 21",
                     "usage-feed: worker-a finished at 1 output token and 0 tool calls "
                     "— over budget 2.0× its budget of 1 output token"):
            self.assertEqual(MODULE.spend_complaint(line), "")

    def test_an_unmeasured_or_unbudgeted_line_fails_the_case_and_is_quoted(self):
        unknown = "usage-feed: worker-a finished, spend unknown"
        unbudgeted = "usage-feed: worker-a finished at 282 output tokens and 1 tool call"
        self.assertIn("no measured spend", MODULE.spend_complaint(unknown))
        self.assertIn(unknown, MODULE.spend_complaint(unknown))
        self.assertIn("against no budget", MODULE.spend_complaint(unbudgeted))
        self.assertIn(unbudgeted, MODULE.spend_complaint(unbudgeted))

    def test_the_case_records_failed_when_the_feed_reports_no_spend(self):
        def case(home):
            raise AssertionError(MODULE.spend_complaint("usage-feed: worker-a finished, "
                                                        "spend unknown"))
        with patch.dict(MODULE.CASES, {"cost-posture": (case, "canned")}), \
                patch.object(MODULE.Home, "__init__", fake_home), \
                patch.object(MODULE.Home, "discard", lambda self: None):
            outcome = MODULE.probe(CLIENT, "cost-posture", "cheapest", False)
        self.assertEqual(outcome["result"], "failed")
        self.assertIn("spend unknown", outcome["observation"])


class KeychainTests(unittest.TestCase):
    """A disposable home on macOS carries its own default keychain, so no store raises a dialog."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def completed(self, code, stderr=""):
        return subprocess.CompletedProcess([], code, stdout="", stderr=stderr)

    def test_other_hosts_run_nothing(self):
        with patch.object(MODULE, "run", side_effect=AssertionError("a process ran")):
            self.assertIsNone(MODULE.keychain(self.home, host="Linux"))
        self.assertFalse((self.home / "Library").exists())

    def test_macos_creates_the_keychain_inside_the_disposable_home(self):
        with patch.object(MODULE, "run", return_value=self.completed(0)) as ran:
            path = MODULE.keychain(self.home, host="Darwin")
        self.assertEqual(path, self.home / "Library" / "Keychains" / "login.keychain-db")
        self.assertTrue(path.parent.is_dir())
        create = ran.call_args_list[0]
        self.assertEqual(create.args[0][:2], ["security", "create-keychain"])
        self.assertEqual(create.args[0][-1], path)
        for call in ran.call_args_list:
            self.assertEqual(call.kwargs["env"]["HOME"], str(self.home))

    def test_a_home_without_a_keychain_refuses_a_client_turn(self):
        failed = self.completed(1, "security: could not create")
        with patch.object(MODULE.platform, "system", return_value="Darwin"), \
                patch.object(MODULE, "run", return_value=failed) as ran:
            home = MODULE.Home("claude", "kc", "haiku")
            self.addCleanup(home.discard)
            launches = len(ran.call_args_list)
            with self.assertRaises(MODULE.Unverified) as caught:
                home.session("hello")
        self.assertIn("could not create", str(caught.exception))
        self.assertEqual(len(ran.call_args_list), launches)
        self.assertEqual(home.launched, 0)


class RedactionTests(unittest.TestCase):
    def test_home_paths_become_a_tilde(self):
        text = MODULE.redact("read /somewhere/tmp/harness-native-x/.claude/settings.json",
                             ["/somewhere/tmp/harness-native-x"])
        self.assertNotIn("harness-native-x", text)
        self.assertIn("~/.claude/settings.json", text)

    def test_credential_shapes_and_identities_are_removed(self):
        # Assembled here so the fixtures are not themselves secret-shaped literals in source.
        for secret in ("sk-" + "ant-api03-" + "A" * 20, "AKI" + "A" + "B" * 16,
                       "ghp" + "_" + "c" * 36, "Authorization: Bearer " + "d" * 16,
                       "fixture" + "@" + "example.invalid",
                       "3f2a1b4c-5d6e-7f80-91a2-" + "b" * 12):
            self.assertNotIn(secret.split()[-1], MODULE.redact("probe said " + secret))

    def test_an_observation_carries_no_temporary_home_path(self):
        outcome = FailureTests().outcome(AssertionError(HOME_PATH + "/.claude broke"))
        self.assertNotIn("harness-native", outcome["observation"])
        self.assertIn("~/.claude broke", outcome["observation"])


if __name__ == "__main__":
    unittest.main()
