# SPDX-License-Identifier: MIT
"""Unit tests for the decision log: the rows, the joins and `usage --by decision`.

The property under test is that logging is inert. A row is written where a hook already made a
judgment, an outcome is a separate record joined at read time, and a log that cannot be written
changes no decision, no output and no exit status.

Run: python3 -m unittest discover tests
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from isolation import drop_inherited_config_dir

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


harness = _load("harness", REPO / "bin" / "harness")
decisions = _load("decisions", REPO / "claude" / "hooks" / "decisions.py")
usage_log = _load("usage_log_budget", REPO / "claude" / "hooks" / "usage-log.py")
STOP_GATE = REPO / "claude" / "hooks" / "stop-gate.py"
IDENTITY = "gate" + "@" + "example" + ".invalid"

PUSH = "git push --force origin main"
OTHER = "git push --force origin other"


class Base(unittest.TestCase):
    """A temporary HOME, so every hook writes its state where the test can read it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.log = self.home / ".local" / "state" / "agent-harness" / "decisions.jsonl"

    def env(self, extra=None):
        env = dict(os.environ)
        env.pop("CLAUDE_CONFIG_DIR", None)
        for name in list(env):
            if name.startswith("HARNESS_STANCE_"):
                env.pop(name)
        env.update({"HOME": str(self.home), "HARNESS_HOME": str(self.home)})
        env.update(extra or {})
        return env

    def config(self, block):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(block), encoding="utf-8")

    def rows(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def dispatch(self, *events):
        """Run the lifecycle coordinator in a subprocess, one event at a time.

        A subprocess, because the hooks read HOME at import and the coordinator is what both
        adapters actually run; the test then exercises the installed path rather than a
        rearrangement of it.
        """
        script = (
            "import json, sys\n"
            "sys.path.insert(0, %r)\n"
            "from harness_core import lifecycle\n"
            "for event in json.load(sys.stdin):\n"
            "    print(json.dumps(lifecycle.dispatch(sys.argv[1], event)))\n"
        ) % str(REPO / "lib")
        out = subprocess.run([sys.executable, "-c", script, "claude-code"],
                             input=json.dumps(list(events)), env=self.env(),
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        return [json.loads(line) for line in out.stdout.splitlines()]

    def bash(self, command, event="PreToolUse", session="s-1", **extra):
        payload = {"hook_event_name": event, "session_id": session, "cwd": str(self.home),
                   "tool_name": "Bash", "tool_input": {"command": command}}
        payload.update(extra)
        return payload


class BashDecisionTests(Base):
    def test_one_row_per_graded_command_with_the_later_outcome_joined(self):
        answer = self.dispatch(self.bash(PUSH),
                               self.bash(PUSH, "PostToolUse", tool_response={"stdout": ""}))[0]
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "ask")
        rows = self.rows()
        self.assertEqual([r["kind"] for r in rows], ["decision", "outcome"])
        decision, outcome = rows
        self.assertEqual(decision["point"], "grade-bash")
        self.assertEqual(decision["deterministic_answer"], "ask")
        self.assertEqual(decision["input"], PUSH)
        self.assertEqual(decision["session_id"], "s-1")
        self.assertEqual(decision["runtime"], "claude-code")
        self.assertIsNone(decision["outcome"], "a decision row is never rewritten")
        self.assertEqual(outcome["decision_id"], decision["decision_id"])
        self.assertEqual(outcome["outcome"], "ran")
        joined = decisions.joined(rows)
        self.assertEqual([(r["point"], r["outcome"]) for r in joined], [("grade-bash", "ran")])

    def test_an_approved_command_is_not_a_decision(self):
        self.assertEqual(self.dispatch(self.bash("git status"))[0]["hookSpecificOutput"]
                         ["permissionDecision"], "allow")
        self.assertEqual(self.rows(), [])

    def test_a_completed_command_nothing_was_asked_about_writes_no_outcome(self):
        self.dispatch(self.bash("git status", "PostToolUse", tool_response={"stdout": ""}))
        self.assertEqual(self.rows(), [])

    def test_an_ask_with_no_post_tool_use_reads_not_run_at_session_end(self):
        self.dispatch(self.bash(PUSH), self.bash(OTHER),
                      self.bash(PUSH, "PostToolUse", tool_response={"stdout": ""}),
                      {"hook_event_name": "SessionEnd", "session_id": "s-1",
                       "cwd": str(self.home)})
        joined = {r["input"]: r["outcome"] for r in decisions.joined(self.rows())}
        self.assertEqual(joined, {PUSH: "ran", OTHER: "not_run"})

    def test_session_end_settles_only_its_own_session(self):
        self.dispatch(self.bash(PUSH, session="s-1"), self.bash(OTHER, session="s-2"),
                      {"hook_event_name": "SessionEnd", "session_id": "s-1",
                       "cwd": str(self.home)})
        joined = {r["input"]: r["outcome"] for r in decisions.joined(self.rows())}
        self.assertEqual(joined, {PUSH: "not_run", OTHER: None})

    def test_a_second_session_end_does_not_label_a_decision_twice(self):
        end = {"hook_event_name": "SessionEnd", "session_id": "s-1", "cwd": str(self.home)}
        self.dispatch(self.bash(PUSH), end, end)
        self.assertEqual([r["kind"] for r in self.rows()], ["decision", "outcome"])


class BoundsTests(Base):
    def test_the_input_is_capped_and_the_hash_is_over_the_whole_text(self):
        long = "x" * (decisions.MAX_INPUT + 500)
        identity = decisions.record("grade-bash", "ask", long, {"session_id": "s-1"},
                                    target=self.log)
        row = self.rows()[0]
        self.assertEqual(row["decision_id"], identity)
        self.assertEqual(len(row["input"]), decisions.MAX_INPUT)
        self.assertEqual(row["input_sha256"], decisions.digest(long))
        self.assertNotEqual(row["input_sha256"], decisions.digest(row["input"]))

    def test_the_cap_is_two_kibibytes(self):
        self.assertEqual(decisions.MAX_INPUT, 2048)

    def test_the_log_is_owner_only_in_an_owner_only_directory(self):
        decisions.record("grade-bash", "ask", PUSH, {}, target=self.log)
        self.assertEqual(os.stat(str(self.log)).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(str(self.log.parent)).st_mode & 0o777, 0o700)

    def test_a_decision_id_is_reproducible_from_the_match_key(self):
        event = {"session_id": "s-1"}
        self.assertEqual(decisions.match_key(event, PUSH),
                         "s-1:" + decisions.digest(PUSH))
        self.assertEqual(decisions.match_key({"session_id": "s-1", "tool_use_id": "tu-9"}, PUSH),
                         "tu-9")
        key = decisions.match_key(event, PUSH)
        self.assertEqual(decisions.record("grade-bash", "ask", PUSH, event, key=key,
                                          target=self.log),
                         decisions.decision_id("grade-bash", key))

    def test_the_first_outcome_recorded_is_the_one_that_holds(self):
        identity = decisions.record("grade-bash", "ask", PUSH, {}, key="k", target=self.log)
        decisions.observe(identity, "ran", "grade-bash", "", target=self.log)
        decisions.observe(identity, "not_run", "grade-bash", "", target=self.log)
        self.assertEqual([r["outcome"] for r in decisions.joined(self.rows())], ["ran"])

    def test_an_outcome_for_a_decision_that_was_never_logged_is_not_written(self):
        self.assertFalse(decisions.observe_if_logged("deadbeef", "ran", target=self.log))
        self.assertEqual(self.rows(), [])


class SwitchTests(Base):
    def test_with_the_decision_log_off_nothing_is_written_at_all(self):
        self.config({"telemetry": {"decisions": False}})
        answer = self.dispatch(self.bash(PUSH),
                               self.bash(PUSH, "PostToolUse", tool_response={"stdout": ""}))[0]
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertFalse(self.log.exists())
        self.assertFalse(self.log.parent.exists())

    def test_the_switch_defaults_to_on_and_is_validated_with_the_rest_of_the_block(self):
        telemetry = _load("telemetry_decisions", REPO / "claude" / "hooks" / "telemetry.py")
        self.assertTrue(telemetry.settings({"telemetry": {}})["decisions"])
        self.assertFalse(telemetry.settings({"telemetry": {"decisions": False}})["decisions"])
        with self.assertRaises(ValueError):
            telemetry.settings({"telemetry": {"decisions": "no"}})

    def test_a_telemetry_block_that_is_not_an_object_writes_nothing(self):
        self.assertFalse(decisions.enabled({"telemetry": "on"}))
        self.assertTrue(decisions.enabled({}))


class FailureTests(Base):
    def test_a_write_failure_leaves_the_hook_decision_unchanged_and_is_counted(self):
        # The log's own directory is a file, so every write raises. The hook must not notice.
        self.log.parent.parent.mkdir(parents=True, exist_ok=True)
        self.log.parent.write_text("not a directory", encoding="utf-8")
        results = self.dispatch(self.bash(PUSH),
                                self.bash(PUSH, "PostToolUse", tool_response={"stdout": ""}))
        self.assertEqual(results[0]["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("irreversible", results[0]["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.log.parent.read_text(encoding="utf-8"), "not a directory")

    def test_a_failed_write_is_counted_rather_than_raised(self):
        before = decisions.errors()
        self.assertIsNone(decisions.record("grade-bash", "ask", PUSH, {},
                                           target=Path(self.tmp.name) / "no" / "\0" / "x"))
        self.assertEqual(decisions.errors(), before + 1)

    def test_a_log_that_will_not_load_costs_the_lifecycle_nothing(self):
        from harness_core import lifecycle
        saved = list(lifecycle._DECISIONS)
        lifecycle._DECISIONS[:] = [None]
        try:
            lifecycle.log_bash_decision("claude-code", {"tool_input": {"command": PUSH}},
                                        [{"hookSpecificOutput": {"permissionDecision": "ask"}}])
            lifecycle.log_bash_outcome("claude-code", {"tool_input": {"command": PUSH}})
        finally:
            lifecycle._DECISIONS[:] = saved
        self.assertEqual(self.rows(), [])


class StopGateTests(Base):
    """The gate hook itself, run as the subprocess Claude Code runs, over a real repository."""

    def setUp(self):
        super().setUp()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        (self.home / ".claude.json").write_text(json.dumps(
            {"projects": {str(self.repo): {"hasTrustDialogAccepted": True}}}))
        self.git("init")
        (self.repo / "file.txt").write_text("one\n")
        self.git("add", "-A")
        self.git("commit", "-m", "initial")

    def env(self, extra=None):
        env = super().env(extra)
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Gate Fixture",
                    "GIT_COMMITTER_NAME": "Gate Fixture", "GIT_AUTHOR_EMAIL": IDENTITY,
                    "GIT_COMMITTER_EMAIL": IDENTITY})
        return env

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], env=self.env(),
                       capture_output=True, text=True, check=True)

    def write_gate(self, *commands):
        (self.repo / "AGENTS.md").write_text(
            "# a repo\n\n## Gate\n\n```sh\n" + "\n".join(commands) + "\n```\n")

    def run_hook(self):
        return subprocess.run(
            [sys.executable, str(STOP_GATE)],
            input=json.dumps({"session_id": "s-1", "cwd": str(self.repo),
                              "hook_event_name": "Stop", "stop_hook_active": False}),
            env=self.env(), capture_output=True, text=True, timeout=180)

    def test_a_red_gate_writes_a_blocked_decision_and_the_failure_it_found(self):
        self.write_gate("exit 4")
        self.assertEqual(json.loads(self.run_hook().stdout)["decision"], "block")
        decision = decisions.joined(self.rows())[0]
        self.assertEqual(decision["point"], "stop-gate")
        self.assertEqual(decision["deterministic_answer"], "blocked")
        self.assertEqual(decision["outcome"], "failed")
        self.assertEqual(decision["session_id"], "s-1")
        self.assertIn("exit 4", decision["input"])
        self.assertNotIn("\n" + "#", decision["input"], "the gate block, not the file")

    def test_a_green_gate_releases_the_turn_and_says_so(self):
        self.write_gate("true")
        self.assertEqual(self.run_hook().stdout.strip(), "")
        decision = decisions.joined(self.rows())[0]
        self.assertEqual((decision["deterministic_answer"], decision["outcome"]),
                         ("released", "passed"))

    def test_an_unchanged_tree_is_a_skip_and_not_a_second_gate_run(self):
        self.write_gate("true")
        self.run_hook()
        self.run_hook()
        answers = [(r["deterministic_answer"], r["outcome"])
                   for r in decisions.joined(self.rows())]
        self.assertEqual(answers, [("released", "passed"), ("skipped", "passed")])

    def test_an_untrusted_folder_is_recorded_as_skipped_and_the_gate_does_not_run(self):
        self.write_gate("exit 4")
        (self.home / ".claude.json").write_text(json.dumps({"projects": {}}))
        out = self.run_hook()
        self.assertEqual(out.stdout.strip(), "")
        decision = decisions.joined(self.rows())[0]
        self.assertEqual((decision["deterministic_answer"], decision["outcome"]),
                         ("skipped", "untrusted"))

    def test_a_repository_with_no_gate_block_is_no_decision_at_all(self):
        (self.repo / "AGENTS.md").write_text("# a repo\n")
        self.assertEqual(self.run_hook().stdout.strip(), "")
        self.assertEqual(self.rows(), [])


