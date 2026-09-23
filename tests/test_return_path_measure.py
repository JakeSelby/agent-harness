# SPDX-License-Identifier: MIT
"""Whether a subagent return carried a path instead of the payload, on the ledger row.

`transcript-hygiene` says the detail goes to a file and the verdict plus the path comes back.
These tests hold the two deterministic halves of that: a path the reader can actually open, and
a return that stayed inside the cap its brief stated. Nothing here is a judgment of the return's
content — that is #157's question, and these fields are the labelled input it reads.

Run: python3 -m unittest discover tests
"""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from test_usage import REPO, harness, usage_log

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex"
STAMPS = [time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 600 + i * 30))
          for i in range(8)]


def brief_of(words):
    return " ".join("word" for _ in range(words))


class Transcript(unittest.TestCase):
    """One session that spawned agents, each with its brief, its return and its own transcript.

    Laid out the way Claude Code writes it: the parent records the `Agent` call as the model
    wrote it and the return as a `tool_result`, and the subagent's `.meta.json` names the tool
    use id that joins the two to its row.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = Path(self.tmp.name) / "worktree"
        (self.cwd / "notes").mkdir(parents=True)
        (self.cwd / "notes" / "dimension-a.md").write_text("the long version", encoding="utf-8")
        self.project = Path(self.tmp.name) / "projects"
        self.spawns = []

    def spawn(self, agent_id, brief, returned, agent_type="builder"):
        self.spawns.append((agent_id, brief, returned, agent_type))

    def rows(self, join=True, ran_as=None):
        entries = [{"type": "user", "sessionId": "s-1", "cwd": str(self.cwd),
                    "timestamp": STAMPS[0]}]
        calls, results = [], []
        for agent_id, brief, returned, agent_type in self.spawns:
            calls.append({"type": "tool_use", "id": "tu-" + agent_id, "name": "Agent",
                          "input": {"subagent_type": agent_type, "prompt": brief}})
            results.append({"type": "tool_result", "tool_use_id": "tu-" + agent_id,
                            "content": returned})
        entries.append({"type": "assistant", "sessionId": "s-1", "cwd": str(self.cwd),
                        "timestamp": STAMPS[1],
                        "message": {"id": "m1", "model": "model-a", "content": calls,
                                    "usage": {"input_tokens": 1, "output_tokens": 20}}})
        entries.append({"type": "user", "sessionId": "s-1", "cwd": str(self.cwd),
                        "timestamp": STAMPS[2], "message": {"content": results}})
        transcript = self.project / "s-1.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        subagents = self.project / "s-1" / "subagents"
        subagents.mkdir(parents=True, exist_ok=True)
        for agent_id, _, _, agent_type in self.spawns:
            (subagents / ("agent-%s.jsonl" % agent_id)).write_text(json.dumps(
                {"type": "assistant", "timestamp": STAMPS[3],
                 "message": {"id": "a-" + agent_id, "model": "model-b", "content": [],
                             "usage": {"input_tokens": 1, "output_tokens": 40}}}) + "\n",
                encoding="utf-8")
            meta = {"agentType": ran_as or agent_type, "spawnDepth": 1}
            if join:
                meta["toolUseId"] = "tu-" + agent_id
            (subagents / ("agent-%s.meta.json" % agent_id)).write_text(json.dumps(meta),
                                                                       encoding="utf-8")
        rows = usage_log.scan_all(transcript, "s-1", str(self.cwd))
        return dict((row["agent_id"], row) for row in rows if row["kind"] == "subagent")

    def row(self, returned, brief="Return at most 400 words.", agent_type="builder"):
        self.spawn("aaa", brief, returned, agent_type)
        return self.rows()["aaa"]

    def rows_for(self, returned):
        """One row per call, over a fixture that is built fresh each time."""
        self.spawns = []
        return self.row(returned)


class PathTests(Transcript):
    def test_a_return_naming_a_file_that_exists_carries_a_resolvable_path(self):
        row = self.row("Fixed. The long version is at `notes/dimension-a.md`.")
        self.assertEqual(row["return_path"], "resolvable")

    def test_an_absolute_path_inside_the_worktree_resolves_too(self):
        row = self.row("Fixed. Detail: " + str(self.cwd / "notes" / "dimension-a.md"))
        self.assertEqual(row["return_path"], "resolvable")

    def test_a_path_in_a_fenced_block_counts(self):
        row = self.row("Fixed.\n\n```\nnotes/dimension-a.md\n```\n")
        self.assertEqual(row["return_path"], "resolvable")

    def test_a_path_that_does_not_exist_is_unresolvable(self):
        row = self.row("Fixed. The long version is at notes/dimension-z.md.")
        self.assertEqual(row["return_path"], "unresolvable")

    def test_a_path_outside_the_worktree_and_the_scratchpad_does_not_count(self):
        # /etc/hosts exists on every machine this runs on and is nobody's scratchpad.
        row = self.row("Fixed. See /etc/hosts for the detail.")
        self.assertEqual(row["return_path"], "unresolvable")

    def test_a_return_with_no_path_carries_none_and_is_not_a_failure(self):
        row = self.row("Fixed. The filter bites and one record was spot-checked.")
        self.assertEqual(row["return_path"], "none")

    def test_a_scratchpad_file_resolves_from_outside_the_worktree(self):
        scratch = Path(self.tmp.name) / "scratch"
        scratch.mkdir()
        (scratch / "digest.md").write_text("detail", encoding="utf-8")
        row = self.row("Fixed. Digest: %s" % (scratch / "digest.md"))
        self.assertEqual(row["return_path"], "resolvable")

    def test_a_url_contributes_nothing_at_all(self):
        row = self.row("Fixed. See https://example.com/notes/dimension-a.md for the source.")
        self.assertEqual(row["return_path"], "none")

    def test_a_relative_prefix_survives_the_trailing_trim(self):
        row = self.row("Fixed. Detail in ./notes/dimension-a.md.")
        self.assertEqual(row["return_path"], "resolvable")

    def test_prose_with_a_slash_in_it_is_not_a_path(self):
        for prose in ("the check is pass/fail", "24/7 and 3/4 of the rows", "on 2026/09/22",
                      "they/them throughout"):
            self.assertEqual(self.rows_for(prose)["return_path"], "none", prose)

    def test_a_slashed_word_pair_inside_backticks_is_taken_at_its_word(self):
        row = self.row("Wrote `notes/dimension-a`.")
        self.assertEqual(row["return_path"], "unresolvable")

    def test_resolution_is_taken_when_the_row_is_written_not_when_the_agent_returned(self):
        self.spawn("aaa", "Return at most 400 words.", "Fixed. See notes/dimension-a.md.")
        (self.cwd / "notes" / "dimension-a.md").unlink()
        self.assertEqual(self.rows()["aaa"]["return_path"], "unresolvable")


class BudgetTests(Transcript):
    def test_a_return_past_the_cap_its_brief_stated_is_over_budget(self):
        row = self.row(brief_of(30), brief="Return at most 10 words: the verdict first.")
        self.assertIs(row["return_over_budget"], True)

    def test_a_return_inside_that_cap_is_not(self):
        row = self.row(brief_of(5), brief="Return at most 10 words: the verdict first.")
        self.assertIs(row["return_over_budget"], False)

    def test_a_brief_that_stated_no_cap_is_measured_against_the_one_the_hook_appends(self):
        _, _, default = usage_log.return_rules()
        self.assertEqual(default, 400)
        self.spawn("aaa", "Do the thing.", brief_of(default + 1))
        self.spawn("bbb", "Do the thing.", brief_of(default - 1))
        rows = self.rows()
        self.assertIs(rows["aaa"]["return_over_budget"], True)
        self.assertIs(rows["bbb"]["return_over_budget"], False)

    def test_an_agent_whose_own_definition_carries_the_cap_is_left_unmeasured(self):
        row = self.row(brief_of(900), brief="Do the thing.", agent_type="gatherer")
        self.assertIsNone(row["return_over_budget"])
        self.assertEqual(row["return_path"], "none")

    def test_the_cap_is_the_number_beside_the_word_words(self):
        self.assertEqual(usage_log.return_cap("cap each of the 3 sections at 200 words", ""), 200)
        self.assertEqual(usage_log.return_cap("a word cap of 300 applies", ""), 300)
        row = self.row(brief_of(210), brief="Cap each of the 3 sections at 200 words.")
        self.assertIs(row["return_over_budget"], True)

    def test_a_brief_that_was_empty_is_measured_against_no_cap(self):
        # `brief-guard` appends nothing to an empty prompt, so there is no default to apply.
        self.assertIsNone(usage_log.return_cap("", ""))
        self.assertIsNone(usage_log.return_cap("   ", "builder"))
        self.assertIsNone(self.row(brief_of(900), brief="")["return_over_budget"])

    def test_the_exemption_follows_the_type_the_call_asked_for(self):
        # The spawn asked for a capped agent and was rerouted; the brief it carried is the one
        # the hook read, so the reroute must not put it under a cap it never had.
        self.spawn("aaa", "Do the thing.", brief_of(900), "gatherer")
        rows = self.rows(ran_as="worker-b")
        self.assertEqual(rows["aaa"]["requested_type"], "gatherer")
        self.assertIsNone(rows["aaa"]["return_over_budget"])

    def test_punctuation_is_not_counted_as_words(self):
        self.assertEqual(usage_log.word_count("one - two \u00b7 three\n```\nfour\n```"), 4)
        row = self.row("- a\n- b\n- c\n", brief="Return at most 3 words.")
        self.assertIs(row["return_over_budget"], False)

    def test_a_cap_the_detector_does_not_read_as_one_leaves_the_field_unmeasured(self):
        # Not a word cap and not the default either: a capped agent whose brief says nothing.
        self.assertIsNone(usage_log.return_cap("keep it short", "gatherer"))
        self.assertEqual(usage_log.return_cap("keep it short", "builder"), 400)
        self.assertEqual(usage_log.return_cap("a 250-word cap applies", "builder"), 250)


class UnmeasuredTests(Transcript):
    def test_a_row_whose_parent_call_is_not_in_the_transcript_keeps_both_fields_null(self):
        self.spawn("aaa", "Return at most 400 words.", "Fixed. See notes/dimension-a.md.")
        self.assertEqual(self.rows()["aaa"]["return_path"], "resolvable")
        # The join is the tool use id; without it the row is the same row, measured for nothing.
        for field in usage_log.RETURN_KEYS:
            self.assertIsNone(self.rows(join=False)["aaa"][field], field)

    def test_an_empty_return_measures_nothing(self):
        row = self.row("   ")
        for field in usage_log.RETURN_KEYS:
            self.assertIsNone(row[field], field)

    def test_a_return_the_scan_only_kept_the_head_of_is_named_truncated(self):
        oversized = ("word " * 40) + ("x" * usage_log.MAX_RESULT_TEXT)
        row = self.row(oversized)
        self.assertEqual(row["return_measured"], "truncated")
        for field in usage_log.RETURN_KEYS:
            self.assertIsNone(row[field], field)

    def test_a_return_inside_the_kept_size_is_measured_and_not_named(self):
        row = self.row("Fixed. See notes/dimension-a.md.")
        self.assertIsNone(row["return_measured"])
        self.assertEqual(row["return_path"], "resolvable")

    def test_a_subagent_row_still_holds_no_text(self):
        row = self.row("Fixed. See notes/dimension-a.md.")
        self.assertEqual(set(row) & {"prompt", "brief", "return", "text", "return_text"}, set())

    def test_a_codex_subagent_row_declares_both_fields_uncovered(self):
        row = usage_log.scan(FIXTURES / "subagent-depth-1.jsonl")
        self.assertEqual(row["kind"], "subagent")
        for field in usage_log.RETURN_KEYS:
            self.assertIsNone(row[field], field)

    def test_the_codex_capabilities_file_names_the_gap(self):
        limits = json.loads((REPO / "adapters" / "codex" / "capabilities.json").read_text())
        named = [line for line in limits["limitations"] if "return_path" in line]
        self.assertEqual(len(named), 1, limits["limitations"])
        self.assertIn("return_over_budget", named[0])


class ReportTests(unittest.TestCase):
    """`usage --by role`: the two shares, over the runs that carry a measurement."""

    def setUp(self):
        # `say` honours HARNESS_QUIET, and a suite run whole reaches here with it still set.
        quiet = os.environ.pop("HARNESS_QUIET", None)
        if quiet is not None:
            self.addCleanup(os.environ.__setitem__, "HARNESS_QUIET", quiet)

    def report(self, rows):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(harness.role_report(rows, 30, {}), 0)
        return buf.getvalue()

    @staticmethod
    def row(**fields):
        base = {"kind": "subagent", "agent_type": "builder", "output": 10, "tool_calls": 2,
                "return_path": None, "return_over_budget": None}
        base.update(fields)
        return base

    def line(self, rows, role="builder"):
        for line in self.report(rows).splitlines():
            if line.startswith(role):
                return line
        self.fail("no line for " + role)

    def cells(self, rows, role="builder"):
        """`(path, over)` as the report printed them, by position on the role's line."""
        fields = self.line(rows, role).split()
        return fields[10], fields[11]

    def test_the_path_share_is_taken_over_the_returns_that_named_a_path(self):
        rows = [self.row(return_path="resolvable"), self.row(return_path="unresolvable"),
                self.row(return_path="none"), self.row()]
        self.assertEqual(self.cells(rows)[0], "50%")

    def test_a_role_whose_returns_all_named_no_path_prints_a_dash_not_a_zero(self):
        rows = [self.row(return_path="none"), self.row(return_path="none")]
        self.assertEqual(self.cells(rows)[0], "-")

    def test_the_over_share_is_taken_over_the_returns_measured_against_a_cap(self):
        rows = [self.row(return_over_budget=True), self.row(return_over_budget=False),
                self.row()]
        self.assertEqual(self.cells(rows)[1], "50%")

    def test_a_role_with_no_measured_return_prints_a_dash_in_both_cells(self):
        self.assertEqual(self.cells([self.row(), self.row()]), ("-", "-"))

    def test_the_header_names_both_columns(self):
        head = self.report([self.row()]).splitlines()[0]
        self.assertIn("path", head)
        self.assertIn("over", head)


