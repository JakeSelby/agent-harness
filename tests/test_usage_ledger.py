# SPDX-License-Identifier: MIT
"""What a ledger row says about itself: harness version, session effort and per-day slices.

A session was attributed to the day it ended, so a run of a fortnight landed on one date and a
handful of long sessions dominated every before-and-after comparison. A row also said nothing
about which harness version wrote it or what effort the session ran at, so a change in spend
could not be tied to a release or told apart from an effort change.

Every transcript here is synthetic: the shapes are the ones the runtimes write — Claude Code's
`effort` on each assistant record, Codex's `turn_context.effort` and its cumulative
`total_token_usage` snapshots — and the figures are hand-chosen so the arithmetic is checkable
by eye. Run: python3 -m unittest discover tests
"""
import contextlib
import copy
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import CFG
from test_usage import REPO, harness, usage_log

workers = harness.workers

VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()


def ts(hours_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - hours_ago * 3600))


# Twenty-six hours apart, so the two are always different UTC dates whatever hour it is now.
EARLIER, LATER = ts(26), ts(1)
DAY_ONE, DAY_TWO = EARLIER[:10], LATER[:10]


def assistant(mid, stamp, output, effort=None, model="model-a", session="s-1"):
    entry = {"type": "assistant", "sessionId": session, "cwd": "", "timestamp": stamp,
             "message": {"id": mid, "model": model, "content": [],
                         "usage": {"input_tokens": 1, "output_tokens": output,
                                   "cache_read_input_tokens": 10,
                                   "cache_creation_input_tokens": 2}}}
    if effort:
        entry["effort"] = effort
        entry["perTurnEffort"] = effort
    return entry


def write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def codex_rollout(path, session_id="c-1"):
    """A top-level Codex rollout over two dates, changing effort after the first turn.

    Two cumulative snapshots, as Codex writes them: the second is the running total and not the
    turn's own, which is what makes the per-day and per-effort figures differences.
    """
    return write(path, [
        {"timestamp": EARLIER, "type": "session_meta",
         "payload": {"id": session_id, "session_id": session_id, "cwd": "/work/example-repo",
                     "source": "cli", "cli_version": "0.156.0"}},
        {"timestamp": EARLIER, "type": "turn_context",
         "payload": {"turn_id": "t1", "model": "gpt-6-astra", "effort": "medium"}},
        {"timestamp": EARLIER, "type": "event_msg",
         "payload": {"type": "token_count", "info": {"total_token_usage": {
             "input_tokens": 1000, "cached_input_tokens": 400,
             "cache_write_input_tokens": 50, "output_tokens": 300,
             "total_tokens": 1300}}}},
        {"timestamp": LATER, "type": "turn_context",
         "payload": {"turn_id": "t2", "model": "gpt-6-astra", "effort": "ultra"}},
        {"timestamp": LATER, "type": "event_msg",
         "payload": {"type": "token_count", "info": {"total_token_usage": {
             "input_tokens": 3000, "cached_input_tokens": 1400,
             "cache_write_input_tokens": 150, "output_tokens": 1100,
             "total_tokens": 4100}}}},
    ])


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        os.environ.pop("HARNESS_QUIET", None)
        self.addCleanup(self.restore)

    def restore(self):
        if self._home is not None:
            os.environ["HOME"] = self._home

    @property
    def state(self):
        return self.home / ".local/state/agent-harness/usage.jsonl"

    def write_rows(self, rows):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def session_fixture(self):
        """A session whose own turns are on day one and whose subagent ran on day two."""
        project = self.home / ".claude" / "projects" / "a-repo"
        transcript = write(project / "s-1.jsonl", [
            {"type": "user", "sessionId": "s-1", "cwd": "", "timestamp": EARLIER},
            assistant("m1", EARLIER, 100, effort="high"),
            assistant("m2", EARLIER, 400, effort="max"),
        ])
        agents = project / "s-1" / "subagents"
        write(agents / "agent-aaa.jsonl", [assistant("a1", LATER, 700, model="model-haiku")])
        (agents / "agent-aaa.meta.json").write_text(
            json.dumps({"agentType": "gatherer", "spawnDepth": 1}), encoding="utf-8")
        return transcript

    def report(self, **kwargs):
        args = harness.argparse.Namespace(
            days=kwargs.pop("days", 30), by=kwargs.pop("by", "day"),
            stance=kwargs.pop("stance", None), rules=kwargs.pop("rules", False),
            rescan=kwargs.pop("rescan", False))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = harness.cmd_usage(args)
        self.assertEqual(code, kwargs.pop("code", 0))
        return buf.getvalue()