class ReportTests(Base):
    def report(self, days=30):
        args = harness.argparse.Namespace(days=days, by="decision", stance=None, rules=False,
                                          rescan=False, action=None)
        buf = io.StringIO()
        env = dict(os.environ)
        drop_inherited_config_dir()
        os.environ["HARNESS_HOME"] = str(self.home)
        # `say` is silent under HARNESS_QUIET, which another test in the suite may have set.
        os.environ.pop("HARNESS_QUIET", None)
        try:
            with contextlib.redirect_stdout(buf):
                code = harness.cmd_usage(args)
        finally:
            os.environ.clear()
            os.environ.update(env)
        return code, buf.getvalue()

    def add(self, point, answer, outcome=None, age_days=0):
        now = time.time() - age_days * 86400
        identity = decisions.record(point, answer, PUSH, {"session_id": "s-1"},
                                    target=self.log, now=now)
        if outcome is not None:
            decisions.observe(identity, outcome, point, "s-1", target=self.log, now=now)

    def test_the_report_counts_rows_outcomes_and_the_unlabelled_share(self):
        self.add("grade-bash", "ask", "ran")
        self.add("grade-bash", "ask", "not_run")
        self.add("grade-bash", "deny")
        self.add("stop-gate", "blocked", "failed")
        code, text = self.report()
        self.assertEqual(code, 0)
        line = [ln for ln in text.splitlines() if ln.startswith("grade-bash")][0]
        self.assertIn("3", line.split()[1])
        self.assertIn("33%", line)
        self.assertIn("ran 1 (50%)", line)
        self.assertIn("not_run 1 (50%)", line)
        self.assertIn("stop-gate", text)

    def test_the_window_excludes_older_decisions(self):
        self.add("grade-bash", "ask", "ran", age_days=40)
        code, text = self.report(days=7)
        self.assertEqual(code, 0)
        self.assertIn("no hook decisions recorded", text)

    def test_an_empty_log_is_said_rather_than_an_empty_table(self):
        self.assertIn("no hook decisions recorded", self.report()[1])

    def test_rules_and_stance_do_not_apply_to_this_report(self):
        args = harness.argparse.Namespace(days=30, by="decision", stance="cost", rules=False,
                                          rescan=False, action=None)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(harness.cmd_usage(args), 2)
        self.assertIn("do not apply", err.getvalue())


