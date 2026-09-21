# SPDX-License-Identifier: MIT
"""A subagent whose stop fires before one word of it has been written to its transcript.

Measured on a native qualification run from a clean home: `SubagentStop` summed the agent's
transcript the instant it fired, the transcript at that instant held nothing but the `user` and
`attachment` records the parent had written into it, and the stop was journalled with null
totals. The one line the session ever printed for that agent said `spend unknown`, while
replaying the same payload against the same home a moment later yielded 297.

So the sum belongs to the moment the agent is reported, not the moment it stops. These tests hold
that shut from both ends — the synchronous `Agent` return and the next prompt's line for a
background spawn — and hold the three things that must not be traded for it: the stop still
journals without waiting, `spend unknown` still means a transcript that is not there, and one
event's summing is bounded however many agents it has to name.

Run: python3 -m unittest discover tests
"""
import time
import unittest

from test_usage_feed import append, assistant, load_feed, write
from test_usage_feed_settling import Clock, SettlingFixture, ended, streaming


def unwritten(prompt="do the thing"):
    """A subagent transcript as it is the instant the agent stops: the parent's records only.

    Claude Code writes the prompt and its attachments into the file when the agent is spawned,
    and the agent's own responses are flushed afterwards. Between the two there is a file with
    no `assistant` record in it at all, which is what the stop hook found.
    """
    return [{"type": "user", "isSidechain": True,
             "message": {"role": "user", "content": prompt}},
            {"type": "attachment", "attachment": {"type": "file", "path": "notes.md"}}]


class RaceFixture(SettlingFixture):
    def unflushed(self, agent_id, agent_type="gatherer"):
        """The agent's transcript before a single response of its own has landed."""
        return self.records(agent_id, agent_type, unwritten())

    def flush(self, agent_id, agent_type="gatherer", messages=(("a1", 4250, ("t1", "t2", "t3")),)):
        """The responses land, after the stop has already been journalled."""
        return self.records(agent_id, agent_type, unwritten() + [
            assistant(mid, output, tools) for mid, output, tools in messages])

    def stop_record(self, agent_id):
        return next(r for r in self.journal() if r["t"] == "stop" and r["id"] == agent_id)

    # --- the hook in this process, so a test can shorten the wait it would really make --------
    def loaded(self, settle=0.0):
        module = load_feed()
        module.SETTLE_BUDGET = settle
        return module

    def submitted(self, module):
        return module.run({"hook_event_name": "UserPromptSubmit", "session_id": self.SESSION,
                           "transcript_path": str(self.transcript)}, self.env()) or []

    def returned_by(self, module, agent_id, agent_type=None, **response):
        body = {"status": "completed", "agentId": agent_id}
        if agent_type:
            body["agentType"] = agent_type
        body.update(response)
        return module.run({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                           "session_id": self.SESSION, "transcript_path": str(self.transcript),
                           "tool_input": {"prompt": "x"}, "tool_response": body}, self.env()) or []


