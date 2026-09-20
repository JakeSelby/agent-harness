# SPDX-License-Identifier: MIT
"""One model name per subagent row.

A routed spawn's `.meta.json` carries the alias the spawn hook asked for, while a directly
spawned agent's carries the full id its transcript records, so the same model used to appear
under two names and `usage --by model` split in half. The row now names what the transcript
reports; the alias is the fallback for an agent that recorded no model at all.

Run: python3 -m unittest discover tests
"""
import json
import unittest

from test_usage import usage_log
from test_usage_roles import STAMPS, Fixture, message, write


class SubagentModelName(Fixture):
    def agent_file(self, agent_id, entries, meta=None):
        path = self.project / "s-1" / "subagents" / ("agent-%s.jsonl" % agent_id)
        write(path, entries)
        if meta is None:
            path.with_name(path.stem + ".meta.json").unlink(missing_ok=True)
        else:
            path.with_name(path.stem + ".meta.json").write_text(json.dumps(meta),
                                                                encoding="utf-8")
        return path

    def row(self, agent_id, rows=None):
        return [r for r in (rows or self.record()) if r.get("agent_id") == agent_id][0]

    def test_a_routed_spawn_records_the_model_its_transcript_ran_on(self):
        # The spawn hook asked for `alias`; the transcript says what actually answered.
        self.agent_file("aaa", [message("a1", STAMPS[3], 100, model="claude-model-5")],
                        {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"})
        self.assertEqual(self.row("aaa")["model"], "claude-model-5")

    def test_a_direct_spawn_and_a_routed_one_land_under_the_same_name(self):
        self.agent_file("aaa", [message("a1", STAMPS[3], 100, model="claude-model-5")],
                        {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"})
        self.agent_file("bbb", [message("b1", STAMPS[3], 200, model="claude-model-5")],
                        {"agentType": "reviewer", "spawnDepth": 1, "model": "claude-model-5"})
        rows = self.record()
        self.assertEqual({self.row("aaa", rows)["model"], self.row("bbb", rows)["model"]},
                         {"claude-model-5"})

    def test_the_most_frequent_model_wins_and_a_tie_goes_to_the_last(self):
        self.agent_file("aaa", [message("a1", STAMPS[3], 10, model="model-one"),
                                message("a2", STAMPS[3], 20, model="model-two"),
                                message("a3", STAMPS[3], 30, model="model-two")],
                        {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"})
        self.assertEqual(self.row("aaa")["model"], "model-two")
        self.agent_file("aaa", [message("a1", STAMPS[3], 10, model="model-one"),
                                message("a2", STAMPS[3], 20, model="model-two")],
                        {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"})
        self.assertEqual(self.row("aaa")["model"], "model-two")

    def test_a_streamed_response_does_not_make_its_model_win_a_turn_it_did_not(self):
        # One response written as three records against a response written as one: the records
        # are the votes, which is what a model that answered more of the run looks like.
        streamed = [message("a1", STAMPS[3], figure, model="model-one") for figure in (8, 90)]
        self.agent_file("aaa", streamed + [message("a2", STAMPS[3], 20, model="model-two")],
                        {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"})
        self.assertEqual(self.row("aaa")["model"], "model-one")

    def test_an_agent_that_recorded_no_model_falls_back_to_the_alias(self):
        blank = message("a1", STAMPS[3], 100)
        del blank["message"]["model"]
        self.agent_file("aaa", [blank], {"agentType": "gatherer", "spawnDepth": 1,
                                         "model": "alias"})
        self.assertEqual(self.row("aaa")["model"], "alias")

    def test_an_agent_with_neither_records_the_field_empty_rather_than_absent(self):
        blank = message("a1", STAMPS[3], 100)
        del blank["message"]["model"]
        self.agent_file("aaa", [blank], {"agentType": "gatherer", "spawnDepth": 1})
        self.assertEqual(self.row("aaa")["model"], "")

    def test_a_worker_row_keeps_the_model_the_worker_reported(self):
        # A worker is an isolated CLI session with no transcript of ours to read: its own
        # status record is the only thing that knows what it ran on, and it stays the source.
        run = self.home / ".local/state/agent-harness/workers" / ("e" * 32)
        run.mkdir(parents=True)
        (run / "status.json").write_text(json.dumps(
            {"schema_version": 1, "id": run.name, "role": "reviewer", "runtime": "codex",
             "model": "worker-model", "status": "completed", "started_at": 1, "finished_at": 2,
             "usage": {"input": 1, "output": 2}}), encoding="utf-8")
        rows = [r for r in usage_log.worker_rows(0.0) if r["session_id"] == run.name]
        self.assertEqual(rows[0]["model"], "worker-model")


class RescanNormalises(Fixture):
    def test_a_rescan_replaces_a_legacy_alias_row_rather_than_adding_one(self):
        write(self.project / "s-1" / "subagents" / "agent-aaa.jsonl",
              [message("a1", STAMPS[3], 100, model="claude-model-5")])
        (self.project / "s-1" / "subagents" / "agent-aaa.meta.json").write_text(json.dumps(
            {"agentType": "gatherer", "spawnDepth": 1, "model": "alias"}), encoding="utf-8")
        legacy = {"kind": "subagent", "runtime": "claude-code", "session_id": "s-1",
                  "agent_id": "aaa", "agent_type": "gatherer", "model": "alias",
                  "output": 100, "ended": STAMPS[3]}
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

        usage_log.rescan(30)

        rows = [r for r in self.rows() if r.get("agent_id") == "aaa"]
        self.assertEqual(len(rows), 1)                       # replaced, never duplicated
        self.assertEqual(rows[0]["model"], "claude-model-5")

    def test_a_second_rescan_changes_nothing(self):
        usage_log.rescan(30)
        first = self.rows()
        usage_log.rescan(30)
        self.assertEqual(self.rows(), first)


class ModelGrouping(Fixture):
    def test_by_model_groups_the_session_rows_and_never_a_subagents_tokens(self):
        # A subagent's tokens are already in its session's row, so the grouping reads the
        # session's `models` list; the subagent rows are what `--by role` reads instead.
        self.record()
        report = self.report(by="model")
        self.assertIn("model-a+model-b", report)
        total = [ln for ln in report.splitlines() if ln.startswith("TOTAL")][0]
        self.assertEqual(total.split()[1:4], ["1", "5", "1,200"])


if __name__ == "__main__":
    unittest.main()
