# SPDX-License-Identifier: MIT
"""The soft budget a brief carries.

`brief-guard` states the row's expected spend in the brief, because a subagent cannot see the
cost variant that priced it. It is informational, so the guarantee these tests hold is the null
one: a variant that prices nothing produces exactly the bytes 0.10.0 produced, for every shape
of spawn, and so does a table that will not build.

Run: python3 -m unittest discover tests
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "claude" / "hooks" / "brief-guard.py"
TIER = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
AGENTS = REPO / "claude" / "agents"
# The session these fixtures spawn from; a reroute needs a record saying it can resolve the type.
SESSION = "fixture-session"

# What `brief-guard` printed before budgets existed: the cap on a brief that states none, and
# silence for everything else. A variant with no budgets must still print exactly this.
BOUND = ("\n\nReturn at most 400 words: a one-line verdict first, then only what changes a "
         "decision. Write anything longer to a file and return its path, not its contents.")
CAP_MESSAGE = "harness:brief-guard: the brief stated no return bound, so a 400-word cap was added"


def capped(tool_input):
    updated = dict(tool_input, prompt=tool_input["prompt"] + BOUND)
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated},
            "systemMessage": CAP_MESSAGE}


NULL_VARIANT_FIXTURES = (
    ("bare", {"prompt": "x"}, capped({"prompt": "x"})),
    ("general-purpose", {"prompt": "x", "subagent_type": "general-purpose"},
     capped({"prompt": "x", "subagent_type": "general-purpose"})),
    ("named capped role", {"prompt": "x", "subagent_type": "gatherer"}, None),
    ("named uncapped role", {"prompt": "x", "subagent_type": "builder"},
     capped({"prompt": "x", "subagent_type": "builder"})),
    ("brief with its own cap", {"prompt": "Reply in at most 50 words."}, None),
)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookCase(unittest.TestCase):
    """A disposable home the hooks resolve their posture from."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text(json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5"}}) + "\n")
        self.config()

    def config(self, delegation="tiered", **extra):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(
            dict({"stances": {"delegation": delegation}}, **extra)))

    def install_workers(self):
        d = self.home / ".claude" / "agents"
        d.mkdir(parents=True, exist_ok=True)
        names = ("worker-a", "worker-b", "worker-c")
        for name in names:
            (d / (name + ".md")).write_text((AGENTS / (name + ".md")).read_text(encoding="utf-8"))
        # The record the SessionStart policy writes: a reroute needs one naming the worker.
        sessions = self.home / ".local" / "state" / "agent-harness" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / (SESSION + ".json")).write_text(json.dumps({"agents": list(names), "at": 0}))

    def variant(self, name, sidecar):
        """Select a cost variant of the test's own, on a primitive root under the temp home."""
        root = self.home / "primitives" / "stances" / "cost"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(sidecar))
        self.config(primitive_roots=[str(self.home / "primitives")],
                    stances={"delegation": "tiered", "cost": name})

    def env(self, extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        env["HOME"] = str(self.home)
        env.update(extra or {})
        return env

    def run_hook(self, hook, tool_input, env=None, cwd=None, transcript=True):
        payload = {"tool_name": "Agent", "tool_input": tool_input, "session_id": SESSION}
        if transcript:
            payload["transcript_path"] = str(self.transcript)
        if cwd:
            payload["cwd"] = cwd
        out = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                             capture_output=True, text=True, env=self.env(env))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def guard(self, tool_input, **kwargs):
        return self.run_hook(GUARD, tool_input, **kwargs)

    def prompt(self, tool_input, **kwargs):
        out = self.guard(tool_input, **kwargs)
        self.assertIsNotNone(out, "the hook should have rewritten this brief")
        return out["hookSpecificOutput"]["updatedInput"]["prompt"]


