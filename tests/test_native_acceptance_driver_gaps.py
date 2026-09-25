# SPDX-License-Identifier: MIT
"""The case drivers observe each clause of the procedure they cite, or the procedure narrows it.

A qualification assessment named seven places where a driver read something weaker than its
procedure step asked for (#742): unchanged roles compared by content rather than by link, a brief
checked to contain the budget sentence rather than to end with it, the missing-worker-state rule
never exercised, the harness's own `PostToolUse` entry never shown firing, drift read only at
uninstall, and two claims (a multi-file patch, the auto posture) wider than any run shows. No
test here launches a client.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in
from test_native_acceptance_cli_contract import disposable_home
from test_native_acceptance_hook_composition import FakeHome, SESSION
from test_native_acceptance_spawn_confinement import SpawnConfinementCaseTests, WORKER
from harness_core import lifecycle

PROCEDURE = " ".join((REPO / "docs" / "compatibility.md").read_text().split())


def step(number):
    """One numbered step of the qualification procedure, whitespace-normalized."""
    start = PROCEDURE.index(" %s. " % number)
    end = PROCEDURE.index(" %s. " % (number + 1), start) if number < 9 else \
        PROCEDURE.index("Store a redacted", start)
    return PROCEDURE[start:end]


def hook_context(content, hook="PostToolUse:Write"):
    """The transcript record Claude Code writes for a hook's additional context."""
    return {"type": "attachment", "attachment": {
        "type": "hook_additional_context", "hookName": hook, "content": [content]}}


