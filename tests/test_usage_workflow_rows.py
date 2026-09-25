# SPDX-License-Identifier: MIT
"""Workflow-tool agents in the usage ledger and in `harness usage --by role`.

The Workflow tool launches its agents itself, so no spawn hook routed them and no brief budgeted
them. A row for one must not read as a spawn of the role it is named for, and must not carry that
role's soft budget. The fixture ledger `fixtures/usage/workflow-and-spawned.jsonl` holds spawned
rows beside workflow rows named for a budgeted role, one of them written before rows were marked.

Run: python3 -m unittest discover tests
"""
import json
import unittest

from test_usage_roles import STAMPS, Fixture, message, write

from test_usage import REPO

LEDGER = REPO / "tests" / "fixtures" / "usage" / "workflow-and-spawned.jsonl"


class WorkflowRowsAreUnconfined(Fixture):
    """What the hook writes: a workflow row is marked and carries no role's budget."""

    def nested(self, agent_type):
        directory = self.project / "s-1" / "subagents" / "workflows" / "wf_9c1"
        write(directory / "agent-www.jsonl", [message("w1", STAMPS[4], 250, ("t9",))])
        (directory / "agent-www.meta.json").write_text(json.dumps(
            {"agentType": agent_type, "spawnDepth": 2, "model": "model-haiku"}), encoding="utf-8")

    def test_a_workflow_row_named_for_a_budgeted_role_carries_no_budget(self):
        # `gatherer` is budgeted by the default cost variant; the spawned `aaa` row proves it.
        self.nested("gatherer")
        rows = {r.get("agent_id"): r for r in self.record() if r["kind"] == "subagent"}
        self.assertIsInstance(rows["aaa"]["budget_output_tokens"], int)
        self.assertNotIn("unconfined", rows["aaa"])
        workflow = rows["www"]
        self.assertEqual((workflow["agent_type"], workflow["workflow"]), ("gatherer", "wf_9c1"))
        self.assertIs(workflow["unconfined"], True)
        self.assertIsNone(workflow["budget_output_tokens"])
        self.assertIsNone(workflow["budget_tool_calls"])


class WorkflowBucket(Fixture):
    """What the report prints over the fixture ledger."""

    def setUp(self):
        super().setUp()
        rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()]
        # The fixture's dates are fixed; the report reads a window, so each row ends now.
        for row in rows:
            row["started"], row["ended"] = STAMPS[0], STAMPS[5]
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def lines(self):
        return {ln.split()[0]: ln.split() for ln in self.report(by="role").splitlines()[2:]
                if ln.strip()}

    def test_workflow_rows_have_their_own_bucket_and_leave_the_role_alone(self):
        lines = self.lines()
        # Two spawned gatherers at 100 and 300; the two workflow rows named gatherer are not in it.
        self.assertEqual(lines["gatherer"][1:5], ["2", "100", "300", "300"])
        self.assertEqual(lines["reviewer"][1:3], ["1", "700"])
        # Three workflow rows, including the legacy one that still carries a budget.
        self.assertEqual(lines["(workflow)"][1:5], ["3", "5,000", "9,000", "9,000"])
        self.assertNotIn("unknown", lines)

    def test_the_bucket_prints_after_every_role_and_is_named_in_the_footer(self):
        out = self.report(by="role").splitlines()
        table = [ln.split()[0] for ln in out[2:] if not ln.startswith(("unpriced", "(workflow):"))]
        self.assertEqual(table, ["gatherer", "reviewer", "(workflow)"])
        self.assertIn("(workflow): 3 Workflow-tool run(s), unconfined; not counted as spawns",
                      out[-1])

    def test_a_ledger_without_workflow_rows_prints_no_bucket_and_no_footer(self):
        rows = [json.loads(line) for line in self.state.read_text().splitlines()]
        self.state.write_text("".join(json.dumps(r) + "\n" for r in rows if not r["workflow"]),
                              encoding="utf-8")
        out = self.report(by="role")
        self.assertNotIn("(workflow)", out)


class FixtureShape(unittest.TestCase):
    def test_the_fixture_holds_both_kinds_and_a_legacy_budgeted_workflow_row(self):
        rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines()]
        spawned = [r for r in rows if not r["workflow"]]
        workflow = [r for r in rows if r["workflow"]]
        self.assertTrue(spawned and workflow)
        self.assertTrue(any(r["agent_type"] == "gatherer" for r in workflow))
        self.assertTrue(any(r.get("budget_output_tokens") and "unconfined" not in r
                            for r in workflow))


if __name__ == "__main__":
    unittest.main()
