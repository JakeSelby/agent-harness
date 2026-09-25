# SPDX-License-Identifier: MIT
"""A role-confinement refusal is logged as a decision and is not counted as a subagent (#760).

Every confinement refusal writes one `role-confinement` decision row naming the role and what
named it, as `framework-spawn` and `evasion-deny` refusals already did, and the usage ledger's
`subagents` count leaves out an `Agent` call that was refused and never ran.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_config_dir
from test_usage import REPO, usage_log

HOOK = REPO / "claude" / "hooks" / "usage-log.py"
BRIEF = "Read notes.md and say which behaviour it describes that no test exercises."
DENY = "This constrained harness role requires an isolated worker. Use harness role run reviewer."


class ConfinementRows(unittest.TestCase):
    """The coordinator run in a subprocess over a temporary HOME, as the hook runs it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.log = self.home / ".local" / "state" / "agent-harness" / "decisions.jsonl"

    def spawn(self, prompt, role=None, delegation="tiered"):
        env = dict(without_config_dir(), HOME=str(self.home), HARNESS_HOME=str(self.home))
        for name in list(env):
            if name.startswith("HARNESS_STANCE_"):
                env.pop(name)
        env["HARNESS_STANCE_DELEGATION"] = delegation
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s-1",
                   "tool_input": {"prompt": prompt, "subagent_type": role}}
        script = ("import json, sys\nsys.path.insert(0, %r)\nfrom harness_core import lifecycle\n"
                  "print(json.dumps(lifecycle.dispatch('claude-code', json.load(sys.stdin))))\n"
                  % str(REPO / "lib"))
        out = subprocess.run([sys.executable, "-c", script], input=json.dumps(payload), env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def rows(self, point="role-confinement"):
        if not self.log.exists():
            return []
        rows = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        return [row for row in rows if row.get("point") == point]

    def test_a_spawn_named_for_a_constrained_role_writes_a_deny_row_naming_it(self):
        result = self.spawn(BRIEF, role="reviewer")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["deterministic_answer"], "deny")
        self.assertEqual(rows[0]["session_id"], "s-1")
        self.assertTrue(rows[0]["input"].startswith("reviewer (subagent_type): "), rows[0]["input"])
        self.assertIn("no test exercises", rows[0]["input"])

    def test_a_brief_declaring_its_role_writes_a_deny_row_naming_the_marker(self):
        result = self.spawn("harness-role: reviewer\n" + BRIEF, role="worker-a")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["input"].startswith("reviewer (harness-role marker): "),
                        rows[0]["input"])

    def test_a_named_refusal_is_logged_when_delegation_is_off_too(self):
        self.spawn(BRIEF, role="reviewer", delegation="off")
        self.assertEqual(len(self.rows()), 1)

    def test_a_spawn_of_an_unconstrained_role_writes_no_confinement_row(self):
        self.spawn(BRIEF, role="builder")
        self.assertEqual(self.rows(), [])


def assistant(mid, stamp, blocks):
    return {"type": "assistant", "sessionId": "s-1", "cwd": "", "timestamp": stamp,
            "message": {"id": mid, "model": "model-a", "content": blocks,
                        "usage": {"input_tokens": 1, "output_tokens": 10}}}


def spawn_call(use_id):
    return {"type": "tool_use", "id": use_id, "name": "Agent",
            "input": {"subagent_type": "reviewer", "prompt": BRIEF}}


def result(use_id, stamp, error, text):
    block = {"type": "tool_result", "tool_use_id": use_id, "content": text}
    if error:
        block["is_error"] = True
    return {"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": stamp,
            "message": {"role": "user", "content": [block]}}


class RefusedSpawnCount(unittest.TestCase):
    """The SessionEnd worker over a transcript whose spawns were refused, ran, or ran and failed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.project = self.home / ".claude" / "projects" / "a-repo"
        self.project.mkdir(parents=True)

    def session(self, entries, ran=()):
        transcript = self.project / "s-1.jsonl"
        transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        subagents = self.project / "s-1" / "subagents"
        for use_id in ran:
            subagents.mkdir(parents=True, exist_ok=True)
            (subagents / ("agent-%s.jsonl" % use_id)).write_text(json.dumps(
                assistant("sub-" + use_id, "2026-09-25T10:00:05.000Z", [])) + "\n", encoding="utf-8")
            (subagents / ("agent-%s.meta.json" % use_id)).write_text(json.dumps(
                {"agentType": "gatherer", "toolUseId": use_id}), encoding="utf-8")
        out = subprocess.run([sys.executable, str(HOOK), "--worker", str(transcript), "s-1", ""],
                             capture_output=True, text=True, timeout=60,
                             env=dict(without_config_dir(), HOME=str(self.home)))
        self.assertEqual(out.returncode, 0, out.stderr)
        state = self.home / ".local/state/agent-harness/usage.jsonl"
        rows = [json.loads(line) for line in state.read_text().splitlines()]
        return [row for row in rows if row["kind"] == "session"][0]

    def test_four_refused_spawns_count_as_no_subagents(self):
        entries = [{"type": "user", "sessionId": "s-1", "cwd": "",
                    "timestamp": "2026-09-25T10:00:00.000Z"}]
        for n in range(4):
            use_id = "tu-%d" % n
            entries.append(assistant("m%d" % n, "2026-09-25T10:00:0%d.000Z" % (n + 1),
                                     [spawn_call(use_id)]))
            entries.append(result(use_id, "2026-09-25T10:00:0%d.500Z" % (n + 1), True, DENY))
        self.assertEqual(self.session(entries)["subagents"], 0)

    def test_a_spawn_that_ran_and_failed_is_still_counted(self):
        entries = [assistant("m1", "2026-09-25T10:00:01.000Z", [spawn_call("tu-a")]),
                   result("tu-a", "2026-09-25T10:00:09.000Z", True, "interrupted"),
                   assistant("m2", "2026-09-25T10:00:10.000Z", [spawn_call("tu-b")]),
                   result("tu-b", "2026-09-25T10:00:11.000Z", True, DENY)]
        self.assertEqual(self.session(entries, ran=("tu-a",))["subagents"], 1)

    def test_a_spawn_with_no_transcript_of_its_own_and_no_error_is_still_counted(self):
        """Older Claude Code wrote a subagent into the session file; the call is the evidence."""
        entries = [assistant("m1", "2026-09-25T10:00:01.000Z", [spawn_call("tu-a")]),
                   result("tu-a", "2026-09-25T10:00:09.000Z", False, "DONE")]
        self.assertEqual(self.session(entries)["subagents"], 1)

    def test_a_spawn_that_ran_as_sidechain_lines_and_failed_is_still_counted(self):
        """Older Claude Code: the subagent's turns are sidechain lines here, and it has no file."""
        work = assistant("sub-1", "2026-09-25T10:00:05.000Z", [])
        work["isSidechain"] = True
        entries = [assistant("m1", "2026-09-25T10:00:01.000Z", [spawn_call("tu-a")]), work,
                   result("tu-a", "2026-09-25T10:00:09.000Z", True, "interrupted")]
        self.assertEqual(self.session(entries)["subagents"], 1)

    def test_the_helper_leaves_a_call_a_subagent_row_names(self):
        agents = [{"tool_use_id": "tu-a"}, {"tool_use_id": ""}]
        self.assertEqual(usage_log.refused_spawns(agents, {"tu-a", "tu-b"}), {"tu-b"})
        self.assertEqual(usage_log.refused_spawns(None, {"tu-b"}), {"tu-b"})


if __name__ == "__main__":
    unittest.main()
