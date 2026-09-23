# SPDX-License-Identifier: MIT
"""The `hook-composition` case: composition, patches, trust and denials read from turns.

The case used to prove composition from the merged settings table alone, with no turn that fired
the user's hook. It now reads what two native turns left behind: the transcript's file-tool
calls, the user-owned hook's own log, the stop gate's rows in the decision log and the deny
turn's permission denials. No test here launches a client; a fake home writes those artefacts in
the shapes the client and the hooks write them.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in

SESSION = "11111111-2222-3333-4444-555555555555"
DENY_SESSION = "66666666-7777-8888-9999-000000000000"


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def tool_use(name, file_path, ident):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": ident, "name": name, "input": {"file_path": file_path}}]}}


class FakeHome(MODULE.Home):
    """A disposable home whose sync and turns write what the real ones are observed to write.

    `patch` lists the (tool, name) calls the write turn makes; `fire` says whether the user hook
    logs them; `gate` is the stop gate's logged outcome; `denials` the deny turn's refusals.
    """

    def __init__(self, directory, patch=(("Write", "alpha.txt"), ("Write", "beta.txt")),
                 fire=True, gate="untrusted", denials=1, deny_row=True):
        base = home_in(directory)
        self.__dict__.update(base.__dict__)
        self.project = self.root / "project"
        self.project.mkdir()
        self.patch, self.fire, self.gate = patch, fire, gate
        self.denials, self.deny_row = denials, deny_row

    def harness(self, *args, **kwargs):
        path = self.client_dir / "settings.json"
        settings = json.loads(path.read_text())
        settings["hooks"]["PostToolUse"].append(
            {"hooks": [{"type": "command", "command": "python3 /x/adapters/claude-code/hook.py"}]})
        settings["permissions"] = {"defaultMode": MODULE.BYPASS_MODE}
        path.write_text(json.dumps(settings))
        return "sync complete"

    def decisions(self, rows):
        write_jsonl(self.root / ".local" / "state" / "agent-harness" / "decisions.jsonl", rows)

    def session(self, prompt, tools=("Agent",), resume=None, timeout=0):
        self.launched += 1
        transcript = self.client_dir / "projects" / "p"
        if prompt == MODULE.PATCH_PROMPT:
            records = []
            for index, (tool, name) in enumerate(self.patch):
                target = self.project / name
                records.append(tool_use(tool, str(target), "t%s" % index))
                target.write_text(name + "\n")
                if self.fire and tool in MODULE.FILE_TOOLS:
                    write_jsonl(self.root / "user-hook.log", [
                        {"session_id": SESSION, "event": "PostToolUse", "tool": tool,
                         "file": str(target)}])
            write_jsonl(transcript / (SESSION + ".jsonl"), records)
            if self.gate is not None:
                self.decisions([
                    {"kind": "decision", "decision_id": "g1", "point": "stop-gate",
                     "session_id": SESSION, "deterministic_answer": "skipped"},
                    {"kind": "outcome", "decision_id": "g1", "point": "stop-gate",
                     "session_id": SESSION, "outcome": self.gate}])
            return {"session_id": SESSION, "result": "DONE"}
        write_jsonl(transcript / (DENY_SESSION + ".jsonl"), [tool_use("Bash", "", "b1")])
        if self.deny_row:
            self.decisions([{"kind": "decision", "point": "grade-bash", "session_id": DENY_SESSION,
                             "deterministic_answer": "deny"}])
        return {"session_id": DENY_SESSION, "result": "I could not do that.",
                "permission_denials": [{"tool_name": "Bash"}] * self.denials}


class DriverTests(unittest.TestCase):

    def run_case(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            home = FakeHome(directory, **kwargs)
            try:
                return MODULE.case_hook_composition(home), home.launched
            finally:
                MODULE.shutil.rmtree(str(home.project / ".git"), ignore_errors=True)

    def test_a_composed_two_file_turn_an_untrusted_gate_and_a_hook_deny_pass(self):
        text, launched = self.run_case()
        self.assertEqual(launched, 2)
        self.assertIn("alpha.txt and beta.txt with that turn's session id", text)
        self.assertIn("2 file-tool call(s) (Write alpha.txt, Write beta.txt)", text)
        self.assertIn("logged verdict (answer/outcome) for that git workspace with a ## Gate block was "
                      "skipped/untrusted", text)
        self.assertIn("its gate ran 0 times", text)
        self.assertIn("permission_denials held 1 entry (tool Bash)", text)
        self.assertIn("its decision-log deny row for that session", text)
        self.assertIn("recorded no hasTrustDialogAccepted flag", text)
        self.assertNotIn(SESSION, text)
        self.assertNotIn("no Write turn was run", text)

    def test_a_file_tool_write_the_user_hook_never_heard_of_fails(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_case(fire=False)
        self.assertIn("user-owned PostToolUse hook logged no call", str(caught.exception))

    def test_a_turn_that_never_used_the_file_tool_is_unverified(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            self.run_case(patch=())
        self.assertIn("never attempted the write", str(caught.exception))

    def test_a_turn_that_wrote_one_file_observed_no_multi_file_patch(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            self.run_case(patch=(("Write", "alpha.txt"),))
        self.assertIn("did not write beta.txt", str(caught.exception))

    def test_a_trusted_verdict_for_an_unlisted_workspace_fails(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_case(gate="passed")
        self.assertIn("not untrusted", str(caught.exception))

    def test_a_turn_with_no_denial_is_unverified_rather_than_passed(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            self.run_case(denials=0)
        self.assertIn("declined on its own judgement", str(caught.exception))

    def test_a_denial_nothing_attributes_to_grade_bash_is_unverified(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            self.run_case(deny_row=False)
        self.assertIn("attributes one to grade-bash", str(caught.exception))


class ReaderTests(unittest.TestCase):

    def test_a_bash_write_is_not_a_file_tool_write(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.patch_verdict(MODULE.PATCH_FILES, {"alpha.txt": True, "beta.txt": True}, [],
                                 [], SESSION)
        self.assertIn("without the client's file-writing tool", str(caught.exception))

    def test_a_hook_line_from_another_session_does_not_count(self):
        calls = [{"id": "a", "tool": "Write", "file": "/p/alpha.txt"},
                 {"id": "b", "tool": "Write", "file": "/p/beta.txt"}]
        fired = [{"session_id": "other", "event": "PostToolUse", "tool": "Write",
                  "file": "/p/alpha.txt"},
                 {"session_id": SESSION, "event": "PostToolUse", "tool": "Write",
                  "file": "/p/beta.txt"}]
        with self.assertRaises(AssertionError) as caught:
            MODULE.patch_verdict(MODULE.PATCH_FILES, {"alpha.txt": True, "beta.txt": True},
                                 calls, fired, SESSION)
        self.assertIn("wrote alpha.txt", str(caught.exception))

    def test_the_gate_verdict_joins_each_decision_to_its_own_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            write_jsonl(home.root / ".local" / "state" / "agent-harness" / "decisions.jsonl", [
                {"kind": "decision", "decision_id": "x", "point": "stop-gate",
                 "session_id": "elsewhere", "deterministic_answer": "released"},
                {"kind": "outcome", "decision_id": "x", "outcome": "passed"},
                {"kind": "decision", "decision_id": "y", "point": "stop-gate",
                 "session_id": SESSION, "deterministic_answer": "skipped"},
                {"kind": "outcome", "decision_id": "y", "outcome": "untrusted"}])
            self.assertEqual(MODULE.gate_verdicts(home, SESSION), [("skipped", "untrusted")])
            self.assertEqual(MODULE.gate_verdicts(home, "nobody"), [])

    def test_the_client_trust_flag_is_read_at_either_form_of_the_project_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            home.project = home.root / "project"
            home.project.mkdir()
            self.assertIsNone(MODULE.trust_flag(home))
            home.client_dir.mkdir()
            (home.client_dir / ".claude.json").write_text(json.dumps({"projects": {
                str(home.project.resolve()): {"hasTrustDialogAccepted": False}}}))
            self.assertIs(MODULE.trust_flag(home), False)

    def test_the_user_hook_logs_the_session_tool_and_file_the_client_handed_it(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "user-hook.log"
            script = Path(directory) / "user-hook.py"
            script.write_text(MODULE.USER_HOOK % str(log))
            payload = {"session_id": SESSION, "hook_event_name": "PostToolUse",
                       "tool_name": "Write", "tool_input": {"file_path": "/p/alpha.txt"}}
            result = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(MODULE.jsonl_rows(log), [
                {"session_id": SESSION, "event": "PostToolUse", "tool": "Write",
                 "file": "/p/alpha.txt"}])

    def test_the_user_hook_is_registered_for_every_file_writing_tool(self):
        self.assertEqual(MODULE.USER_MATCHER.split("|"), list(MODULE.FILE_TOOLS))
        for name in MODULE.PATCH_FILES:
            self.assertIn(name, MODULE.PATCH_PROMPT)
        self.assertIn("Write tool", MODULE.PATCH_PROMPT)


if __name__ == "__main__":
    unittest.main()
