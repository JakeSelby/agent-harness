# SPDX-License-Identifier: MIT
"""`spawn-confinement` sees a refusal in the harness decision log, not only in the client's answer.

A headless client need not repeat a PreToolUse deny's reason in its result, so a refusal the
harness made could read as unobserved. The decision log each test reads here is written by the
real hook path, `lifecycle.dispatch`, with the disposable home as `HOME`, so the row is the shape
the hook writes rather than a hand-typed copy of it. No client is launched.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO  # noqa: F401  (puts lib/ on the path)
from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in
from harness_core import lifecycle

REFUSED = "00000000-0000-4000-8000-0000000000a1"
ORDINARY = "00000000-0000-4000-8000-0000000000a2"
OTHER = "00000000-0000-4000-8000-0000000000a3"


class SpawnRefusalObservationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = home_in(temp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": temp.name, "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()
        # The writer reads its config once per process; another test may have read a different one.
        log = lifecycle.decisions()
        self.assertIsNotNone(log)
        log._CONFIG.clear()
        self.addCleanup(log._CONFIG.clear)
        self.log = Path(temp.name) / ".local" / "state" / "agent-harness" / "decisions.jsonl"
        _, self.spawn = MODULE.descriptor_spawn()
        self.reported = {REFUSED: "Done.", ORDINARY: "Spawned it."}
        self.home.seed = lambda *args, **kwargs: None
        self.home.harness = lambda *args, **kwargs: ""
        self.home.session = self.session
        self.sessions = iter((REFUSED, ORDINARY))
        self.home.orchestrator_text = lambda session_id: ""
        self.home.subagents = lambda session_id: ([({"agentType": "general-purpose"}, [])]
                                                  if session_id == ORDINARY else [])

    def session(self, prompt, **kwargs):
        session_id = next(self.sessions)
        return {"session_id": session_id, "result": self.reported[session_id]}

    def hook_refuses(self, session_id):
        """The spawn the model would issue, through the real PreToolUse path, which logs it."""
        prompt = " ".join(self.spawn["phrases"])
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": session_id,
                   "tool_input": {"prompt": prompt}}
        result = lifecycle.dispatch("claude-code", payload)
        self.assertEqual(result.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")
        self.assertTrue(self.log.exists())

    def test_a_refusal_in_the_log_alone_is_observed(self):
        self.hook_refuses(REFUSED)
        self.assertNotIn(MODULE.CONFINEMENT_DENY, self.reported[REFUSED])
        verdict = MODULE.case_spawn_confinement(self.home)
        self.assertIn("decision log recorded 1 framework-spawn deny row(s)", verdict)
        self.assertIn("its wording was not observed in this run", verdict)

    def test_neither_source_is_still_unverified_even_with_another_sessions_row(self):
        # Proves the session filter bites: a deny logged for some other session is not this one.
        self.hook_refuses(OTHER)
        self.assertEqual(MODULE.logged_refusals(self.home, REFUSED), [])
        with self.assertRaises(MODULE.Unverified) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("classification itself was not observed", str(caught.exception))

    def test_a_refusal_the_client_reports_is_still_held_to_its_wording(self):
        self.reported[REFUSED] = MODULE.CONFINEMENT_DENY + " " + MODULE.FRAMEWORK_ORIGIN
        with self.assertRaises(AssertionError) as caught:
            MODULE.case_spawn_confinement(self.home)
        self.assertIn("the read roots that worker needs", str(caught.exception))

    def test_a_row_that_is_not_a_framework_deny_is_not_read_as_one(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text('not json\n{"kind": "decision", "point": "framework-spawn", '
                            '"deterministic_answer": "allow", "session_id": "%s"}\n' % REFUSED)
        self.assertEqual(MODULE.logged_refusals(self.home, REFUSED), [])


if __name__ == "__main__":
    unittest.main()
