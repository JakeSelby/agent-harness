# SPDX-License-Identifier: MIT
"""An isolated role worker follows the selected cost variant, as a rendered definition does.

The constrained roles are denied as native spawns and always run through `harness role run`, so
until this landed neither the posture nor the soft budget reached exactly the roles that carry
measured budgets: under `frugal` a `gatherer` worker ran on its own class while the same sync
rendered that role one class lower. These tests hold the two paths equal — the worker's binding
is compared with what the sync renderer produces, never with a literal — and hold the null case,
where a variant that prices nothing leaves a worker exactly as it was.

Run: python3 -m unittest discover tests
"""
import copy
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

from harness_core import catalog, workers  # noqa: E402

EFFORT_KEYS = {"claude-code": "effort", "codex": "model_reasoning_effort"}
BRIEF = "Find every caller of this function."


def rendered(cfg, runtime, role):
    """What the sync path renders this role's native definition with: `{model, effort}`.

    Read off the projection the renderer writes, through the functions `cmd_sync` calls, so a
    change to the precedence moves both sides of every comparison below or neither.
    """
    overrides = harness.agent_overrides(cfg, harness.cost_table(cfg), runtime, role)
    text = catalog.role_projection(REPO, runtime, REPO / "primitives" / "roles" / (role + ".md"),
                                   overrides, cfg.get("tiers", {}).get(runtime))
    if runtime == "claude-code":
        fields = {k.strip(): v.strip() for k, _, v in
                  (line.partition(":") for line in text.split("---", 2)[1].strip().splitlines())}
    else:
        fields = {k.strip(): json.loads(v.strip()) for k, _, v in
                  (line.partition(" = ") for line in text.splitlines() if " = " in line)}
    return {"model": fields.get("model"), "effort": fields.get(EFFORT_KEYS[runtime])}


def resolved(cfg, runtime, role, model=None, prompt=BRIEF):
    return workers.resolution(REPO, cfg, runtime, role, model, prompt)


def binding_of(ready, runtime):
    return {"model": ready["bindings"].get("model"),
            "effort": ready["bindings"].get(EFFORT_KEYS[runtime])}


class PostureCase(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))

    def variant(self, name, **stances):
        cfg = copy.deepcopy(self.cfg)
        cfg["stances"].update(dict(stances, cost=name))
        return cfg


class WorkerFollowsTheVariant(PostureCase):
    def test_a_frugal_gatherer_resolves_what_the_renderer_resolves(self):
        cfg = self.variant("frugal")
        for runtime in workers.RUNTIMES:
            with self.subTest(runtime=runtime):
                ready = resolved(cfg, runtime, "gatherer")
                self.assertEqual(binding_of(ready, runtime), rendered(cfg, runtime, "gatherer"))
                # The defect: the role's own class is `strong`, and the row moves it down one.
                self.assertNotEqual(binding_of(ready, runtime),
                                    binding_of(resolved(self.cfg, runtime, "gatherer"), runtime))
                self.assertEqual(ready["posture"]["class"], "standard")

    def test_every_constrained_role_matches_the_renderer_under_every_shipped_variant(self):
        roles = [p.stem for p in sorted((REPO / "primitives" / "roles").glob("*.md"))
                 if catalog.role_contract(REPO, p.stem)[0]["authority"] != "workspace-write"]
        for path in sorted((REPO / "primitives" / "stances" / "cost").glob("*.json")):
            cfg = self.variant(path.stem)
            for runtime in workers.RUNTIMES:
                for role in roles:
                    with self.subTest(variant=path.stem, runtime=runtime, role=role):
                        self.assertEqual(binding_of(resolved(cfg, runtime, role), runtime),
                                         rendered(cfg, runtime, role))

    def test_a_fixed_role_is_unmoved_by_any_variant_and_still_priced(self):
        for path in sorted((REPO / "primitives" / "stances" / "cost").glob("*.json")):
            cfg = self.variant(path.stem)
            with self.subTest(variant=path.stem):
                ready = resolved(cfg, "claude-code", "reviewer")
                self.assertEqual(binding_of(ready, "claude-code"),
                                 binding_of(resolved(self.cfg, "claude-code", "reviewer"), "claude-code"))
                self.assertEqual(ready["posture"]["class_source"], "role")
                self.assertEqual(ready["posture"]["effort_source"], "role")
                self.assertIn("Expected spend:", ready["budget_sentence"])

    def test_a_user_role_binding_beats_the_row_and_a_model_flag_beats_everything(self):
        cfg = self.variant("frugal")
        cfg["role_bindings"] = {"codex": {"gatherer": {"model": "mine", "model_reasoning_effort": "high"}}}
        ready = resolved(cfg, "codex", "gatherer")
        self.assertEqual(binding_of(ready, "codex"), {"model": "mine", "effort": "high"})
        self.assertEqual(binding_of(ready, "codex"), rendered(cfg, "codex", "gatherer"))
        self.assertEqual(ready["posture"]["model_source"], "role-binding")
        self.assertEqual(ready["posture"]["effort_source"], "role-binding")
        flagged = resolved(cfg, "codex", "gatherer", model="from-the-command-line")
        self.assertEqual(flagged["bindings"]["model"], "from-the-command-line")
        self.assertEqual(flagged["posture"]["model_source"], "cli")

    def test_without_a_tiered_delegation_the_row_moves_effort_and_not_the_class(self):
        cfg = self.variant("frugal", delegation="session-model")
        ready = resolved(cfg, "claude-code", "gatherer")
        self.assertEqual(binding_of(ready, "claude-code"), rendered(cfg, "claude-code", "gatherer"))
        self.assertEqual(ready["bindings"]["model"],
                         resolved(self.cfg, "claude-code", "gatherer")["bindings"]["model"])
        self.assertEqual(ready["bindings"]["effort"], "low")
        self.assertEqual(ready["posture"]["class_source"], "role")
        self.assertEqual(ready["posture"]["effort_source"], "cost-row")

    def test_the_codex_worker_takes_its_own_effort_key(self):
        ready = resolved(self.variant("frugal"), "codex", "gatherer")
        self.assertEqual(ready["bindings"]["model_reasoning_effort"], "low")
        self.assertNotIn("effort", ready["bindings"])