class CandidateTests(unittest.TestCase):
    """The path matcher, on the forms a return writes a path in."""

    def test_every_form_yields_the_same_token(self):
        for text in ("see `notes/a.md` for detail", "see notes/a.md.", "```\nnotes/a.md\n```",
                     "[the digest](notes/a.md)", "wrote notes/a.md, then stopped"):
            self.assertIn("notes/a.md", usage_log.path_candidates(text), text)

    def test_a_bare_word_is_never_a_path(self):
        self.assertEqual(usage_log.path_candidates("fixed the parser and ran the suite"), [])

    def test_prose_joined_by_a_slash_is_never_a_path(self):
        for prose in ("pass/fail", "and/or", "24/7", "3/4", "2026/09/22", "they/them"):
            self.assertEqual(usage_log.path_candidates(prose), [], prose)

    def test_a_root_a_relative_prefix_or_an_extension_makes_one(self):
        for text in ("/etc/hosts", "./notes/a", "../notes/a", "~/notes/a", "notes/a.md"):
            self.assertEqual(len(usage_log.path_candidates(text)), 1, text)

    def test_quoted_text_is_taken_at_its_word(self):
        self.assertEqual(usage_log.path_candidates("wrote `notes/a` there"), ["notes/a"])

    def test_a_leading_dot_survives_the_trim(self):
        self.assertEqual(usage_log.path_candidates("see ./notes/a.md."), ["./notes/a.md"])

    def test_a_url_contributes_nothing(self):
        self.assertEqual(usage_log.path_candidates("https://example.com/notes/a.md"), [])

    def test_the_candidate_list_is_bounded(self):
        text = " ".join("dir%d/file.md" % i for i in range(usage_log.MAX_CANDIDATES + 20))
        self.assertEqual(len(usage_log.path_candidates(text)), usage_log.MAX_CANDIDATES)

    def test_a_repeated_path_is_one_candidate(self):
        self.assertEqual(usage_log.path_candidates("a/b.md and a/b.md again"), ["a/b.md"])

    def test_the_scratchpad_is_a_root_and_a_missing_directory_is_not(self):
        roots = usage_log.return_roots(os.path.join(tempfile.gettempdir(), "no-such-dir-416"),
                                       "")
        self.assertEqual(roots, [os.path.realpath(tempfile.gettempdir())])


if __name__ == "__main__":
    unittest.main()