class StopTests(RaceFixture):
    """What `SubagentStop` may and may not do with a transcript that holds nothing yet."""

    def test_a_stop_with_no_response_to_read_is_journalled_as_not_yet_summed(self):
        self.unflushed("aaa")
        self.assertEqual(self.stop("aaa", agent_type="gatherer"), [])
        record = self.stop_record("aaa")
        self.assertIsNone(record["output"])
        self.assertIsNone(record["tool_calls"])
        self.assertFalse(record["summed"])       # not "summed at nothing": not summed
        self.assertTrue(load_feed().needs_sum(record))

    def test_a_stop_that_could_read_the_whole_thing_is_final(self):
        self.flush("bbb")
        self.stop("bbb", agent_type="gatherer")
        record = self.stop_record("bbb")
        self.assertTrue(record["summed"])
        self.assertEqual(record["output"], 4250)
        self.assertFalse(load_feed().needs_sum(record))

    def test_a_figure_read_out_of_a_response_still_being_written_is_not_final(self):
        # The other half of the same race: there is a figure, and it is the partial streaming
        # count. Journalling it as final would print 143 for an agent that spent 278.
        self.records("ccc", "gatherer", [streaming("c1", 143)])
        self.stop("ccc", agent_type="gatherer")
        record = self.stop_record("ccc")
        self.assertEqual(record["output"], 143)
        self.assertFalse(record["summed"])
        self.assertTrue(load_feed().needs_sum(record))

    def test_the_stop_does_not_wait_for_the_response_it_cannot_see(self):
        # The stop runs on the parent's thread with a prompt possibly queued behind it. It is
        # the report that waits, never this.
        self.unflushed("ddd")
        started = time.monotonic()
        self.stop("ddd", agent_type="gatherer")
        self.assertLess(time.monotonic() - started, load_feed().SETTLE_BUDGET + 1)

    def test_the_journalled_path_is_this_agents_own_transcript_and_nothing_else(self):
        module = load_feed()
        self.unflushed("eee")
        self.stop("eee", agent_type="gatherer")
        stored = self.stop_record("eee")["path"]
        self.assertTrue(stored.startswith("~/"), stored)
        self.assertEqual(module.expand(stored, self.env(), "eee"), self.agent_path("eee"))
        self.assertIsNone(module.expand(stored, self.env(), "fff"))
        self.assertIsNone(module.expand("/etc/passwd", self.env(), "eee"))
        self.assertIsNone(module.expand("~/.ssh/id_rsa", self.env(), "eee"))


class ReportTests(RaceFixture):
    """The sum that is made when the agent is named, from both places one is named."""

    def test_the_synchronous_return_prints_the_figure_the_stop_could_not_read(self):
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        self.assertIsNone(self.stop_record("aaa")["output"])
        self.flush("aaa")                                  # the responses land
        self.assertEqual(self.returned("aaa", "gatherer"),
                         ["usage-feed: gatherer finished at 4,250 output tokens and 3 tool "
                          "calls — 0.5× its budget of 8,500 / 15"])
        totals = self.state()["subagents"]
        self.assertEqual((totals["output"], totals["tool_calls"]), (4250, 3))
        self.assertEqual((totals["count"], totals["unknown"]), (1, 0))

    def test_a_background_spawn_is_summed_at_the_prompt_that_names_it(self):
        self.unflushed("bbb")
        self.assertEqual(self.returned("bbb", "gatherer", isAsync=True, status="in_progress"), [])
        self.stop("bbb", agent_type="gatherer")
        self.flush("bbb")
        append(self.transcript, [assistant("m1", 20)])
        lines = self.submit()
        self.assertIn("finished at 4,250 output tokens and 3 tool calls — 0.5× its budget",
                      lines[1])
        self.assertIn("session 4,270 output, 3 tool calls, 1 subagent", lines[0])
        self.assertNotIn("partial", lines[0])
        self.assertEqual(self.state()["subagents"]["unknown"], 0)

    def test_a_launch_between_the_stop_and_the_prompt_costs_nothing_and_loses_nothing(self):
        # A launch's only line is the width note, so it sums nobody and stays as quick as it was.
        # What it ingests while passing through is still reported with its figure, once.
        self.unflushed("ggg")
        self.stop("ggg", agent_type="gatherer")
        started = time.monotonic()
        self.assertEqual(self.returned("ggg", "gatherer", isAsync=True, status="in_progress"), [])
        self.assertLess(time.monotonic() - started, load_feed().REPORT_BUDGET)
        self.flush("ggg")
        append(self.transcript, [assistant("m1", 20)])
        lines = self.submit()
        self.assertIn("finished at 4,250 output tokens and 3 tool calls — 0.5× its budget",
                      lines[1])
        self.assertEqual(self.state()["subagents"], {"output": 4250, "tool_calls": 3, "count": 1,
                                                     "unknown": 0})

    def test_the_agent_is_named_once_however_many_events_sum_it(self):
        self.unflushed("ccc")
        self.stop("ccc", agent_type="gatherer")
        self.flush("ccc")
        self.assertEqual(len(self.returned("ccc", "gatherer")), 1)
        append(self.transcript, [assistant("m1", 20)])
        self.assertEqual([line for line in self.submit() if "finished" in line], [])
        self.assertEqual(self.state()["subagents"]["output"], 4250)

    def test_a_stop_summed_short_is_summed_again_when_it_is_reported(self):
        # The stop read the streaming count. The report reads the record that ended the response.
        self.records("ddd", "gatherer", [streaming("d1", 143)])
        self.stop("ddd", agent_type="gatherer")
        self.records("ddd", "gatherer", [ended("d1", 278)])
        append(self.transcript, [assistant("m1", 10)])
        lines = self.submit()
        self.assertIn("finished at 278 output tokens", lines[1])
        self.assertNotIn("143", lines[1])
        self.assertEqual(self.state()["subagents"]["output"], 278)

    def test_the_sum_is_made_before_the_lock_is_taken(self):
        # The whole reason the stop path was fast. A prompt waiting on this lock has two seconds.
        module = self.loaded()
        order, sums, locks = [], module.settle_many, module.Lock

        class Watched(locks):
            def __enter__(self):
                order.append("lock")
                return locks.__enter__(self)

        module.settle_many = lambda *a, **k: (order.append("sum"), sums(*a, **k))[1]
        module.Lock = Watched
        self.unflushed("eee")
        self.stop("eee", agent_type="gatherer")
        self.flush("eee")
        append(self.transcript, [assistant("m1", 10)])
        self.submitted(module)
        self.assertEqual(order[:2], ["sum", "lock"])