class VersionStamp(LedgerTest):
    def test_the_hook_reads_the_version_file_the_cli_reads(self):
        self.assertEqual(usage_log.harness_version(), VERSION)
        self.assertEqual(workers.harness_version(REPO), VERSION)

    def test_a_live_row_names_the_version_that_wrote_it(self):
        usage_log.main(["--worker", str(self.session_fixture()), "s-1", ""])
        rows = [json.loads(line) for line in self.state.read_text().splitlines()]
        self.assertEqual(sorted(r["kind"] for r in rows), ["session", "subagent"])
        for row in rows:
            self.assertEqual(row["harness_version"], VERSION)

    def test_a_rescanned_row_names_no_version_rather_than_todays(self):
        self.session_fixture()
        self.assertEqual(usage_log.rescan(30), 1)
        rows = [json.loads(line) for line in self.state.read_text().splitlines()]
        self.assertTrue(rows)
        for row in rows:
            self.assertIsNone(row["harness_version"])
        session = [r for r in rows if r["kind"] == "session"][0]
        self.assertEqual(session["stances_source"], "rescan")

    def test_a_codex_row_is_stamped_the_same_way(self):
        rollout = codex_rollout(self.home / "rollout.jsonl")
        self.assertEqual(usage_log.scan(rollout)["harness_version"], VERSION)
        self.assertIsNone(usage_log.scan(rollout, rescan=True)["harness_version"])

    def test_a_worker_row_carries_the_version_stamped_when_the_run_started(self):
        run = self.home / ".local/state/agent-harness/workers/w1"
        run.mkdir(parents=True)
        (run / "status.json").write_text(json.dumps({
            "id": "w1", "role": "reviewer", "status": "completed", "runtime": "claude-code",
            "harness_version": "0.9.9", "started_at": time.time(), "finished_at": time.time(),
            "usage": {"output": 120}}), encoding="utf-8")
        rows = usage_log.worker_rows(0)
        self.assertEqual([r["harness_version"] for r in rows], ["0.9.9"])

    def test_a_run_stamps_the_version_into_its_status_file(self):
        workspace = self.home / "project"
        workspace.mkdir()
        state = self.home / "worker-state"

        def fake(command, prompt, env, cwd, run_dir, timeout):
            (run_dir / "stdout.log").write_text(json.dumps(
                {"type": "result", "subtype": "success", "is_error": False, "result": "done"}))
            return 0

        # Run from inside a client session, `CLAUDECODE` would send the stand-in client through
        # the token-only preflight (#759); this test is about the version stamp, not that.
        session = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        with patch.object(workers.shutil, "which", return_value="/native/cli"), \
                patch.object(workers.subprocess, "check_output", return_value="fixture-version"), \
                patch.object(workers, "execute", side_effect=fake), \
                patch.dict(os.environ, session, clear=True):
            result = workers.run(REPO, copy.deepcopy(CFG), "claude-code", "reviewer", workspace,
                                 "Inspect the fixture", state, model="fixture-model")
        self.assertEqual(result["harness_version"], VERSION)
        self.assertEqual(workers.status(state, result["id"])[0]["harness_version"], VERSION)


class SessionEffort(LedgerTest):
    def test_the_recorded_effort_is_the_one_covering_the_most_output(self):
        # `high` wrote 100 output tokens and `max` wrote 400, so the session ran mostly at max.
        record = usage_log.scan(self.session_fixture(), "s-1", "")
        self.assertEqual(record["effort"], "max")
        self.assertEqual(record["effort_source"], "transcript")

    def test_a_transcript_that_records_no_effort_records_none(self):
        path = write(self.home / "plain.jsonl", [assistant("m1", EARLIER, 10)])
        record = usage_log.scan(path, "s-2", "")
        self.assertIsNone(record["effort"])
        self.assertIsNone(record["effort_source"])

    def test_a_subagents_effort_is_not_weighed_into_its_sessions(self):
        project = self.home / ".claude" / "projects" / "a-repo"
        transcript = write(project / "s-1.jsonl", [assistant("m1", EARLIER, 100, effort="high")])
        agents = project / "s-1" / "subagents"
        write(agents / "agent-aaa.jsonl", [assistant("a1", LATER, 9000, effort="low")])
        (agents / "agent-aaa.meta.json").write_text(
            json.dumps({"agentType": "gatherer"}), encoding="utf-8")
        session = usage_log.scan_all(transcript, "s-1", "")[0]
        self.assertEqual(session["effort"], "high")

    def test_codex_effort_is_weighed_by_the_output_between_snapshots(self):
        # 300 output tokens under `medium`, then 800 more under `ultra`, from the deltas.
        record = usage_log.scan(codex_rollout(self.home / "rollout.jsonl"))
        self.assertEqual(record["effort"], "ultra")
        self.assertEqual(record["effort_source"], "turn_context")