class RoleLinkTests(unittest.TestCase):
    """Step 8: every role the variant does not change keeps its link."""

    TARGET = "/checkout/claude/agents/"

    def reading(self, **roles):
        return {name + ".md": value for name, value in roles.items()}

    def test_a_kept_link_and_a_rewritten_role_pass(self):
        before = self.reading(gatherer=(self.TARGET + "gatherer.md", "g"), worker_a=(None, "a1"))
        after = self.reading(gatherer=(self.TARGET + "gatherer.md", "g"), worker_a=(None, "a2"))
        self.assertEqual(MODULE.link_verdict(before, after), (["worker_a.md"], ["gatherer.md"]))

    def test_a_link_replaced_by_an_identical_copy_fails(self):
        before = self.reading(gatherer=(self.TARGET + "gatherer.md", "g"),
                              reviewer=(self.TARGET + "reviewer.md", "r"), worker_a=(None, "a1"))
        after = self.reading(gatherer=(None, "g"), reviewer=(self.TARGET + "reviewer.md", "r"),
                             worker_a=(None, "a2"))
        with self.assertRaises(AssertionError) as caught:
            MODULE.link_verdict(before, after)
        self.assertIn("did not keep its link: gatherer.md (its link became a copy)",
                      str(caught.exception))

    def test_a_retargeted_link_fails(self):
        before = self.reading(gatherer=(self.TARGET + "gatherer.md", "g"), worker_a=(None, "a1"))
        after = self.reading(gatherer=("/elsewhere/gatherer.md", "g"), worker_a=(None, "a2"))
        with self.assertRaises(AssertionError) as caught:
            MODULE.link_verdict(before, after)
        self.assertIn("its link was retargeted", str(caught.exception))

    def test_no_kept_role_being_a_link_observes_no_link_kept(self):
        before = self.reading(gatherer=(None, "g"), worker_a=(None, "a1"))
        after = self.reading(gatherer=(None, "g"), worker_a=(None, "a2"))
        with self.assertRaises(AssertionError) as caught:
            MODULE.link_verdict(before, after)
        self.assertIn("no role was observed keeping its link", str(caught.exception))

    def test_a_switch_that_rewrote_nothing_fails(self):
        before = self.reading(gatherer=(self.TARGET + "gatherer.md", "g"))
        with self.assertRaises(AssertionError) as caught:
            MODULE.link_verdict(before, dict(before))
        self.assertIn("rewrote 0 of 1 roles", str(caught.exception))

    def test_role_links_reads_a_link_as_its_target_and_a_file_as_none(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("linked\n")
            (root / "agents").mkdir()
            (root / "agents" / "linked.md").symlink_to(root / "source.md")
            (root / "agents" / "copy.md").write_text("linked\n")
            self.assertEqual(MODULE.role_links(root / "agents"), {
                "copy.md": (None, "linked\n"),
                "linked.md": (str(root / "source.md"), "linked\n")})

    def test_the_real_sync_keeps_every_unchanged_role_linked_across_the_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            home = disposable_home(directory)
            home.primitives = home.root / "primitives"
            home.seed(stances={"cost": "balanced", "delegation": "tiered"})
            home.harness("sync")
            before = MODULE.role_links(home.client_dir / "agents")
            data = home.config()
            data["stances"]["cost"] = "frugal"
            home.write_config(data)
            home.harness("sync")
            after = MODULE.role_links(home.client_dir / "agents")
            rewritten, kept = MODULE.link_verdict(before, after)
            self.assertIn("worker-a.md", rewritten)
            self.assertTrue(all(after[name][0] for name in kept if before[name][0]))


class BudgetEndingTests(unittest.TestCase):
    """Step 8: the brief ends with the row's budget sentence."""

    SENTENCE = ("\n\nExpected spend: about 12,000 output tokens and about 12 tool calls. Past "
                "that, finish if you are close; otherwise return what you have and say why.")

    def test_a_brief_ending_with_the_sentence_passes(self):
        self.assertEqual(MODULE.budget_ending("Reply DONE." + self.SENTENCE + "\n", self.SENTENCE),
                         self.SENTENCE.strip())

    def test_a_sentence_followed_by_more_text_fails(self):
        with self.assertRaises(AssertionError) as caught:
            MODULE.budget_ending("Reply DONE." + self.SENTENCE + "\n\nAnd one more thing.",
                                 self.SENTENCE)
        self.assertIn("does not end with the row's", str(caught.exception))

    def test_another_rows_figures_fail(self):
        with self.assertRaises(AssertionError):
            MODULE.budget_ending("Reply DONE." + self.SENTENCE.replace("12,000", "9,000"),
                                 self.SENTENCE)

    def test_no_sentence_and_no_priced_row_each_fail(self):
        with self.assertRaises(AssertionError) as caught:
            MODULE.budget_ending("Reply DONE.", self.SENTENCE)
        self.assertIn("carries no budget sentence", str(caught.exception))
        with self.assertRaises(AssertionError) as caught:
            MODULE.budget_ending("Reply DONE." + self.SENTENCE, None)
        self.assertIn("prices nothing", str(caught.exception))

    def test_the_frugal_default_band_row_prices_a_sentence_for_the_case_to_expect(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            home.seed(stances={"cost": "frugal"})
            posture = MODULE.hook_posture()
            sentence = posture.budget_sentence(
                posture.row_for(posture.cost_table(env=home.env()), "worker-a"))
        self.assertTrue(sentence and "Expected spend: about" in sentence)


class MissingWorkerStateTests(unittest.TestCase):
    """Step 9: a routed run with no worker state is judged a failed case, on the live output."""

    setUp = SpawnConfinementCaseTests.setUp

    def test_the_passing_case_records_that_the_moved_aside_run_failed(self):
        verdict = MODULE.case_spawn_confinement(self.home)
        self.assertIn("with that run's state directory moved aside, the same printed record was "
                      "judged a failed case", verdict)
        workers = self.home.root / ".local" / "state" / "agent-harness" / "workers"
        self.assertEqual([path.name for path in workers.iterdir()], [WORKER])

    def test_a_judgement_that_ignores_the_missing_state_fails_the_case(self):
        real, calls = MODULE.worker_state, []

        def lenient(home, printed, role):
            calls.append(role)
            return real(home, printed, role) if len(calls) == 1 else (None, None)

        with patch.object(MODULE, "worker_state", side_effect=lenient):
            with self.assertRaises(AssertionError) as caught:
                MODULE.case_spawn_confinement(self.home)
        self.assertIn("with its worker state moved aside, the routed", str(caught.exception))
        self.assertEqual(len(calls), 2)

    def test_the_state_directory_is_restored_after_the_rejudgement(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            run_dir = home.root / ".local" / "state" / "agent-harness" / "workers" / "abc"
            run_dir.mkdir(parents=True)
            (run_dir / "status.json").write_text("{}")
            printed = json.dumps({"id": "abc", "status": "completed"})
            self.assertEqual(MODULE.worker_state(home, printed, "reviewer")[1], run_dir)
            reason = MODULE.missing_state_fails(home, printed, "reviewer", run_dir)
            self.assertIn("wrote no isolated worker state", reason)
            self.assertTrue((run_dir / "status.json").is_file())
            self.assertFalse(run_dir.with_name("abc.aside").exists())


class HarnessPostToolUseTests(unittest.TestCase):
    """Step 4: the harness's own PostToolUse entry is seen firing on the write turn."""

    def test_the_real_coordinator_flags_the_write_the_patch_prompt_asks_for(self):
        self.assertIn(MODULE.FLAGGED_LINE, MODULE.PATCH_PROMPT)
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"HOME": directory, "PATH": os.environ["PATH"]},
                            clear=True):
                answer = lifecycle.dispatch("claude-code", {
                    "hook_event_name": "PostToolUse", "session_id": SESSION, "cwd": directory,
                    "tool_name": "Write",
                    "tool_input": {"file_path": directory + "/beta.txt",
                                   "content": MODULE.FLAGGED_LINE + "\n"},
                    "tool_response": {"type": "create", "filePath": directory + "/beta.txt",
                                      "content": MODULE.FLAGGED_LINE + "\n"}})
        context = answer["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith(MODULE.HARNESS_NOTICE), context)
        self.assertEqual(MODULE.harness_post_notice(json.dumps(hook_context(context))), context)

    def test_the_notice_is_read_only_from_a_write_hook_context_record(self):
        notice = MODULE.HARNESS_NOTICE + "settings-json. Treat it.]"
        self.assertEqual(MODULE.harness_post_notice('{"type": "user"}'), "")
        quoted = json.dumps({"type": "user", "message": {"content": notice}})
        self.assertEqual(MODULE.harness_post_notice(quoted), "")
        bash = json.dumps(hook_context(notice, hook="PostToolUse:Bash"))
        self.assertEqual(MODULE.harness_post_notice(bash), "")
        success = json.dumps({"type": "attachment", "attachment": {
            "type": "hook_success", "hookName": "PostToolUse:Write", "stdout": notice}})
        self.assertEqual(MODULE.harness_post_notice(success), "")
        text = "\n".join(["not json", quoted, json.dumps(hook_context(notice + " tail"))])
        self.assertEqual(MODULE.harness_post_notice(text), notice)

    def run_case(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            home = FakeHome(directory, **kwargs)
            try:
                return MODULE.case_hook_composition(home)
            finally:
                MODULE.shutil.rmtree(str(home.project / ".git"), ignore_errors=True)

    def test_the_passing_case_quotes_the_notice_and_states_the_patch_reading(self):
        text = self.run_case()
        self.assertIn("The harness's own PostToolUse entry fired in the same turn", text)
        self.assertIn(MODULE.HARNESS_NOTICE, text)
        self.assertIn("the multi-file patch is this one turn's two file-tool writes", text)

    def test_a_write_turn_with_no_harness_notice_is_unverified(self):
        with self.assertRaises(MODULE.Unverified) as caught:
            self.run_case(notice=False)
        self.assertIn("so that entry was not observed firing", str(caught.exception))


class DriftTests(unittest.TestCase):
    """Step 7: a hand edit is drift before it is anything uninstall preserves."""

    def test_the_diff_line_for_the_key_is_found_and_another_key_is_not(self):
        output = "- live-only change: settings.outputStyle = 'Explanatory' (upstream it or re-sync)\n"
        self.assertEqual(MODULE.drift_named(output, "outputStyle"),
                         "live-only change: settings.outputStyle = 'Explanatory' (upstream it or "
                         "re-sync)")
        self.assertEqual(MODULE.drift_named(output, "output"), "")
        self.assertEqual(MODULE.drift_named("no drift\n", "outputStyle"), "")

    def test_a_diff_that_exits_0_or_names_nothing_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            for code, output in ((0, "no drift\n"), (1, "- missing link /x\n")):
                def harness(*args, **kwargs):
                    home.last_code = code
                    return output
                home.harness = harness
                with self.assertRaises(AssertionError) as caught:
                    MODULE.drift_verdict(home, "outputStyle")
                self.assertIn("without naming it as drift", str(caught.exception))

    def test_the_case_reads_the_drift_from_the_real_cli_before_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            home = disposable_home(directory)
            with patch.object(MODULE.Home, "session", return_value={"result": "PRESERVED\nNONE"}):
                note = MODULE.case_migration_uninstall(home)
        self.assertIn("harness diff, which had not named it before the edit, exited 1 reporting "
                      "\"live-only change: settings.outputStyle = 'Explanatory'", note)
        self.assertLess(note.index("harness diff"), note.index("harness uninstall exited 2"))


class ProcedureTests(unittest.TestCase):
    """Where a driver cannot observe a clause, the procedure states the narrower claim."""

    def test_step_3_claims_the_auto_posture_narrowly(self):
        text = step(3)
        for needle in ("auto posture is claimed narrowly", "auto-mode classifier",
                       "does not ask it to refuse anything"):
            self.assertIn(needle, text)

    def test_the_auto_observation_carries_the_same_limit(self):
        self.assertIn("no probe here asks it to refuse anything", MODULE.AUTO_LIMIT)
        from test_permission_controls_case import HAPPY, run_case
        self.assertTrue(run_case(HAPPY).rstrip(".").endswith(MODULE.AUTO_LIMIT))

    def test_step_4_reads_both_hooks_from_the_turn_and_narrows_the_patch(self):
        text = step(4)
        for needle in ("harness's own `PostToolUse` entry", "no multi-file patch tool",
                       "one turn writing each file with its file tool"):
            self.assertIn(needle, text)

    def test_step_7_reads_drift_before_uninstall(self):
        self.assertIn("reported as drift by `harness diff` while the harness is still installed",
                      step(7))

    def test_step_9_exercises_the_missing_state_rule(self):
        self.assertIn("judging the routed run again with its worker state moved aside", step(9))

    def test_each_changed_case_says_what_it_now_reads(self):
        self.assertIn("each role's link", MODULE.CASES["cost-posture"][1])
        self.assertIn("the end of its brief", MODULE.CASES["cost-posture"][1])
        self.assertIn("harness PostToolUse notice", MODULE.CASES["hook-composition"][1])
        self.assertIn("state moved aside", MODULE.CASES["spawn-confinement"][1])
        self.assertIn("harness diff", MODULE.CASES["migration-uninstall"][1])


if __name__ == "__main__":
    unittest.main()