class BudgetSentenceTests(HookCase):
    def test_a_named_role_carries_both_halves_of_its_row(self):
        prompt = self.prompt({"prompt": "Read it.", "subagent_type": "gatherer"})
        self.assertIn("Expected spend: about 8,500 output tokens and about 15 tool calls. "
                      "Past that, finish if you are close; otherwise return what you have and "
                      "say why.", prompt)
        self.assertTrue(prompt.startswith("Read it."))

    def test_a_row_with_only_tokens_states_only_tokens(self):
        self.variant("tokens-only", {"schema_version": 1, "extends": "balanced", "rows": {
            "gatherer": {"budget_output_tokens": 1200, "budget_tool_calls": None}}})
        prompt = self.prompt({"prompt": "x", "subagent_type": "gatherer"})
        self.assertIn("Expected spend: about 1,200 output tokens. Past that,", prompt)
        self.assertNotIn("tool calls", prompt)

    def test_a_row_with_only_calls_states_only_calls(self):
        self.variant("calls-only", {"schema_version": 1, "extends": "balanced", "rows": {
            "gatherer": {"budget_output_tokens": None, "budget_tool_calls": 7}}})
        prompt = self.prompt({"prompt": "x", "subagent_type": "gatherer"})
        self.assertIn("Expected spend: about 7 tool calls. Past that,", prompt)
        self.assertNotIn("output tokens", prompt)

    def test_an_unbudgeted_role_gets_no_sentence(self):
        # `planner` is priced at null in both units: a role the variant deliberately does not cap.
        self.assertIsNone(self.guard({"prompt": "Plan it in at most 200 words.",
                                      "subagent_type": "planner"}))

    def test_a_role_the_table_does_not_name_gets_no_sentence(self):
        self.assertNotIn("Expected spend", self.prompt({"prompt": "x", "subagent_type": "Explore"}))

    def test_the_multiplier_is_reflected_as_the_table_rounds_it(self):
        prompt = self.prompt({"prompt": "x", "subagent_type": "gatherer"},
                             env={"HARNESS_STANCE_COST": "frugal"})
        self.assertIn("about 5,100 output tokens and about 9 tool calls", prompt)

    def test_a_routed_unnamed_spawn_is_priced_by_its_band(self):
        self.install_workers()
        prompt = self.prompt({"prompt": "x"})
        self.assertIn("about 39,000 output tokens and about 90 tool calls", prompt)  # band B

    def test_an_unrouted_unnamed_spawn_is_priced_by_nothing(self):
        # No worker definitions installed, so nothing routes this spawn and no band prices it.
        self.assertNotIn("Expected spend", self.prompt({"prompt": "x"}))
        self.assertNotIn("Expected spend",
                         self.prompt({"prompt": "x", "subagent_type": "general-purpose"}))

    def test_a_non_tiered_delegation_stance_prices_no_unnamed_spawn(self):
        self.install_workers()
        self.config("session-model")
        self.assertNotIn("Expected spend", self.prompt({"prompt": "x"}))

    def test_the_bound_comes_before_the_budget(self):
        self.install_workers()
        prompt = self.prompt({"prompt": "x"})
        self.assertLess(prompt.index("Return at most 400 words"), prompt.index("Expected spend:"))
        # The cap is the exception this hook reports; the budget rides along without a word.
        self.assertEqual(self.guard({"prompt": "x"})["systemMessage"], CAP_MESSAGE)

    def test_a_budget_alone_says_nothing(self):
        out = self.guard({"prompt": "x", "subagent_type": "gatherer"})
        self.assertIn("Expected spend", out["hookSpecificOutput"]["updatedInput"]["prompt"])
        self.assertNotIn("systemMessage", out)


class LeavesAloneTests(HookCase):
    def test_a_second_pass_over_its_own_output_changes_nothing(self):
        self.install_workers()
        once = self.prompt({"prompt": "x"})
        self.assertIsNone(self.guard({"prompt": once}))

    def test_a_brief_that_prices_itself(self):
        for own in ("Stay under 20 tool calls.", "Spend at most 9,000 output tokens.",
                    "Keep to a budget of 30 tool calls."):
            with self.subTest(brief=own):
                self.assertIsNone(self.guard({"prompt": own, "subagent_type": "gatherer"}))

    def test_a_brief_that_prices_itself_still_gets_its_bound(self):
        prompt = self.prompt({"prompt": "Stay under 20 tool calls."})
        self.assertIn("at most 400 words", prompt)
        self.assertNotIn("Expected spend", prompt)