class UnrecordedTests(RaceFixture):
    """A transcript that is there and still holds no response, against one that is not there."""

    def test_a_transcript_that_never_gains_a_response_says_so_and_is_reconciled_later(self):
        module = self.loaded()
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        append(self.transcript, [assistant("m1", 10)])
        lines = self.submitted(module)
        self.assertEqual(lines[1], "usage-feed: gatherer finished, spend not yet recorded")
        self.assertTrue(lines[0].endswith("1 subagent (partial)"), lines[0])
        state = self.state()
        self.assertEqual(state["subagents"]["unknown"], 1)
        self.assertEqual(list(state["unsummed"]), ["aaa"])

        self.flush("aaa")                                  # it lands a turn later
        append(self.transcript, [assistant("m2", 10)])
        later = self.submitted(module)
        self.assertEqual([line for line in later if "finished" in line], [])   # said once
        self.assertIn("session 4,270 output, 3 tool calls, 1 subagent", later[0])
        self.assertNotIn("partial", later[0])
        state = self.state()
        self.assertEqual(state["subagents"], {"output": 4250, "tool_calls": 3, "count": 1,
                                              "unknown": 0})
        self.assertEqual(state["unsummed"], {})

    def test_a_synchronous_return_with_nothing_written_yet_says_the_same(self):
        module = self.loaded()
        self.unflushed("bbb")
        self.assertEqual(self.returned_by(module, "bbb", "gatherer"),
                         ["usage-feed: gatherer finished, spend not yet recorded"])
        self.assertEqual(list(self.state()["unsummed"]), ["bbb"])
        # The stop the journal brings afterwards carries the figure into the totals, silently.
        self.flush("bbb")
        self.stop("bbb", agent_type="gatherer")
        append(self.transcript, [assistant("m1", 10)])
        lines = self.submitted(module)
        self.assertEqual([line for line in lines if "finished" in line], [])
        self.assertEqual(self.state()["subagents"], {"output": 4250, "tool_calls": 3, "count": 1,
                                                     "unknown": 0})

    def test_a_transcript_that_is_not_there_is_spend_unknown_and_is_not_asked_again(self):
        module = self.loaded()
        self.stop("nowhere", agent_type="gatherer")
        append(self.transcript, [assistant("m1", 10)])
        lines = self.submitted(module)
        self.assertEqual(lines[1], "usage-feed: gatherer finished, spend unknown")
        self.assertEqual(self.state()["unsummed"], {})     # final, not pending
        self.assertEqual(self.state()["subagents"]["unknown"], 1)

    def test_a_retry_that_never_comes_good_stops_being_made(self):
        module = self.loaded()
        self.unflushed("ccc")
        self.stop("ccc", agent_type="gatherer")
        for turn in range(module.UNSUMMED_TRIES + 2):
            append(self.transcript, [assistant("m%d" % turn, 10)])
            self.submitted(module)
        self.assertEqual(self.state()["unsummed"], {})
        # It stays counted, and the session line stays honest about the figure it never got.
        self.assertEqual(self.state()["subagents"]["unknown"], 1)
        append(self.transcript, [assistant("last", 10)])
        self.assertIn("(partial)", self.submitted(module)[0])


