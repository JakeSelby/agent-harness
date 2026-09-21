# SPDX-License-Identifier: MIT
"""Codex rollout rows: classification, tokens and migration. Run: python3 -m unittest discover tests

The fixtures in `fixtures/codex/` were cut from real rollouts under `~/.codex` on 2026-09-21 by
a throwaway reader that kept the record types, the field names, the model, the effort and the
token figures and replaced every id, path, nickname and body of text. `subagent-depth-2.jsonl`
is the one exception: no depth-2 thread existed in that corpus, so it is a recorded depth-1
rollout whose `thread_spawn` names depth 2 and another subagent as its parent.
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"


def _load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


usage_log = _load("usage_log_codex", REPO / "claude" / "hooks" / "usage-log.py")

SESSION = "00000000-0000-7000-8000-000000000001"
AGENT1 = "00000000-0000-7000-8000-000000000002"
AGENT2 = "00000000-0000-7000-8000-000000000003"
DESKTOP = "00000000-0000-7000-8000-000000000004"


class CodexRowTests(unittest.TestCase):
    def scan(self, name):
        return usage_log.scan(FIXTURES / name)

    def test_a_top_level_rollout_is_a_session(self):
        row = self.scan("session-vscode.jsonl")
        self.assertEqual(row["kind"], "session")
        self.assertEqual(row["runtime"], "codex")
        self.assertEqual(row["session_id"], SESSION)
        self.assertEqual(row["repo"], "example-repo")
        self.assertEqual(row["models"], ["gpt-6-astra"])
        self.assertEqual(row["turns"], 2)
        # `input_tokens` is reported inclusive of the cached part, so the row's input is net.
        self.assertEqual(row["input"], 413036423 - 405204992)
        self.assertEqual(row["output"], 1140106)
        self.assertEqual(row["cache_read"], 405204992)
        self.assertEqual(row["total"], 414176529)
        self.assertNotIn("partial", row)

    def test_a_total_only_rollout_is_partial_and_not_a_zero(self):
        row = self.scan("session-desktop-total-only.jsonl")
        self.assertEqual(row["kind"], "session")
        self.assertTrue(row["partial"])
        self.assertEqual(row["total"], 249567)
        for field in ("input", "output", "cache_read", "cache_write"):
            self.assertIsNone(row[field], field)

    def test_a_spawned_thread_is_a_subagent_row_joined_to_its_parent(self):
        row = self.scan("subagent-depth-1.jsonl")
        self.assertEqual(row["kind"], "subagent")
        self.assertEqual(row["runtime"], "codex")
        self.assertEqual(row["session_id"], SESSION)
        self.assertEqual(row["agent_id"], AGENT1)
        self.assertEqual(row["agent_type"], "Fixture-One")
        self.assertEqual(row["spawn_depth"], 1)
        self.assertEqual(row["model"], "gpt-6-astra")
        self.assertEqual(row["effort"], "high")
        self.assertEqual(row["tool_calls"], 3)
        self.assertEqual(row["output"], 9490)
        self.assertNotIn("stances", row)

    def test_a_depth_two_thread_joins_to_the_thread_that_spawned_it(self):
        row = self.scan("subagent-depth-2.jsonl")
        self.assertEqual(row["kind"], "subagent")
        self.assertEqual(row["agent_id"], AGENT2)
        self.assertEqual(row["session_id"], AGENT1)
        self.assertEqual(row["spawn_depth"], 2)

    def test_an_inherited_parent_session_meta_does_not_reclassify_the_child(self):
        """The second `session_meta` in the depth-2 fixture is the parent's, as Codex writes it."""
        lines = (FIXTURES / "subagent-depth-2.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(lines[-1])["payload"]["id"], SESSION)
        self.assertEqual(self.scan("subagent-depth-2.jsonl")["agent_id"], AGENT2)

    def test_a_thread_source_subagent_with_no_source_object_still_joins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(json.dumps({"type": "session_meta", "payload": {
                "id": AGENT1, "session_id": SESSION, "parent_thread_id": SESSION,
                "thread_source": "subagent", "agent_nickname": "Fixture-One"}}) + "\n"
                + json.dumps({"type": "turn_context", "payload": {"model": "m"}}) + "\n",
                encoding="utf-8")
            row = usage_log.scan(path)
            self.assertEqual((row["kind"], row["session_id"]), ("subagent", SESSION))
            self.assertIsNone(row["spawn_depth"])


class CodexRescanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        os.environ.pop("CODEX_HOME", None)
        self.ledger = self.home / ".local/state/agent-harness/usage.jsonl"

    def tearDown(self):
        if self._old is not None:
            os.environ["HOME"] = self._old
        self.tmp.cleanup()

    def place(self, folder, *names):
        target = self.home / ".codex" / folder / "2026" / "09" / "18"
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copy(FIXTURES / name, target / ("rollout-" + name))

    def rows(self):
        return [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]

    def test_rescan_reads_archived_rollouts_and_counts_the_children(self):
        self.place("sessions", "session-vscode.jsonl")
        self.place("archived_sessions", "subagent-depth-1.jsonl", "subagent-depth-2.jsonl")
        self.assertEqual(usage_log.rescan(30), 3)
        rows = {row["agent_id"] if row["kind"] == "subagent" else row["session_id"]: row
                for row in self.rows()}
        self.assertEqual(sorted(rows), sorted([SESSION, AGENT1, AGENT2]))
        self.assertEqual(rows[SESSION]["subagents"], 1)
        self.assertEqual(rows[AGENT1]["kind"], "subagent")

    def test_rescan_replaces_a_thread_recorded_as_a_session_and_backs_up_first(self):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        stale = {"kind": "session", "runtime": "codex", "session_id": AGENT1,
                 "ended": "2026-09-18T16:00:00Z", "input": 1, "output": 2}
        self.ledger.write_text(json.dumps(stale) + "\n", encoding="utf-8")
        self.place("sessions", "subagent-depth-1.jsonl")
        usage_log.rescan(30)
        rows = self.rows()
        self.assertEqual([row["kind"] for row in rows], ["subagent"])
        self.assertEqual(rows[0]["agent_id"], AGENT1)
        self.assertEqual(json.loads(self.ledger.with_name("usage.jsonl.bak").read_text()), stale)

    def test_rescan_keeps_a_row_it_did_not_reclassify(self):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        other = {"kind": "session", "runtime": "claude-code", "session_id": "keep-me"}
        self.ledger.write_text(json.dumps(other) + "\n", encoding="utf-8")
        self.place("sessions", "subagent-depth-1.jsonl")
        usage_log.rescan(30)
        self.assertIn(other, self.rows())

    def test_rescan_honours_codex_home(self):
        elsewhere = self.home / "alt-codex"
        os.environ["CODEX_HOME"] = str(elsewhere)
        try:
            target = elsewhere / "archived_sessions"
            target.mkdir(parents=True)
            shutil.copy(FIXTURES / "session-vscode.jsonl", target / "rollout.jsonl")
            self.assertEqual(usage_log.rescan(30), 1)
        finally:
            os.environ.pop("CODEX_HOME", None)

    def test_rescan_skips_a_rollout_older_than_the_window(self):
        self.place("sessions", "session-vscode.jsonl")
        stale = time.time() - 40 * 86400
        for path in (self.home / ".codex").rglob("*.jsonl"):
            os.utime(path, (stale, stale))
        self.assertEqual(usage_log.rescan(7), 0)


class CodexReportTests(unittest.TestCase):
    """`harness usage` reads the rows; the runtimes disagree about what a parent's tokens mean."""

    def setUp(self):
        self.harness = _load("harness_codex", REPO / "bin" / "harness")

    def report(self, rows, by="day"):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            old = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            os.environ.pop("HARNESS_QUIET", None)
            ledger = home / ".local/state/agent-harness/usage.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            args = self.harness.argparse.Namespace(days=30, by=by, rules=False, rescan=False)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(self.harness.cmd_usage(args), 0)
            finally:
                if old is not None:
                    os.environ["HOME"] = old
            return buf.getvalue()

    def rows(self):
        ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return [
            {"kind": "session", "runtime": "codex", "session_id": SESSION, "ended": ended,
             "models": ["gpt-6-astra"], "input": 10, "output": 100,
             "cache_read": 0, "cache_write": 0},
            {"kind": "subagent", "runtime": "codex", "session_id": SESSION, "agent_id": AGENT1,
             "agent_type": "Fixture-One", "ended": ended, "model": "gpt-6-astra",
             "input": 5, "output": 50, "cache_read": 0, "cache_write": 0, "tool_calls": 3},
            {"kind": "subagent", "runtime": "claude-code", "session_id": "cc-1",
             "agent_id": "cc-a", "agent_type": "builder", "ended": ended, "model": "model-a",
             "input": 7, "output": 70, "cache_read": 0, "cache_write": 0, "tool_calls": 1},
            {"kind": "session", "runtime": "claude-code", "session_id": "cc-1", "ended": ended,
             "models": ["model-a"], "input": 7, "output": 70, "cache_read": 0, "cache_write": 0},
        ]

    def test_a_codex_subagent_is_summed_and_a_claude_code_one_is_not(self):
        out = self.report(self.rows())
        # 100 + 50 from Codex, 70 from Claude Code counted once through its session row.
        self.assertIn("220", out.replace(",", ""))
        self.assertIn("TOTAL", out)

    def test_by_model_reads_a_subagent_row_that_names_one_model(self):
        out = self.report(self.rows(), by="model")
        self.assertIn("gpt-6-astra", out)
        self.assertNotIn("(unknown)", out)

    def test_by_role_names_the_codex_thread(self):
        self.assertIn("Fixture-One", self.report(self.rows(), by="role"))


if __name__ == "__main__":
    unittest.main()