class NullVariantTests(HookCase):
    """The guarantee: nothing in this release is compulsory."""

    def null_variant(self):
        self.install_workers()
        self.variant("plain", {"schema_version": 1, "extends": None, "rows": {}})

    def test_a_variant_that_prices_nothing_prints_the_0_10_0_bytes(self):
        self.null_variant()
        for name, tool_input, expected in NULL_VARIANT_FIXTURES:
            with self.subTest(case=name):
                self.assertEqual(self.guard(tool_input), expected)

    def test_a_table_that_cannot_be_built_prints_the_same(self):
        module = load(GUARD, "harness_brief_guard")
        real = module.sibling

        def broken(name):
            loaded = real(name)
            if name == "posture" and loaded is not None:
                loaded.cost_table = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no table"))
            return loaded

        module.sibling = broken
        self.install_workers()
        for name, tool_input, expected in NULL_VARIANT_FIXTURES:
            with self.subTest(case=name):
                payload = {"tool_name": "Agent", "tool_input": tool_input,
                           "transcript_path": str(self.transcript)}
                out = io.StringIO()
                with unittest.mock.patch.dict(os.environ, self.env(), clear=True), \
                        unittest.mock.patch.object(module.sys, "stdin",
                                                   io.StringIO(json.dumps(payload))), \
                        contextlib.redirect_stdout(out):
                    module.main()
                text = out.getvalue()
                self.assertEqual(json.loads(text) if text.strip() else None, expected)


class OneRouterTests(HookCase):
    """Both hooks ask the same function where an unnamed spawn goes; two answers would drift."""

    def test_the_guard_routes_through_the_spawn_hooks_own_function(self):
        module = load(GUARD, "harness_brief_guard")
        router = module.sibling("tier-agent-spawns")
        self.assertEqual(Path(router.band_route.__code__.co_filename), TIER.resolve())

    def test_patching_that_function_moves_the_price_the_guard_writes(self):
        module = load(GUARD, "harness_brief_guard")
        real, asked = module.sibling, []

        def patched(name):
            loaded = real(name)
            if name == "tier-agent-spawns":
                def band_route(posture, models, cwd, table=None, session=None, announce=False):
                    asked.append(cwd)
                    return {"worker": "gatherer", "row": {}}, None
                loaded.band_route = band_route
            return loaded

        module.sibling = patched
        payload = {"tool_name": "Agent", "tool_input": {"prompt": "x"},
                   "transcript_path": str(self.transcript)}
        out = io.StringIO()
        with unittest.mock.patch.dict(os.environ, self.env(), clear=True), \
                unittest.mock.patch.object(module.sys, "stdin", io.StringIO(json.dumps(payload))), \
                contextlib.redirect_stdout(out):
            module.main()
        self.assertEqual(len(asked), 1)
        prompt = json.loads(out.getvalue())["hookSpecificOutput"]["updatedInput"]["prompt"]
        # No worker is installed in this home, so only the patched route can have priced it.
        self.assertIn("about 8,500 output tokens and about 15 tool calls", prompt)


class DetectorTests(unittest.TestCase):
    """A spend is a limiting word, a quantity and a unit; any one of them alone is prose."""

    def test_what_counts_as_a_brief_that_prices_itself(self):
        pattern = load(REPO / "claude" / "hooks" / "rule-detectors.py", "harness_detectors").BUDGET_RE
        for text, priced in (("fix the 3 tool calls in parser.py", False),
                             ("the budget of the project", False),
                             ("align the 12 tokens", False),
                             ("under 20k output tokens", True),
                             ("Return at most 400 words.", False),
                             ("Keep to a budget of 30 tool calls.", True),
                             ("Expected spend: about 8,500 output tokens.", True)):
            with self.subTest(text=text):
                self.assertEqual(bool(pattern.search(text)), priced)


