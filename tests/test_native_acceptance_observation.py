# SPDX-License-Identifier: MIT
"""Three case drivers observe what the client did rather than guessing at it (#716).

The 0.13.0 round-2 qualification left three cases unverified although nothing in them misbehaved:
`role-confinement` matched the text `status: completed` against a JSON worker record,
`bidirectional-handoff` required the reading model to name the writing runtime unprompted, and
`spawn-confinement` could not tell a refused spawn from one the model never attempted. No client
is launched here; the worker record, the task record and the decision log are each written by the
real code path that writes them in a round.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO  # noqa: F401  (puts lib/ on the path)
from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in
from harness_core import lifecycle

SESSION = "00000000-0000-4000-8000-0000000000b1"
ORDINARY = "00000000-0000-4000-8000-0000000000b2"


def worker_output(result_path, status="completed", mode="isolated-cli"):
    """What `harness role run` prints: its worker record as `cmd_role` dumps it, indent and all."""
    record = {"id": "gatherer-1", "role": "gatherer", "mode": mode, "status": status,
              "usage": {"output_tokens": 12, "tool_calls": 1},
              "context": {"posture": {"cost": "balanced"}}}
    if status == "completed":
        record["result_path"] = str(result_path)
    else:
        record["error"] = "native worker exited with status 1; inspect its private logs"
    return json.dumps(record, indent=2) + "\n"


class LastJsonObjectTests(unittest.TestCase):
    def test_the_worker_record_is_decoded_not_matched_as_text(self):
        text = worker_output("/x/result.md")
        self.assertNotIn("status: completed", text)
        record = MODULE.last_json_object("launching worker\n" + text + "done\n")
        self.assertEqual((record["mode"], record["status"]), ("isolated-cli", "completed"))

    def test_the_last_top_level_object_wins_over_one_nested_in_it(self):
        text = '{"status": "starting"}\nnoise {not json}\n{"status": "completed", "usage": {"a": 1}}'
        self.assertEqual(MODULE.last_json_object(text)["status"], "completed")

    def test_text_with_no_object_is_none(self):
        self.assertIsNone(MODULE.last_json_object("role worker: no such role [1, 2]"))


class RoleConfinementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.home.project = self.home.root / "project"
        self.home.project.mkdir()
        self.result = self.home.root / "result.md"
        self.result.write_text(MODULE.GATHER_LINE + "\n")
        self.gathered = worker_output(self.result)
        self.code = 0
        self.home.seed = lambda *args, **kwargs: None
        self.home.session = lambda prompt, **kwargs: {"session_id": SESSION, "result": ""}
        self.home.orchestrator_text = lambda session_id: MODULE.CONFINEMENT_DENY
        self.home.subagents = lambda session_id: []
        self.home.harness = self.harness

    def harness(self, *args, **kwargs):
        if args[:3] == ("role", "run", "gatherer"):
            self.home.last_code = self.code
            return self.gathered
        if args[:3] == ("role", "run", "planner"):
            self.home.last_code = 1
            return "role worker: " + MODULE.ARTIFACT_REFUSAL + "\n"
        return ""

    def test_a_completed_isolated_worker_record_passes(self):
        # The write probes after this read are driven in test_native_acceptance_role_writes.py.
        with patch.object(MODULE, "role_write_attempts"):
            verdict = MODULE.case_role_confinement(self.home)
        self.assertIn("mode isolated-cli and status completed", verdict)
        self.assertIn("held the workspace line", verdict)

    def test_a_worker_that_did_not_complete_is_unverified_with_its_status(self):
        self.gathered, self.code = worker_output(self.result, status="failed"), 1
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_role_confinement(self.home)
        self.assertIn("status 'failed'", str(caught.exception))

    def test_a_worker_in_another_mode_fails(self):
        self.gathered = worker_output(self.result, mode="native-subagent")
        with self.assertRaises(AssertionError) as caught:
            MODULE.case_role_confinement(self.home)
        self.assertIn("mode 'native-subagent'", str(caught.exception))

    def test_the_line_is_read_from_the_result_path_not_the_printed_record(self):
        self.result.write_text("something else\n")
        with self.assertRaises(AssertionError) as caught:
            MODULE.case_role_confinement(self.home)
        self.assertIn("did not return the workspace line", str(caught.exception))

    def test_no_record_at_all_is_unverified(self):
        self.gathered, self.code = "role worker: the client is not signed in\n", 1
        with self.assertRaises(MODULE.Unverified):
            MODULE.case_role_confinement(self.home)


class HandoffReturnLegTests(unittest.TestCase):
    """The task record is saved by the real `harness task save`; only the model is stubbed."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.home.project = self.home.root / "project"
        self.home.project.mkdir()
        real = self.home.harness
        self.home.harness = lambda *args, **kwargs: "" if args[:1] == ("sync",) else real(*args, **kwargs)
        self.prompts = []
        self.back = "OBJECTIVE=%s RUNTIME=codex" % MODULE.TASK_OBJECTIVE
        self.home.session = self.session

    def session(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if prompt == MODULE.HANDOFF_PROMPT:
            return {"session_id": SESSION,
                    "result": "OBJECTIVE=%s STATUS=unverified" % MODULE.TASK_OBJECTIVE}
        return {"session_id": ORDINARY, "result": self.back}

    def test_the_record_names_the_writer_and_the_reader_is_asked_for_it(self):
        verdict = MODULE.case_bidirectional_handoff(self.home)
        self.assertEqual(self.prompts[-1], MODULE.RETURN_PROMPT)
        self.assertIn("RUNTIME=", MODULE.RETURN_PROMPT)
        self.assertIn("whose record names codex as its writing runtime", verdict)
        self.assertIn("named codex as the writing runtime when asked", verdict)

    def test_a_reader_that_does_not_name_the_runtime_no_longer_leaves_the_leg_unobserved(self):
        self.back = "OBJECTIVE=%s" % MODULE.TASK_OBJECTIVE
        verdict = MODULE.case_bidirectional_handoff(self.home)
        self.assertIn("whose record names codex as its writing runtime", verdict)
        self.assertIn("it did not name codex", verdict)

    def test_a_reader_that_did_not_read_the_record_is_unverified(self):
        self.back = "I could not find a task file."
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_bidirectional_handoff(self.home)
        self.assertIn("did not report its objective", str(caught.exception))

    def test_a_record_naming_the_wrong_writer_fails(self):
        with patch.object(MODULE, "task_runtime", return_value="claude-code"):
            with self.assertRaises(AssertionError) as caught:
                MODULE.case_bidirectional_handoff(self.home)
        self.assertIn("names 'claude-code' as its writing runtime", str(caught.exception))


class SpawnAttemptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.home.project = self.home.root / "project"
        self.home.project.mkdir()
        self.home.seed = lambda *args, **kwargs: None
        self.home.harness = lambda *args, **kwargs: ""
        self.sessions = iter((SESSION, ORDINARY))
        self.home.session = lambda prompt, **kwargs: {"session_id": next(self.sessions),
                                                      "result": "Done."}
        self.home.subagents = lambda session_id: ([({"agentType": "worker-a"}, [])]
                                                  if session_id == ORDINARY else [])
        _, self.spawn = MODULE.descriptor_spawn()

    def transcript(self, session_id, *records):
        path = self.home.client_dir / "projects" / "-tmp-project" / (session_id + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(record) + "\n" for record in records))

    def spawn_call(self, result=None, is_error=False):
        records = [{"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "Agent",
             "input": {"prompt": " ".join(self.spawn["phrases"])}}]}}]
        if result is not None:
            records.append({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "is_error": is_error,
                 "content": [{"type": "text", "text": result}]}]}})
        return records

    def test_a_transcript_with_no_agent_call_says_the_model_never_attempted_it(self):
        self.transcript(SESSION, {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "I will not launch a review."}]}})
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("the model never attempted the spawn", str(caught.exception))

    def test_an_attempted_spawn_that_came_back_clean_fails(self):
        self.transcript(SESSION, *self.spawn_call("DONE"))
        with self.assertRaises(AssertionError) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("attempted 1 time(s) and allowed", str(caught.exception))

    def test_an_attempt_refused_by_something_else_is_unverified_and_names_it(self):
        self.transcript(SESSION, *self.spawn_call("Permission to use Agent was denied.", True))
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("what refused it was not the confinement", str(caught.exception))
        self.assertIn("Permission to use Agent was denied", str(caught.exception))

    def test_agent_calls_pairs_each_call_with_its_result(self):
        self.transcript(SESSION, *self.spawn_call("refused", True))
        calls, readable = MODULE.agent_calls(self.home, SESSION)
        self.assertTrue(readable)
        self.assertEqual([(c["id"], c["result"], c["is_error"]) for c in calls],
                         [("toolu_1", "refused", True)])
        self.assertEqual(MODULE.agent_calls(self.home, ORDINARY), ([], False))

    def test_an_ordinary_spawn_the_model_never_attempted_is_not_read_as_refuse_everything(self):
        self.transcript(SESSION, *self.spawn_call(MODULE.CONFINEMENT_DENY + " "
                                                  + MODULE.FRAMEWORK_ORIGIN + " "
                                                  + MODULE.FRAMEWORK_ROOTS, True))
        self.transcript(ORDINARY, {"type": "assistant", "message": {"role": "assistant",
                                                                    "content": []}})
        self.home.subagents = lambda session_id: []
        self.home.orchestrator_text = lambda session_id: (
            self.home.transcript_path(session_id).read_text())
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("never attempted the ordinary spawn", str(caught.exception))