class SpawnPointTests(Base):
    """The two spawn hooks, run as the subprocesses the coordinator invokes."""

    SESSION = "fixture-session"

    def spawn(self, hook, tool_input):
        payload = {"tool_name": "Agent", "session_id": self.SESSION,
                   "transcript_path": str(self.home / "session.jsonl"),
                   "tool_input": tool_input}
        out = subprocess.run([sys.executable, str(REPO / "claude" / "hooks" / hook)],
                             input=json.dumps(payload), env=self.env(), capture_output=True,
                             text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def test_brief_guard_records_what_it_wrote_into_the_brief(self):
        out = self.spawn("brief-guard.py", {"prompt": "do a thing"})
        self.assertIn("400 words", out["hookSpecificOutput"]["updatedInput"]["prompt"])
        row = self.rows()[0]
        self.assertEqual(row["point"], "brief-guard")
        self.assertIn(row["deterministic_answer"], ("cap", "cap+budget"))
        self.assertEqual(row["input"], "do a thing", "the brief as the hook was given it")

    def test_an_unnamed_spawn_records_the_band_it_was_routed_to(self):
        agents = self.home / ".claude" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        for name in ("worker-a", "worker-b", "worker-c"):
            (agents / (name + ".md")).write_text(
                (REPO / "claude" / "agents" / (name + ".md")).read_text(encoding="utf-8"))
        sessions = self.home / ".local" / "state" / "agent-harness" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / (self.SESSION + ".json")).write_text(
            json.dumps({"agents": ["worker-a", "worker-b", "worker-c"], "at": 0}))
        (self.home / "session.jsonl").write_text(json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5"}}) + "\n")
        out = self.spawn("tier-agent-spawns.py", {"prompt": "x"})
        routed = out["hookSpecificOutput"]["updatedInput"]["subagent_type"]
        row = self.rows()[0]
        self.assertEqual(row["point"], "tier-agent-spawns")
        self.assertEqual(row["deterministic_answer"], routed)
        self.assertEqual(row["input"], "x")

    def test_a_refused_re_spawn_is_recorded_with_the_fingerprint_it_matched(self):
        script = (
            "import json, os, sys\n"
            "sys.path.insert(0, %r)\n"
            "from harness_core import lifecycle\n"
            "brief = 'review the parser for injection, then report'\n"
            "lifecycle.remember_denial('s-1', 'reviewer', brief)\n"
            "print(json.dumps(bool(lifecycle.evasion_deny('claude-code', 's-1', brief))))\n"
        ) % str(REPO / "lib")
        out = subprocess.run([sys.executable, "-c", script], env=self.env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "true")
        row = self.rows()[0]
        self.assertEqual((row["point"], row["deterministic_answer"]), ("evasion-deny", "deny"))
        self.assertEqual(row["session_id"], "s-1")
        self.assertIn("injection", row["input"])

    def test_a_spawn_nothing_routes_is_not_a_decision(self):
        self.assertIsNone(self.spawn("tier-agent-spawns.py",
                                     {"prompt": "x", "subagent_type": "reviewer"}))
        self.assertEqual(self.rows(), [])


class SubagentBudgetTests(Base):
    def test_a_subagent_row_carries_the_soft_budget_of_the_role_it_ran_as(self):
        row = {"agent_type": "worker-b"}
        fields = usage_log.budget_fields("worker-b")
        self.assertEqual(sorted(fields), ["budget_output_tokens", "budget_tool_calls"])
        row.update(fields)
        for key, value in fields.items():
            self.assertTrue(value is None or isinstance(value, int), key)
        # The shipped cost variant prices the bands, so the field is a number and not a null.
        self.assertIsInstance(row["budget_output_tokens"], int)

    def test_an_unpriced_role_records_null_rather_than_zero(self):
        fields = usage_log.budget_fields("not-a-role-anyone-prices")
        self.assertEqual(fields, {"budget_output_tokens": None, "budget_tool_calls": None})
        self.assertEqual(usage_log.budget_fields(""),
                         {"budget_output_tokens": None, "budget_tool_calls": None})


class PointNameTests(Base):
    def test_every_declared_point_has_a_writer(self):
        """A point nobody writes is a group the report would list forever and never fill."""
        sources = [path.read_text(encoding="utf-8")
                   for path in sorted((REPO / "policy" / "hooks").glob("*.py"))
                   if path.name != "decisions.py"]
        sources.append((REPO / "lib" / "harness_core" / "lifecycle.py").read_text(encoding="utf-8"))
        for point in decisions.POINTS:
            self.assertTrue(any('"' + point + '"' in text for text in sources), point)


if __name__ == "__main__":
    unittest.main()