class RuntimeTests(HookCase):
    """Only Claude Code reroutes an unnamed spawn, so only there is one priced by a band."""

    def test_another_runtime_prices_no_unnamed_spawn(self):
        self.install_workers()
        for runtime in ("codex", "some-future-runtime"):
            with self.subTest(runtime=runtime):
                prompt = self.prompt({"prompt": "x"}, env={"HARNESS_RUNTIME": runtime})
                self.assertNotIn("Expected spend", prompt)

    def test_another_runtime_still_prices_a_named_role(self):
        prompt = self.prompt({"prompt": "x", "subagent_type": "gatherer"},
                             env={"HARNESS_RUNTIME": "codex"})
        self.assertIn("about 8,500 output tokens", prompt)

    def test_claude_code_named_explicitly_prices_it_like_a_bare_run(self):
        self.install_workers()
        self.assertIn("about 39,000 output tokens",
                      self.prompt({"prompt": "x"}, env={"HARNESS_RUNTIME": "claude-code"}))


class WhitespaceAndZeroTests(HookCase):
    def test_a_subagent_type_of_whitespace_is_priced_by_nothing(self):
        # The spawn hook reads this as a named type and routes it nowhere, so pricing it as a
        # band worker would state a budget for a spawn that never runs as one.
        self.install_workers()
        self.assertNotIn("Expected spend", self.prompt({"prompt": "x", "subagent_type": "  "}))

    def test_a_half_that_rounds_below_one_is_left_out_like_a_null(self):
        self.variant("tiny", {"schema_version": 1, "extends": "balanced",
                              "switches": {"budget_multiplier": 0.01},
                              "rows": {"gatherer": {"budget_output_tokens": 900,
                                                    "budget_tool_calls": 15}}})
        # 900 × 0.01 rounds to 0 output tokens; 15 × 0.01 rounds to 0 tool calls. `gatherer`
        # needs no bound either, so the hook has nothing at all to say.
        self.assertIsNone(self.guard({"prompt": "x", "subagent_type": "gatherer"}))

    def test_a_zero_half_leaves_the_other_half_stated(self):
        self.variant("half", {"schema_version": 1, "extends": "balanced", "rows": {
            "gatherer": {"budget_output_tokens": 4000, "budget_tool_calls": 0}}})
        prompt = self.prompt({"prompt": "x", "subagent_type": "gatherer"})
        self.assertIn("Expected spend: about 4,000 output tokens. Past that,", prompt)


class OneTableTests(HookCase):
    """A table is a walk of every sidecar on the chain, and this hook runs on a tool call."""

    def builds(self, tool_input):
        module = load(GUARD, "harness_brief_guard")
        real, built = module.sibling, []

        def counted(name):
            loaded = real(name)
            if name == "posture" and loaded is not None:
                inner = loaded.cost_table

                def cost_table(*args, **kwargs):
                    built.append(name)
                    return inner(*args, **kwargs)

                loaded.cost_table = cost_table
            return loaded

        module.sibling = counted
        payload = {"tool_name": "Agent", "tool_input": tool_input,
                   "transcript_path": str(self.transcript)}
        with unittest.mock.patch.dict(os.environ, self.env(), clear=True), \
                unittest.mock.patch.object(module.sys, "stdin", io.StringIO(json.dumps(payload))), \
                contextlib.redirect_stdout(io.StringIO()):
            module.main()
        return len(built)

    def test_a_priced_spawn_builds_it_once_however_it_was_priced(self):
        self.install_workers()
        self.assertEqual(self.builds({"prompt": "x", "subagent_type": "gatherer"}), 1)
        self.assertEqual(self.builds({"prompt": "x"}), 1)

    def test_a_spawn_the_cheap_gates_stop_never_builds_it(self):
        self.install_workers()
        self.assertEqual(self.builds({"prompt": "Stay under 20 tool calls."}), 0)
        self.config("session-model")
        self.assertEqual(self.builds({"prompt": "x"}), 0)


class SpawnHookTests(unittest.TestCase):
    """The spawn hook carries no budget behaviour of its own; the usage feed sees what runs."""

    def test_it_holds_nothing_but_the_shared_router(self):
        text = TIER.read_text(encoding="utf-8")
        for absent in ("in_flight", "fanout", "max_parallel", "in flight"):
            self.assertNotIn(absent, text)
        module = load(TIER, "harness_tier_spawns")
        self.assertIn("table", module.band_route.__code__.co_varnames)


if __name__ == "__main__":
    unittest.main()