class LiveHookLogPathTests(unittest.TestCase):
    """The registered hook command, run as the client runs it, logs where the case reads.

    The client launches the command in `registration` with the environment the runner gave it,
    which is `Home.env()`. The runner's own `HARNESS_HOME` and `XDG_STATE_HOME` are set to a
    different directory here, so a hook that took its state path from either would miss.
    """

    def test_the_refusal_lands_in_the_log_logged_refusals_reads(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as elsewhere:
            home = home_in(root)
            home.project = home.root / "project"
            home.project.mkdir()
            home.seed()
            _, spawn = MODULE.descriptor_spawn()
            command = lifecycle.registration(REPO, "claude-code")["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
                       "session_id": SESSION, "cwd": str(home.project),
                       "tool_input": {"prompt": " ".join(spawn["phrases"])}}
            with patch.dict(os.environ, {"HARNESS_HOME": elsewhere, "XDG_STATE_HOME": elsewhere}):
                env = home.env()
            self.assertNotIn("HARNESS_HOME", env)
            done = subprocess.run(command, shell=True, input=json.dumps(payload), env=env,
                                  cwd=str(home.project), capture_output=True, text=True,
                                  check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            answer = json.loads(done.stdout)
            self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn(MODULE.CONFINEMENT_DENY,
                          answer["hookSpecificOutput"]["permissionDecisionReason"])
            rows = MODULE.logged_refusals(home, SESSION)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["runtime"], "claude-code")
            self.assertEqual(list(Path(elsewhere).rglob("decisions.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