class DaySlices(LedgerTest):
    def test_claude_slices_sum_to_the_rows_totals(self):
        record = usage_log.scan_all(self.session_fixture(), "s-1", "")[0]
        days = record["days"]
        self.assertEqual(sorted(days), sorted([DAY_ONE, DAY_TWO]))
        for name in ("input", "output", "cache_read", "cache_write"):
            self.assertEqual(sum(day[name] for day in days.values()), record[name])
        self.assertEqual(sum(day["turns"] for day in days.values()), record["turns"])

    def test_a_days_slice_holds_that_days_subagent_tokens(self):
        # The session total includes its subagents, so a slice does too: the agent ran on day
        # two and its 700 output tokens are day two's, not the day the session ended.
        record = usage_log.scan_all(self.session_fixture(), "s-1", "")[0]
        self.assertEqual(record["days"][DAY_ONE]["output"], 500)
        self.assertEqual(record["days"][DAY_TWO]["output"], 700)
        self.assertEqual(record["days"][DAY_TWO]["turns"], 0)

    def test_codex_slices_are_snapshot_deltas_and_stay_net_of_cache(self):
        record = usage_log.scan(codex_rollout(self.home / "rollout.jsonl"))
        days = record["days"]
        self.assertEqual(days[DAY_ONE], {"input": 600, "output": 300, "cache_read": 400,
                                         "cache_write": 50, "turns": 1})
        self.assertEqual(days[DAY_TWO], {"input": 1000, "output": 800, "cache_read": 1000,
                                         "cache_write": 100, "turns": 1})
        for name in ("input", "output", "cache_read", "cache_write"):
            self.assertEqual(sum(day[name] for day in days.values()), record[name])

    def test_a_total_only_codex_row_carries_no_slices(self):
        path = write(self.home / "desktop.jsonl", [
            {"timestamp": EARLIER, "type": "session_meta",
             "payload": {"id": "c-2", "cwd": "/work/example-repo", "source": "vscode"}},
            {"timestamp": EARLIER, "type": "turn_context", "payload": {"model": "gpt-6-astra"}},
            {"timestamp": LATER, "type": "event_msg",
             "payload": {"type": "token_count", "info": {"total_token_usage": {
                 "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
                 "total_tokens": 4100}}}}])
        record = usage_log.scan(path)
        self.assertTrue(record["partial"])
        self.assertNotIn("days", record)

    def test_by_day_reports_a_two_day_session_on_both_days(self):
        usage_log.main(["--worker", str(self.session_fixture()), "s-1", ""])
        lines = {ln.split()[0]: ln.split() for ln in self.report(by="day").splitlines()[2:]}
        self.assertIn(DAY_ONE, lines)
        self.assertIn(DAY_TWO, lines)
        # Output — the fourth column, after the label, the runs and the input — is 500 on the
        # day the turns ran and 700 on the day the subagent did.
        self.assertEqual(lines[DAY_ONE][3], "500")
        self.assertEqual(lines[DAY_TWO][3], "700")
        # The run is counted once, on the day the session's own last record was written, so
        # TOTAL still counts sessions rather than session-days.
        self.assertEqual(lines[DAY_ONE][1], "1")
        self.assertEqual(lines[DAY_TWO][1], "0")
        self.assertEqual([lines["TOTAL"][1], lines["TOTAL"][3]], ["1", "1,200"])

    def test_the_window_applies_to_the_slice_date(self):
        row = {"kind": "session", "runtime": "claude-code", "session_id": "s-9", "repo": "a-repo",
               "models": ["model-a"], "ended": LATER, "input": 30, "output": 1200,
               "cache_read": 0, "cache_write": 0, "turns": 2,
               "days": {"2020-01-01": {"input": 20, "output": 1000, "cache_read": 0,
                                       "cache_write": 0, "turns": 1},
                        DAY_TWO: {"input": 10, "output": 200, "cache_read": 0,
                                  "cache_write": 0, "turns": 1}}}
        self.write_rows([row])
        lines = {ln.split()[0]: ln.split() for ln in self.report(by="day", days=7).splitlines()[2:]}
        self.assertNotIn("2020-01-01", lines)
        # Only the in-window day is reported, so the old day's 1,000 tokens are not today's.
        self.assertEqual(lines["TOTAL"][3], "200")

    def test_a_row_with_no_slices_falls_back_to_its_end_date(self):
        self.write_rows([{"kind": "session", "runtime": "claude-code", "session_id": "s-8",
                          "repo": "a-repo", "models": ["model-a"], "ended": LATER,
                          "input": 5, "output": 90, "cache_read": 0, "cache_write": 0}])
        lines = {ln.split()[0]: ln.split() for ln in self.report(by="day").splitlines()[2:]}
        self.assertEqual(lines[DAY_TWO][1:4], ["1", "5", "90"])


