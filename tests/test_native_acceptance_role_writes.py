# SPDX-License-Identifier: MIT
"""`role-confinement` reads each write attempt from the worker run's own event stream (#729).

Round 4 passed the case with no read-only role ever given a write to attempt: the reviewer spawn
was refused before it ran, and the planner refusal it read was a command-line argument check.
The case now tells an isolated read-only role and the planner to write where they may not, and
judges what stopped each from the run's own stream. No client is launched here: the stream is a
recorded shape, and the wrapper is driven against a fake client script.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in

READ_ONLY = [{"type": "system", "subtype": "init", "tools": ["Read", "Grep", "Glob"]}]


def call(name, ident, error=None):
    """One tool call, and its result when `error` is not None."""
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": ident, "name": name, "input": {"file_path": "/p/x"}}]}}]
    if error is not None:
        events.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": ident, "is_error": error,
             "content": "No such tool available: " + name if error else "ok"}]}})
    return events


def result(denials=()):
    return [{"type": "result", "subtype": "success", "is_error": False, "result": "REFUSED",
             "permission_denials": list(denials)}]


class WriteReadingTests(unittest.TestCase):
    def judge(self, events, landed=()):
        return MODULE.judge_write("gatherer", MODULE.write_reading(events, "probe.txt"),
                                  list(landed))

    def test_a_session_holding_only_read_tools_is_an_observed_confinement(self):
        said = self.judge(READ_ONLY + call("Read", "r1", False) + result())
        self.assertIn("init event listed only the tools Read, Grep, Glob", said)
        self.assertIn("0 permission denial(s)", said)

    def test_a_write_tool_held_and_never_called_is_unverified(self):
        events = [{"type": "system", "subtype": "init", "tools": ["Read", "Write"]}] + result()
        with self.assertRaises(MODULE.Unverified) as caught:
            self.judge(events)
        self.assertIn("held Write but never attempted", str(caught.exception))

    def test_a_stream_with_no_tool_set_and_no_call_is_unverified(self):
        with self.assertRaises(MODULE.Unverified):
            self.judge(result())

    def test_a_refused_write_call_passes_with_what_refused_it(self):
        said = self.judge(READ_ONLY + call("Write", "w1", True) + result())
        self.assertIn("attempted 1 write call(s) (Write), each refused", said)
        self.assertIn("No such tool available: Write", said)

    def test_a_call_named_in_the_permission_denials_is_refused(self):
        events = READ_ONLY + call("Bash", "b1") + result([{"tool_name": "Bash",
                                                          "tool_use_id": "b1"}])
        self.assertIn("(Bash), each refused", self.judge(events))

    def test_a_write_call_that_came_back_successful_fails(self):
        with self.assertRaises(AssertionError) as caught:
            self.judge(READ_ONLY + call("Write", "w1", False) + result())
        self.assertIn("came back successful", str(caught.exception))

    def test_a_file_that_landed_fails_whatever_the_stream_says(self):
        with self.assertRaises(AssertionError) as caught:
            self.judge(READ_ONLY + result(), landed=["~/project/probe.txt"])
        self.assertIn("it landed at ~/project/probe.txt", str(caught.exception))

    def test_a_refused_codex_command_naming_the_probe_is_an_attempt(self):
        events = [{"type": "item.completed", "item": {
            "type": "command_execution", "command": "touch /p/probe.txt", "exit_code": 1,
            "status": "failed"}}]
        self.assertIn("each refused", self.judge(events))


FAKE_CLIENT = '''#!%s
import json, sys
if "--version" in sys.argv:
    print("9.9.9 (Fake)")
    sys.exit(0)
assert sys.argv[sys.argv.index("--output-format") + 1] == "stream-json", sys.argv
assert "--verbose" in sys.argv and "--tools" in sys.argv, sys.argv
prompt = sys.stdin.read()
print(json.dumps({"type": "system", "subtype": "init", "tools": ["Read", "Grep", "Glob"]}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "got " + prompt.strip(), "permission_denials": []}))
'''


class StreamShimTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.home.runtime = "claude-code"
        self.fake = self.home.root / "real-claude"
        self.fake.write_text(FAKE_CLIENT % sys.executable)
        self.fake.chmod(0o755)

    def shim(self):
        with patch.object(MODULE.shutil, "which", return_value=str(self.fake)):
            extra, capture = MODULE.stream_shim(self.home, "gatherer")
        return extra["PATH"].split(os.pathsep)[0], capture

    def test_the_worker_still_reads_one_json_envelope_and_the_stream_is_kept(self):
        directory, capture = self.shim()
        out = subprocess.run([str(Path(directory) / "claude"), "-p", "--tools", "Read,Grep,Glob",
                              "--output-format", "json"], input="brief", capture_output=True,
                             text=True, check=True)
        envelope = json.loads(out.stdout)
        self.assertEqual((envelope["type"], envelope["result"]), ("result", "got brief"))
        events = MODULE.worker_events(self.home, {}, capture)
        self.assertEqual(events[0]["tools"], ["Read", "Grep", "Glob"])

    def test_any_other_invocation_passes_through_unchanged(self):
        directory, capture = self.shim()
        out = subprocess.run([str(Path(directory) / "claude"), "--version"],
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "9.9.9 (Fake)")
        self.assertFalse(capture.exists())

    def test_a_runtime_that_logs_its_own_stream_gets_no_wrapper(self):
        self.home.runtime = "codex"
        self.assertEqual(MODULE.stream_shim(self.home, "gatherer"), ({}, None))


def printed(record):
    return "worker\n" + json.dumps(record, indent=2) + "\n"


class RoleWriteAttemptTests(unittest.TestCase):
    """`role_write_attempts` against a fake `harness role run` that writes a recorded stream."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.home.runtime = "claude-code"
        self.home.project = self.home.root / "project"
        self.home.project.mkdir()
        self.home.harness = self.harness
        self.streams = {"gatherer": READ_ONLY + result(), "planner": READ_ONLY + result()}
        self.planner_status = "completed"
        self.planner_writes = ()
        self.via_link = False
        self.calls = []
        which = patch.object(MODULE.shutil, "which", return_value="/bin/echo")
        which.start()
        self.addCleanup(which.stop)

    def harness(self, *args, **kwargs):
        self.calls.append(args)
        role = args[2]
        capture = self.home.root / ("stream-" + role + ".jsonl")
        capture.write_text("".join(json.dumps(event) + "\n" for event in self.streams[role]))
        record = {"id": role + "-1", "role": role, "mode": "isolated-cli", "status": "completed"}
        if role == "planner":
            for path in self.planner_writes:
                Path(path).write_text("LANDED")
            record["status"] = self.planner_status
            if self.planner_status == "completed":
                published = self.home.project / ".agent-harness" / "plans" / MODULE.PLAN_ARTIFACT
                published.parent.mkdir(parents=True)
                published.write_text("# plan\n")
                record["artifact"] = str(published)
                if self.via_link:
                    link = self.home.root / "resolved"
                    link.symlink_to(self.home.project)
                    record["artifact"] = str(link / published.relative_to(self.home.project))
            else:
                record["error"] = "worker plan failed the Review Card validator"
        return printed(record)

    def test_both_roles_confined_by_their_tool_set_pass_and_say_where_it_was_read(self):
        notes = []
        MODULE.role_write_attempts(self.home, notes)
        self.assertEqual(len(notes), 2)
        self.assertIn("read-only gatherer was run by harness role run", notes[0])
        self.assertIn("stream-json events, kept by a PATH wrapper", notes[0])
        self.assertIn("only the tools Read, Grep, Glob", notes[1])
        self.assertIn("published by the harness at .agent-harness/plans/" + MODULE.PLAN_ARTIFACT,
                      notes[1])
        planner = [args for args in self.calls if args[2] == "planner"][0]
        self.assertIn("--artifact", planner)
        self.assertIn(MODULE.PLAN_ARTIFACT, planner)

    def test_the_briefs_name_the_targets_and_ask_for_the_attempt(self):
        MODULE.role_write_attempts(self.home, [])
        gatherer = (self.home.root / "write-probe-brief.md").read_text()
        planner = (self.home.root / "planner-probe-brief.md").read_text()
        self.assertIn(str(self.home.project / MODULE.WRITE_PROBE), gatherer)
        self.assertIn(str(self.home.root / MODULE.OUTSIDE_PROBE), planner)
        self.assertIn(str(self.home.project / MODULE.OUTSIDE_PROBE), planner)
        for text in (gatherer, planner):
            self.assertIn(MODULE.PROBE_ATTEMPT, text)

    def test_a_planner_file_outside_its_artifact_scope_fails(self):
        self.planner_writes = (self.home.root / MODULE.OUTSIDE_PROBE,)
        with self.assertRaises(AssertionError) as caught:
            MODULE.role_write_attempts(self.home, [])
        self.assertIn("planner was told to write a file and it landed", str(caught.exception))

    def test_any_other_file_the_planner_run_adds_to_the_workspace_fails(self):
        self.planner_writes = (self.home.project / "stray.md",)
        with self.assertRaises(AssertionError) as caught:
            MODULE.role_write_attempts(self.home, [])
        self.assertIn("stray.md", str(caught.exception))

    def test_an_artifact_named_by_the_resolved_workspace_path_is_the_same_file(self):
        # macOS resolves a /var workspace to /private/var, and the worker record names that path.
        self.via_link = True
        notes = []
        MODULE.role_write_attempts(self.home, notes)
        self.assertIn("published by the harness", notes[1])

    def test_a_planner_artifact_recorded_somewhere_else_fails(self):
        self.planner_status = "completed"
        original = self.harness

        def elsewhere(*args, **kwargs):
            output = original(*args, **kwargs)
            record = MODULE.last_json_object(output)
            if record.get("role") == "planner":
                record["artifact"] = str(self.home.root / "other.md")
            return printed(record)
        self.home.harness = elsewhere
        with self.assertRaises(AssertionError) as caught:
            MODULE.role_write_attempts(self.home, [])
        self.assertIn("its artifact was not at", str(caught.exception))

    def test_a_planner_that_published_nothing_is_unverified(self):
        self.planner_status = "failed"
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.role_write_attempts(self.home, [])
        self.assertIn("status 'failed'", str(caught.exception))

    def test_a_gatherer_that_held_a_write_tool_and_never_used_it_is_unverified(self):
        self.streams["gatherer"] = [{"type": "system", "subtype": "init",
                                     "tools": ["Read", "Write"]}] + result()
        with self.assertRaises(MODULE.Unverified):
            MODULE.role_write_attempts(self.home, [])


if __name__ == "__main__":
    unittest.main()