class BudgetTests(RaceFixture):
    """One event's summing is one budget, whatever it has been handed."""

    def pending_agents(self, count):
        return [("a%d" % index, self.records("a%d" % index, "gatherer",
                                             [streaming("s%d" % index, 10)]))
                for index in range(count)]

    def test_several_agents_share_one_budget_and_the_rest_wait_for_the_next_event(self):
        module = load_feed()
        clock = Clock()
        resolved = module.settle_many(self.pending_agents(8), clock=clock.time,
                                      sleep=clock.sleep)
        self.assertLessEqual(clock.now, module.REPORT_BUDGET)
        self.assertTrue(clock.slept)                       # it did wait on the first ones
        self.assertLess(len(resolved), 8)                  # and it did not wait on all eight
        self.assertTrue(resolved)

    def test_no_agent_is_attempted_in_a_sliver_of_time_it_could_not_be_summed_in(self):
        # A sum cut off after a tenth of a second would report a figure that is on disk as one
        # that has not landed yet. Below the floor the agent waits for the next event instead.
        module = load_feed()
        clock = Clock()
        resolved = module.settle_many(self.pending_agents(3), budget=module.REPORT_SLICE,
                                      clock=clock.time, sleep=clock.sleep)
        self.assertEqual(len(resolved), 1)                 # the first is always attempted
        self.assertTrue(clock.slept)

    def test_an_agent_the_budget_never_reached_keeps_its_place(self):
        module = load_feed()
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        module.settle_many = lambda items, **kw: {}        # the budget reached nobody
        append(self.transcript, [assistant("m1", 10)])
        lines = self.submitted(module)
        self.assertEqual(lines[1], "usage-feed: gatherer finished, spend not yet recorded")
        self.assertEqual(list(self.state()["unsummed"]), ["aaa"])

    def test_the_wait_a_report_makes_is_a_real_one_and_is_bounded(self):
        # The budgets are shortened everywhere else in this file. Here they are not, so that the
        # wait the hook actually makes is measured once rather than assumed.
        self.records("bbb", "gatherer", [streaming("b1", 143)])
        started = time.monotonic()
        line = self.returned("bbb", "gatherer")[0]
        self.assertIn("(so far)", line)
        self.assertLess(time.monotonic() - started, 10)


