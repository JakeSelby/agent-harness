# SPDX-License-Identifier: MIT
"""A synchronous subagent return whose last response is still being written.

Claude Code writes one API response as several records repeating its message id: the early ones
carry `stop_reason: null` and a partial streaming `output_tokens`, and the record that ends the
response carries a reason. `PostToolUse` on the `Agent` call can fire between the two, which is
how a live feed came to say 143 output tokens for an agent a later scan put at 278.

Three behaviours hold that shut: the return waits a bounded moment for the response to end, it
says `(so far)` rather than an exact-looking figure when it never does, and the settled figure
the journal brings afterwards raises the session total without the agent being named twice.

Run: python3 -m unittest discover tests
"""
import json
import threading
import time
import unittest

from test_usage_feed import Fixture, assistant, load_feed, write


def streaming(mid, output):
    """One record of a response still arriving: a reason of null, a partial count."""
    record = assistant(mid, output)
    record["message"]["stop_reason"] = None
    return record


def ended(mid, output, reason="end_turn"):
    """The record that ends a response. Measured on real transcripts: it holds the id's largest
    figure, over 1,418 message ids without one exception."""
    record = assistant(mid, output)
    record["message"]["stop_reason"] = reason
    return record


class Clock(object):
    """A clock and a sleep that move only when the code under test sleeps."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def time(self):
        return self.now


class SettlingFixture(Fixture):
    def records(self, agent_id, agent_type, entries):
        """A subagent transcript written record by record, `stop_reason` and all."""
        path = self.agent_path(agent_id)
        write(path, entries)
        path.with_name(path.stem + ".meta.json").write_text(json.dumps(
            {"agentType": agent_type, "toolUseId": "use-" + agent_id, "spawnDepth": 1}))
        return path


class WaitTests(SettlingFixture):
    def test_a_final_record_that_lands_between_two_reads_is_reported_at_its_settled_figure(self):
        path = self.records("aaa", "planner", [ended("a1", 100), streaming("a2", 143)])
        finish = threading.Timer(0.2, lambda: write(
            path, [ended("a1", 100), streaming("a2", 143), ended("a2", 278)]))
        finish.start()
        self.addCleanup(finish.cancel)
        line = self.returned("aaa", "planner")[0]
        self.assertIn("finished at 378 output tokens", line)   # 100 + 278, not 100 + 143
        self.assertNotIn("so far", line)

    def test_a_settled_transcript_is_not_waited_on_at_all(self):
        module = load_feed()
        clock = Clock()
        path = self.records("bbb", "planner", [ended("b1", 500)])
        totals = module.settled_totals(path, clock=clock.time, sleep=clock.sleep)
        self.assertEqual(clock.slept, [])
        self.assertTrue(totals["settled"])
        self.assertEqual(totals["output"], 500)

    def test_the_wait_is_bounded_by_its_budget_and_then_gives_up(self):
        module = load_feed()
        clock = Clock()
        path = self.records("ccc", "planner", [streaming("c1", 143)])
        totals = module.settled_totals(path, clock=clock.time, sleep=clock.sleep)
        self.assertFalse(totals["settled"])
        self.assertEqual(totals["output"], 143)
        self.assertLessEqual(sum(clock.slept), module.SETTLE_BUDGET)
        self.assertTrue(clock.slept)                       # it did wait
        self.assertEqual(set(clock.slept), {module.SETTLE_STEP})

    def test_a_record_with_no_stop_reason_at_all_is_taken_as_it_stands(self):
        # A transcript from a writer whose streaming this cannot judge is not waited on: the
        # wait exists for a marker Claude Code writes, not for every file that lacks one.
        module = load_feed()
        clock = Clock()
        path = self.records("ddd", "planner", [assistant("d1", 900)])
        totals = module.settled_totals(path, clock=clock.time, sleep=clock.sleep)
        self.assertEqual(clock.slept, [])
        self.assertTrue(totals["settled"])

    def test_the_tail_is_judged_on_the_last_assistant_record_not_the_last_line(self):
        module = load_feed()
        path = self.records("eee", "planner", [ended("e1", 40), {"type": "system", "x": 1}])
        self.assertTrue(module.tail_settled(path))
        path = self.records("fff", "planner", [streaming("f1", 40), {"type": "system", "x": 1}])
        self.assertFalse(module.tail_settled(path))

    def test_a_transcript_that_is_not_there_is_not_waited_on(self):
        module = load_feed()
        clock = Clock()
        self.assertTrue(module.tail_settled(self.agent_path("nope")))
        self.assertIsNone(module.settled_totals(None, clock=clock.time, sleep=clock.sleep))
        self.assertEqual(clock.slept, [])

    def test_a_figure_that_never_settles_is_printed_as_so_far(self):
        self.records("ggg", "planner", [streaming("g1", 143)])
        started = time.monotonic()
        line = self.returned("ggg", "planner")[0]
        elapsed = time.monotonic() - started
        self.assertEqual(line, "usage-feed: planner finished at 143 output tokens and 0 tool "
                               "calls (so far)")
        self.assertLess(elapsed, 5)   # the wait is bounded; the process is not

    def test_a_sum_cut_short_keeps_the_larger_caveat(self):
        module = load_feed()
        line, _ = module.agent_line("planner", 10, 1, None, [], partial=True, provisional=True)
        self.assertTrue(line.endswith("(partial)"), line)
        self.assertNotIn("so far", line)


class ReconciliationTests(SettlingFixture):
    def settle(self, agent_id, agent_type, output):
        """The subagent's last response finishes being written, after the return was reported."""
        return self.records(agent_id, agent_type, [ended("a1", output)])

    def test_a_larger_settled_figure_raises_the_session_total_without_a_second_line(self):
        self.records("aaa", "planner", [streaming("a1", 143)])
        self.assertIn("(so far)", self.returned("aaa", "planner")[0])
        self.assertEqual(self.state()["subagents"]["output"], 143)

        self.settle("aaa", "planner", 278)
        self.stop("aaa")                                   # the journal's settled figure
        write(self.transcript, [assistant("m1", 20)])
        lines = self.submit()

        self.assertEqual([line for line in lines if "finished at" in line], [])
        self.assertIn("session 298 output", lines[0])      # 20 + 278, never 20 + 143
        state = self.state()
        self.assertEqual(state["subagents"]["output"], 278)
        self.assertEqual(state["subagents"]["count"], 1)   # counted once, not twice
        self.assertEqual(state["counted"], ["aaa"])

    def test_the_session_total_is_never_below_the_sum_of_the_final_figures(self):
        module = load_feed()
        journal = self.feed_dir() / (self.SESSION + ".events.jsonl")
        state = module.new_state()
        final = {}
        for index in range(4):
            agent = "a%d" % index
            provisional = {"id": agent, "type": "planner", "output": 10 + index,
                           "tool_calls": 1, "so_far": True}
            state["counted"].append(agent)
            module.count(state, provisional)
            final[agent] = 100 + index * 5
            module.journal_append(journal, {"t": "stop", "id": agent, "type": "planner",
                                            "at": int(time.time()), "output": final[agent],
                                            "tool_calls": 2})
        state = module.ingest(state, journal)
        self.assertEqual(state["subagents"]["output"], sum(final.values()))
        self.assertEqual(state["subagents"]["tool_calls"], 8)
        self.assertEqual(state["subagents"]["count"], 4)
        # Reading the journal again changes nothing, and a smaller late figure lowers nothing.
        module.journal_append(journal, {"t": "stop", "id": "a0", "type": "planner",
                                        "at": int(time.time()), "output": 1, "tool_calls": 0})
        state["journal_offset"] = 0
        state = module.ingest(state, journal)
        self.assertEqual(state["subagents"]["output"], sum(final.values()))

    def test_the_figures_survive_a_reload_and_stay_bounded(self):
        module = load_feed()
        path = self.feed_dir() / (self.SESSION + ".json")
        state = module.new_state()
        module.count(state, {"id": "aaa", "output": 5, "tool_calls": 1})
        module.save_state(path, state)
        loaded = module.load_state(path)
        self.assertEqual(loaded["figures"]["aaa"], [5, 1])
        loaded["figures"]["junk"] = "not a pair"
        module.save_state(path, loaded)
        self.assertNotIn("junk", module.load_state(path)["figures"])
        for index in range(module.MAX_COUNTED + 50):
            module.count(state, {"id": "b%05d" % index, "output": 1, "tool_calls": 0})
        self.assertEqual(len(state["figures"]), module.MAX_COUNTED)

    def test_a_counted_agent_with_no_remembered_figure_raises_nothing(self):
        # What a state file written before this existed looks like: the id is counted and its
        # figure is not on file. There is no difference to add, so the total stays as it is
        # rather than counting the agent a second time.
        module = load_feed()
        journal = self.feed_dir() / (self.SESSION + ".events.jsonl")
        state = module.new_state()
        state["counted"].append("aaa")
        state["subagents"] = {"output": 143, "tool_calls": 2, "count": 1, "unknown": 0}
        module.journal_append(journal, {"t": "stop", "id": "aaa", "type": "planner",
                                        "at": int(time.time()), "output": 278, "tool_calls": 4})
        state = module.ingest(state, journal)
        self.assertEqual(state["subagents"], {"output": 143, "tool_calls": 2, "count": 1,
                                              "unknown": 0})


if __name__ == "__main__":
    unittest.main()
