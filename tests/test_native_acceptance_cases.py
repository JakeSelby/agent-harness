# SPDX-License-Identifier: MIT
"""Every scripted acceptance case's readers, driven against recorded shapes instead of a client.

No test here launches a client, installs anything, or reaches the network. What is tested is the
part of each case that decides: how a merged settings table is read, what a stance link resolves
to, which review layers carry a role declaration, what a Codex event stream and rollout say, and
that a surface this runner has never been observed against cannot report a pass.

The Codex fixtures under `fixtures/qualification/codex/` are hand-authored to the shapes
`adapters/codex/worker.py` and `policy/hooks/usage-log.py` parse, with placeholder identifiers.
They are derived from those readers and from docs/usage.md, **not** recorded from a Codex run:
no Codex round has been driven through this runner, which is why every Codex verdict is
`unverified` until an operator confirms the home against a hand run.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from test_native_acceptance import MODULE
from test_native_acceptance_runner import home_in, stub_init

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "qualification"
CODEX = FIXTURES / "codex"
PARENT_THREAD = "00000000-0000-7000-8000-0000000000c1"
CHILD_THREAD = "00000000-0000-7000-8000-0000000000c2"
CLAUDE = "claude-code-cli-macos"
CODEX_CLIENT = "codex-cli-macos"


def codex_home():
    """A CodexHome whose configuration home is the fixture tree, with no client behind it."""
    home = MODULE.CodexHome.__new__(MODULE.CodexHome)
    home.root = CODEX
    home.client_dir = CODEX
    home.model = "cheapest"
    home.keep = True
    home.launched = 0
    return home


class RegistrationTests(unittest.TestCase):
    def test_every_required_case_is_now_scripted(self):
        required = MODULE.catalog()["required_cases"]
        self.assertEqual(sorted(MODULE.CASES), sorted(required))

    def test_no_plan_still_says_a_case_is_not_automated(self):
        for client in sorted(MODULE.CLIENTS):
            printed = MODULE.plan(client, MODULE.catalog()["required_cases"], "cheapest")
            self.assertNotIn(MODULE.NOT_AUTOMATED, printed)

    def test_each_case_describes_what_it_reads_rather_than_what_it_configures(self):
        for name, (function, how) in sorted(MODULE.CASES.items()):
            self.assertTrue(callable(function), name)
            self.assertTrue(how.strip() and not how.endswith("."), name)


class ClientSurfaceTests(unittest.TestCase):
    def test_a_codex_surface_names_its_own_configuration_home(self):
        self.assertEqual(MODULE.CLIENTS[CODEX_CLIENT]["home_var"], "CODEX_HOME")
        self.assertEqual(MODULE.HOMES["codex"], MODULE.CodexHome)

    def test_the_disposable_home_exports_whichever_variable_that_surface_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            home = home_in(directory)
            home.home_var = "CODEX_HOME"
            with patch.dict(MODULE.os.environ, {"PATH": "/usr/bin"}, clear=True):
                env = home.env()
        self.assertEqual(env["CODEX_HOME"], str(home.client_dir))
        self.assertNotIn("CLAUDE_CONFIG_DIR", env)

    def test_an_unobserved_surface_says_so_and_an_observed_one_does_not(self):
        self.assertIn("CODEX_HOME", MODULE.unobserved_note(CODEX_CLIENT, False))
        self.assertEqual(MODULE.unobserved_note(CODEX_CLIENT, True), "")
        self.assertEqual(MODULE.unobserved_note(CLAUDE, False), "")

    def test_an_unobserved_surface_cannot_report_a_pass(self):
        def case(home):
            return "the assertion held"

        with patch.dict(MODULE.CASES, {"installation": (case, "canned")}), \
                patch.object(MODULE.CodexHome, "__init__", stub_init), \
                patch.object(MODULE.CodexHome, "discard", lambda self: None, create=True):
            outcome = MODULE.probe(CODEX_CLIENT, "installation", "cheapest", False)
            confirmed = MODULE.probe(CODEX_CLIENT, "installation", "cheapest", False, True)
        self.assertEqual(outcome["result"], "unverified")
        self.assertIn("the assertion held", outcome["observation"])
        self.assertIn("not been confirmed", outcome["observation"])
        self.assertEqual(confirmed["result"], "passed")


class CodexStreamTests(unittest.TestCase):
    def setUp(self):
        self.events = MODULE.codex_events((CODEX / "exec-stream.jsonl").read_text())

    def test_the_stream_is_read_past_lines_that_are_not_events(self):
        self.assertEqual(len(self.events), 4)
        self.assertEqual(MODULE.codex_events("not json\n\n"), [])

    def test_the_last_thing_the_model_said_is_the_answer(self):
        self.assertEqual(MODULE.codex_answer(self.events), "PLAIN")

    def test_a_stream_that_said_nothing_is_read_as_nothing(self):
        self.assertEqual(MODULE.codex_answer([{"type": "thread.started"}]), "")

    def test_the_thread_id_comes_from_the_stream_itself(self):
        self.assertEqual(codex_home().thread_id(self.events), PARENT_THREAD)


class CodexRolloutTests(unittest.TestCase):
    def setUp(self):
        self.home = codex_home()

    def test_both_rollouts_are_found_under_the_configuration_home(self):
        self.assertEqual(len(self.home.rollouts()), 2)

    def test_the_thread_is_identified_by_its_own_first_session_meta(self):
        records = self.home.rollout_records(PARENT_THREAD)
        self.assertTrue(records)
        self.assertEqual(MODULE.rollout_thread(records), PARENT_THREAD)

    def test_a_top_level_thread_is_not_a_spawn_and_a_spawned_one_is(self):
        self.assertIsNone(MODULE.rollout_spawn(self.home.rollout_records(PARENT_THREAD)))
        spawn = MODULE.rollout_spawn(self.home.rollout_records(CHILD_THREAD))
        self.assertEqual(spawn["parent_thread_id"], PARENT_THREAD)

    def test_a_spawned_thread_is_read_as_its_parents_subagent(self):
        found = self.home.subagents(PARENT_THREAD)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0]["agentType"], "amber-fox")

    def test_a_thread_that_spawned_nothing_has_no_subagents(self):
        self.assertEqual(self.home.subagents(CHILD_THREAD), [])

    def test_an_unknown_thread_reads_as_nothing_observed(self):
        self.assertEqual(self.home.rollout_records("00000000-0000-7000-8000-00000000ffff"), [])
        self.assertEqual(self.home.orchestrator_text("00000000-0000-7000-8000-00000000ffff"), "")

    def test_the_orchestrator_text_carries_what_the_thread_said(self):
        self.assertIn("SPAWNED", self.home.orchestrator_text(PARENT_THREAD))


class RuntimeGapTests(unittest.TestCase):
    """A record one runtime never writes is a named gap, never an assertion that holds vacuously."""

    def test_claude_code_has_no_gap(self):
        self.assertEqual(MODULE.native_only(home_in("/tmp"), "a spawn"), "")

    def test_another_runtime_names_itself_and_what_was_not_read(self):
        home = home_in("/tmp")
        home.runtime = "codex"
        gap = MODULE.native_only(home, "a spawn's subagent transcript")
        self.assertIn("codex", gap)
        self.assertIn("subagent transcript", gap)


class HookCompositionReaderTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(
            (FIXTURES / "claude-code" / "merged-settings.json").read_text())

    def test_the_merged_table_holds_both_the_coordinator_and_the_user_entry(self):
        coordinator, user = MODULE.user_hook_entries(self.settings, "/tmp/probe/user-hook.py")
        self.assertTrue(coordinator)
        self.assertTrue(user)

    def test_a_dropped_user_entry_is_visible(self):
        self.settings["hooks"]["PostToolUse"] = self.settings["hooks"]["PostToolUse"][:1]
        self.assertEqual(MODULE.user_hook_entries(self.settings, "/tmp/probe/user-hook.py"),
                         (True, False))

    def test_a_settings_file_with_no_hooks_at_all_reads_as_neither(self):
        self.assertEqual(MODULE.user_hook_entries({}, "/tmp/probe/user-hook.py"), (False, False))


class StanceLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = home_in(self.tmp.name)
        self.directory = self.home.client_dir / "rules" / "harness-stances"
        self.directory.mkdir(parents=True)

    def test_a_resolved_link_reports_the_variant_it_points_at(self):
        variant = self.home.root / "tiered.md"
        variant.write_text("# tiered\n")
        os.symlink(str(variant), str(self.directory / "delegation.md"))
        self.assertEqual(MODULE.link_target(MODULE.stance_link(self.home, "delegation")),
                         "tiered.md")

    def test_a_file_that_is_not_a_link_reports_nothing_rather_than_guessing(self):
        (self.directory / "voice.md").write_text("# not a link\n")
        self.assertEqual(MODULE.link_target(MODULE.stance_link(self.home, "voice")), "")

    def test_an_absent_link_reports_nothing(self):
        self.assertEqual(MODULE.link_target(MODULE.stance_link(self.home, "cost")), "")


class BmadLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / "_bmad" / "custom").mkdir(parents=True)

    def layer(self, name, body):
        (self.repo / "_bmad" / "custom" / name).write_text(body)

    def test_every_applied_layer_declaring_a_role_is_found_with_its_roles(self):
        self.layer("bmad-code-review.user.toml",
                   'a = "harness-role: reviewer\\n..."\nb = "harness-role: spec-reviewer\\n..."\n')
        found = MODULE.layer_declarations(self.repo)
        self.assertEqual(found["bmad-code-review.user.toml"], {"reviewer", "spec-reviewer"})

    def test_a_checkout_with_no_declaration_reads_as_none(self):
        self.layer("bmad-build.user.toml", 'a = "no declaration here"\n')
        self.assertEqual(MODULE.layer_declarations(self.repo), {})

    def test_the_case_is_unverified_rather_than_skipped_without_a_checkout(self):
        with patch.dict(MODULE.os.environ, {MODULE.BMAD_ENV: ""}):
            self.assertIsNone(MODULE.bmad_checkout())


class ProvisionedRoundTests(unittest.TestCase):
    """The committed provisioning and driver scripts, read without running either end to end."""

    def setUp(self):
        self.provision = MODULE_FOR("qualification_provision")
        self.driver = MODULE_FOR("qualification_round")

    def test_the_round_exports_only_the_checkout_it_provisioned(self):
        self.assertEqual(self.provision.environment({"bmad": "/round/bmad"}),
                         {MODULE.BMAD_ENV: "/round/bmad"})
        self.assertEqual(self.provision.environment({"bmad": None}), {})

    def test_a_round_directory_inside_this_checkout_is_refused(self):
        with self.assertRaises(SystemExit):
            self.provision.main(["--out", str(REPO / "inside")])

    def test_the_bmad_installer_is_pinned_rather_than_floating(self):
        self.assertRegex(self.provision.BMAD_INSTALLER, r"@\d+\.\d+\.\d+$")

    def test_a_target_argv_names_the_frozen_clones_own_runner(self):
        argv = self.driver.target_argv("/round/clone", CLAUDE, "cheapest", "/round/out.json", True,
                                       {"execution_class": "standard",
                                        "assessment_class": "strong"})
        self.assertIn("/round/clone/scripts/native_acceptance.py", argv)
        self.assertIn("--home-confirmed", argv)

    def test_a_target_with_no_record_is_reported_rather_than_assumed_green(self):
        summary = self.driver.summarise({CLAUDE: {"cases": {}},
                                         CODEX_CLIENT: {"cases": {"installation": "unverified"}}})
        self.assertIn("no record", summary)
        self.assertIn("not installation", summary)

    def test_an_unknown_target_is_refused(self):
        with self.assertRaises(SystemExit):
            self.driver.main(["--round", "/round", "--targets", "no-such-client"])


def MODULE_FOR(name):
    """One of the committed round scripts, loaded the way the runner's own tests load theirs."""
    import importlib.util
    path = REPO / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