class ShapeTests(RaceFixture):
    """The state a race leaves behind is still a state file of counts."""

    def test_the_unsummed_list_holds_a_redacted_path_and_a_count_of_tries(self):
        module = self.loaded()
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        append(self.transcript, [assistant("m1", 10)])
        self.submitted(module)
        stored, tries = self.state()["unsummed"]["aaa"]
        self.assertTrue(stored.startswith("~/"), stored)
        self.assertEqual(tries, 1)
        self.assertNotIn(str(self.home), stored)

    def test_an_unsummed_entry_of_a_shape_this_cannot_use_is_dropped(self):
        module = load_feed()
        path = self.feed_dir() / (self.SESSION + ".json")
        state = module.new_state()
        state["unsummed"] = {"aaa": ["~/x/agent-aaa.jsonl", 1], "bbb": "not a pair",
                             "ccc": ["~/x", True]}
        module.save_state(path, state)
        self.assertEqual(list(module.load_state(path)["unsummed"]), ["aaa"])

    def test_the_unsummed_list_is_bounded(self):
        module = load_feed()
        path = self.feed_dir() / (self.SESSION + ".json")
        state = module.new_state()
        for index in range(module.MAX_PENDING + 40):
            module.remember_unsummed(state, "a%05d" % index, "~/x/agent-a.jsonl")
        module.save_state(path, state)
        self.assertEqual(len(module.load_state(path)["unsummed"]), module.MAX_PENDING)

    def test_a_reload_keeps_what_a_retry_needs(self):
        module = load_feed()
        path = self.feed_dir() / (self.SESSION + ".json")
        state = module.new_state()
        module.remember_unsummed(state, "aaa", "~/x/agent-aaa.jsonl")
        module.save_state(path, state)
        self.assertEqual(module.load_state(path)["unsummed"], {"aaa": ["~/x/agent-aaa.jsonl", 1]})

    def test_writing_the_turn_off_still_writes_nothing_anywhere(self):
        self.variant("plain", {"schema_version": 1, "extends": None, "rows": {}})
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        self.assertEqual(self.returned("aaa", "gatherer"), [])
        self.assertEqual(self.submit(), [])
        self.assertFalse(self.feed_dir().exists())


class TotalsTests(RaceFixture):
    """The session total is the sum of the final figures, whichever path filled it in."""

    def test_a_resolved_unknown_raises_the_total_and_lowers_the_unknown_count(self):
        module = load_feed()
        state = module.new_state()
        module.count(state, {"id": "aaa", "output": None, "tool_calls": None})
        self.assertEqual(state["subagents"], {"output": 0, "tool_calls": 0, "count": 1,
                                              "unknown": 1})
        module.resolve_unknown(state, "aaa", [297, 4])
        self.assertEqual(state["subagents"], {"output": 297, "tool_calls": 4, "count": 1,
                                              "unknown": 0})
        self.assertEqual(state["figures"]["aaa"], [297, 4])
        # And the journal's own later figure still reconciles from there, never below it.
        module.reconcile(state, {"id": "aaa", "output": 300, "tool_calls": 4})
        self.assertEqual(state["subagents"]["output"], 300)
        module.reconcile(state, {"id": "aaa", "output": 1, "tool_calls": 0})
        self.assertEqual(state["subagents"]["output"], 300)

    def test_a_figure_never_takes_a_figure_away(self):
        module = load_feed()
        record = {"id": "aaa", "output": 143, "tool_calls": 2, "partial": True}
        module.apply_settled(record, module.PENDING)
        self.assertEqual(record["output"], 143)            # a journalled partial beats nothing
        self.assertNotIn("not_yet", record)
        module.apply_settled(record, {"output": 278, "tool_calls": 3, "partial": False,
                                      "settled": True, "agent_type": "gatherer"})
        self.assertEqual((record["output"], record["partial"], record["so_far"]),
                         (278, False, False))

    def test_the_session_totals_survive_a_transcript_being_replaced(self):
        # A compaction resets what the parent transcript said. What a subagent is still owed is
        # not the parent's to forget.
        module = self.loaded()
        self.unflushed("aaa")
        self.stop("aaa", agent_type="gatherer")
        append(self.transcript, [assistant("m1", 10)])
        self.submitted(module)
        self.assertEqual(list(self.state()["unsummed"]), ["aaa"])
        write(self.transcript, [assistant("n1", 5)])       # smaller: a compaction
        self.flush("aaa")
        self.submitted(module)
        self.assertEqual(self.state()["subagents"]["output"], 4250)
        self.assertEqual(self.state()["unsummed"], {})


if __name__ == "__main__":
    unittest.main()