class SessionSelectionTests(PostureCase):
    """The stance ladder a worker walks is the CLI's, so a session variable reaches it."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        env["HOME"] = self.tmp.name
        patcher = unittest.mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_session_scoped_cost_variant_reaches_the_worker(self):
        before = resolved(harness.load_config(), "claude-code", "gatherer")
        os.environ["HARNESS_STANCE_COST"] = "frugal"
        cfg = harness.load_config()
        after = resolved(cfg, "claude-code", "gatherer")
        self.assertNotEqual(after["bindings"]["model"], before["bindings"]["model"])
        self.assertEqual(binding_of(after, "claude-code"), rendered(cfg, "claude-code", "gatherer"))
        self.assertEqual(after["posture"]["cost_variant"], "frugal")

    def test_a_synced_definition_and_a_worker_agree_in_one_home(self):
        """The qualification case: one home, one config, the two paths compared end to end."""
        path = Path(self.tmp.name) / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(self.variant("frugal")), encoding="utf-8")
        os.environ["HARNESS_QUIET"] = "1"
        self.assertEqual(harness.cmd_sync(harness.argparse.Namespace(
            dry_run=False, adopt=False, adopt_codex=False, print_only=False)), 0)
        text = (Path(self.tmp.name) / ".claude" / "agents" / "gatherer.md").read_text(encoding="utf-8")
        fields = {k.strip(): v.strip() for k, _, v in
                  (line.partition(":") for line in text.split("---", 2)[1].strip().splitlines())}
        ready = resolved(harness.load_config(), "claude-code", "gatherer")
        self.assertEqual(binding_of(ready, "claude-code"),
                         {"model": fields["model"], "effort": fields["effort"]})


class NullVariantTests(PostureCase):
    """A variant that prices nothing, and a table that will not build, change nothing."""

    def custom(self, rows):
        root = Path(self.tmp.name) / "primitives" / "stances" / "cost"
        root.mkdir(parents=True, exist_ok=True)
        (root / "plain.md").write_text("# Cost stance: plain\n", encoding="utf-8")
        (root / "plain.json").write_text(
            json.dumps({"schema_version": 1, "extends": None, "rows": rows}), encoding="utf-8")
        cfg = self.variant("plain")
        cfg["primitive_roots"] = [str(Path(self.tmp.name) / "primitives")]
        return cfg

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def baseline(self, runtime, role):
        fields, _ = catalog.role_contract(REPO, role)
        return catalog.role_binding(REPO, runtime, fields)

    def test_a_variant_with_no_row_for_the_role_leaves_it_alone(self):
        cfg = self.custom({"builder": {"class": "light"}})
        for runtime in workers.RUNTIMES:
            with self.subTest(runtime=runtime):
                ready = resolved(cfg, runtime, "gatherer")
                self.assertEqual(ready["bindings"], self.baseline(runtime, "gatherer"))
                self.assertIsNone(ready["budget_sentence"])
                self.assertEqual(ready["posture"]["class_source"], "role")
                self.assertEqual(ready["posture"]["model_source"], "role")
                self.assertEqual(ready["posture"]["effort_source"], "role")

    def test_a_table_that_cannot_be_built_leaves_the_worker_as_it_is(self):
        cfg = self.variant("frugal")
        module = catalog.posture_module(REPO)
        with unittest.mock.patch.object(module, "table_for",
                                        side_effect=RuntimeError("no table")):
            ready = resolved(cfg, "claude-code", "gatherer")
        self.assertEqual(ready["bindings"], self.baseline("claude-code", "gatherer"))
        self.assertIsNone(ready["budget_sentence"])
        self.assertIsNone(ready["posture"]["cost_variant"])

    def test_a_checkout_with_no_resolver_prices_and_moves_nothing(self):
        cfg = self.variant("frugal")
        with unittest.mock.patch.object(catalog, "posture_module", return_value=None):
            ready = resolved(cfg, "codex", "gatherer")
        self.assertEqual(ready["bindings"], self.baseline("codex", "gatherer"))
        self.assertIsNone(ready["budget_sentence"])
        self.assertNotIn("budget", ready["posture"])


class BudgetSentenceTests(PostureCase):
    def test_the_brief_carries_the_rows_figures_once(self):
        sentence = resolved(self.cfg, "codex", "gatherer")["budget_sentence"]
        self.assertEqual(sentence, "\n\nExpected spend: about 8,500 output tokens and about 15 "
                                   "tool calls. Past that, finish if you are close; otherwise "
                                   "return what you have and say why.")
        self.assertEqual(resolved(self.cfg, "codex", "gatherer", prompt=BRIEF + sentence
                                  )["budget_sentence"], None)

    def test_the_variants_multiplier_moves_the_figures(self):
        ready = resolved(self.variant("frugal"), "codex", "gatherer")
        self.assertIn("about 5,100 output tokens and about 9 tool calls", ready["budget_sentence"])
        self.assertEqual(ready["posture"]["budget"],
                         {"budget_output_tokens": 5100, "budget_tool_calls": 9})

    def test_a_brief_that_prices_itself_is_left_alone(self):
        for own in ("Stay under 20 tool calls.", "Spend at most 9,000 output tokens."):
            with self.subTest(brief=own):
                self.assertIsNone(resolved(self.cfg, "codex", "gatherer", prompt=own)["budget_sentence"])

    def test_an_unbudgeted_role_gets_no_sentence(self):
        # `planner` is priced at null in both units: a role the variant deliberately does not cap.
        ready = resolved(self.cfg, "claude-code", "planner")
        self.assertIsNone(ready["budget_sentence"])
        self.assertNotIn("budget", ready["posture"])

    def test_the_guard_and_the_worker_state_a_spend_through_one_function(self):
        guard = importlib.util.spec_from_file_location(
            "harness_brief_guard", str(REPO / "policy" / "hooks" / "brief-guard.py"))
        module = importlib.util.module_from_spec(guard)
        guard.loader.exec_module(module)
        for source in (module.sibling("posture"), catalog.posture_module(REPO)):
            self.assertEqual(Path(source.budget_sentence.__code__.co_filename),
                             (REPO / "policy" / "hooks" / "posture.py").resolve())
        self.assertFalse(hasattr(module, "budget_sentence"))


class StatusRecordTests(unittest.TestCase):
    """What a finished worker records, so qualification can see which variant priced it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.cfg = json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))
        self.cfg["stances"]["cost"] = "frugal"
        patcher = unittest.mock.patch.dict(
            os.environ, {"HOME": str(self.base / "user"), "PATH": os.environ["PATH"]}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_worker(self):
        def execute(command, prompt, env, cwd, run_dir, timeout):
            (run_dir / "stdout.log").write_text(prompt)
            Path(command[command.index("-o") + 1]).write_text("findings")
            return 0

        with unittest.mock.patch.object(workers.shutil, "which", return_value="/native/cli"), \
                unittest.mock.patch.object(workers.subprocess, "check_output", return_value="v"), \
                unittest.mock.patch.object(workers, "execute", side_effect=execute) as ran:
            record = workers.run(REPO, self.cfg, "codex", "gatherer", self.workspace,
                                 BRIEF, self.base / "state")
        return record, ran.call_args[0][1]

    def test_the_record_names_the_variant_the_sources_and_the_figures(self):
        record, _ = self.run_worker()
        self.assertEqual(record["status"], "completed", record)
        self.assertEqual(record["posture"], {
            "cost_variant": "frugal", "class": "standard", "class_source": "cost-row",
            "model_source": "cost-row", "effort_source": "cost-row",
            "budget": {"budget_output_tokens": 5100, "budget_tool_calls": 9}})
        tiers = json.loads((REPO / "adapters" / "codex" / "bindings.json").read_text())["tiers"]
        self.assertEqual(record["model"], tiers["standard"])
        self.assertEqual(record["effort"], "low")
        stored = json.loads((Path(record["result_path"]).parent / "status.json").read_text())
        self.assertEqual(stored["posture"], record["posture"])
        self.assertNotIn(BRIEF, json.dumps(stored))

    def test_the_brief_the_native_client_receives_carries_the_budget(self):
        _, prompt = self.run_worker()
        self.assertTrue(prompt.startswith(BRIEF))
        self.assertEqual(prompt.count("Expected spend:"), 1)
        self.assertIn("about 5,100 output tokens and about 9 tool calls", prompt)


if __name__ == "__main__":
    unittest.main()