class StanceTokens(LedgerTest):
    def rows(self):
        def row(ident, variant, output, **extra):
            base = {"kind": "session", "runtime": "claude-code", "session_id": ident,
                    "repo": "a-repo", "models": ["model-a"], "ended": LATER, "input": 1,
                    "output": output, "cache_read": 0, "cache_write": 0, "turns": 1,
                    "stances": {"cost": variant, "testing": "required"}}
            base.update(extra)
            return base
        return [row("s-1", "balanced", 100), row("s-2", "balanced", 200),
                row("s-3", "frugal", 50), row("s-4", "balanced", 900, stances_source="rescan"),
                row("s-5", None, 10, stances={})]

    def test_by_stance_groups_tokens_by_the_named_dimension(self):
        self.write_rows(self.rows())
        lines = {ln.split()[0]: ln.split()
                 for ln in self.report(by="stance", stance="cost").splitlines()[2:]}
        self.assertEqual(lines["cost=balanced"][1:3], ["2", "2"])
        self.assertEqual(lines["cost=balanced"][3], "300")
        self.assertEqual(lines["cost=frugal"][3], "50")

    def test_a_rescanned_or_unstamped_row_is_counted_as_unknown(self):
        self.write_rows(self.rows())
        lines = {ln.split()[0]: ln.split()
                 for ln in self.report(by="stance", stance="cost").splitlines()[2:]}
        # Counted, never dropped: the rescanned 900 and the unstamped 10 are 910 unknown.
        self.assertEqual(lines["(unknown)"][1], "2")
        self.assertEqual(lines["(unknown)"][3], "910")
        self.assertEqual(lines["TOTAL"][3], "1,260")

    def test_by_stance_with_neither_rules_nor_a_dimension_is_refused(self):
        self.write_rows(self.rows())
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = harness.cmd_usage(harness.argparse.Namespace(
                days=30, by="stance", stance=None, rules=False, rescan=False))
        self.assertEqual(code, 2)
        self.assertIn("--stance", buf.getvalue())

    def test_rules_by_stance_still_reports_hits(self):
        rows = [dict(r, rules={"voice/second-table": 1}, counts={}) for r in self.rows()[:1]]
        self.write_rows(rows)
        out = self.report(by="stance", rules=True)
        self.assertIn("cost=balanced", out)
        self.assertIn("voice/second-table", out)


class RoleSample(LedgerTest):
    def agent(self, index, role):
        return {"kind": "subagent", "runtime": "claude-code", "session_id": "s-1",
                "agent_id": "a%d" % index, "agent_type": role, "model": "model-a",
                "input": 1, "output": 100, "cache_read": 0, "cache_write": 0,
                "tool_calls": 2, "ended": LATER}

    def test_a_role_under_thirty_runs_is_marked_and_one_at_thirty_is_not(self):
        self.write_rows([self.agent(i, "builder") for i in range(harness.ROLE_MIN_RUNS)]
                        + [self.agent(100 + i, "reviewer") for i in range(3)])
        lines = {ln.split()[0]: ln for ln in self.report(by="role").splitlines()[2:]}
        self.assertNotIn("n<30", lines["builder"])
        self.assertTrue(lines["reviewer"].rstrip().endswith("n<30"))


if __name__ == "__main__":
    unittest.main()
