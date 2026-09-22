"""The static context figure is counted, priced and gated without calling a model, and the replay
runner is exercised on recorded CLI output only: no test here launches an agent."""
import importlib.util
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from test_harness import REPO


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


BENCH = load("cost_bench")


def tree(root, rule="r" * 400):
    """A checkout small enough to count by hand: 40 + 400 + 80 + 40 always-loaded, 20 listed."""
    files = {
        "VERSION": "9.9.9\n",
        "config.example.json": json.dumps({"stances": {"cost": "balanced"}}),
        "policy/prices.json": json.dumps({"models": {
            "claude-test": {"input": 1.0, "output": 5.0, "cache_read": 0.5, "cache_write": 2.0},
            "gpt-test": {"input": 1.0, "output": 5.0, "cache_read": 0.5, "cache_write": 0}}}),
        "claude/CLAUDE.md": "c" * 40,
        "claude/rules/one.md": rule,
        "claude/stances/cost/balanced.md": "b" * 80,
        "claude/stances/cost/max.md": "m" * 800,
        "claude/output-styles/style.md": "s" * 40,
        "claude/agents/worker.md": "---\nname: worker\ndescription: " + "a" * 8 + "\n  " + "a" * 3
                                   + "\nmodel: opus\n---\n" + "body " * 500,
        "claude/skills/demo/SKILL.md": "---\nname: demo\ndescription: " + "k" * 8 + "\n---\nlong body\n",
    }
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(root)


class StaticCountTests(unittest.TestCase):
    def test_counts_the_selected_variant_and_only_the_listed_descriptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = BENCH.measure(tree(tmp))
        self.assertEqual(result["harness_version"], "9.9.9")
        self.assertEqual(result["always_loaded"], {"files": 4, "lines": 4, "chars": 560, "est_tokens": 140})
        self.assertEqual(result["listings"]["chars"], 12 + 8)  # the folded line joins with a space
        self.assertEqual(result["total"]["est_tokens"], 145)
        self.assertEqual(result["worst_case_est_tokens"], 325)  # max.md stands in for balanced.md
        self.assertEqual(result["largest"][0]["path"], "claude/rules/one.md")

    def test_prices_only_models_with_cache_rates_from_the_anthropic_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            usd = BENCH.measure(tree(tmp))["usd"]
        self.assertEqual(usd, {"claude-test": {"session_start": 0.00029, "later_turn": 0.000073}})

    def test_a_file_without_frontmatter_lists_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.md"
            path.write_text("no frontmatter\ndescription: not this\n", encoding="utf-8")
            self.assertEqual(BENCH._description(path), "")


class StaticGateTests(unittest.TestCase):
    def committed(self, root):
        (root / "benchmarks").mkdir()
        (root / BENCH.STATIC).write_text(json.dumps(BENCH.measure(root)), encoding="utf-8")

    def test_missing_baseline_is_an_error_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("is missing", BENCH.check(tree(tmp))[0])

    def test_growth_inside_the_limit_passes_and_past_it_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            self.committed(root)
            self.assertEqual(BENCH.check(root), [])
            tree(tmp, rule="r" * 420)  # +3.4%
            self.assertEqual(BENCH.check(root), [])
            tree(tmp, rule="r" * 480)  # +13.8%
            errors = BENCH.check(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("grew from 145 to 165", errors[0])

    def test_an_allow_entry_must_name_this_version_this_figure_and_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            self.committed(root)
            tree(tmp, rule="r" * 480)
            allow = root / BENCH.ALLOW
            for entry in ({"harness_version": "9.9.9", "est_tokens": 165, "reason": " "},
                          {"harness_version": "9.9.8", "est_tokens": 165, "reason": "new rule"},
                          {"harness_version": "9.9.9", "est_tokens": 160, "reason": "new rule"}):
                allow.write_text(json.dumps([entry]), encoding="utf-8")
                self.assertEqual(len(BENCH.check(root)), 1, msg=entry)
            allow.write_text(json.dumps([{"harness_version": "9.9.9", "est_tokens": 165,
                                          "reason": "new rule"}]), encoding="utf-8")
            self.assertEqual(BENCH.check(root), [])

    def test_shrinking_always_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            self.committed(root)
            tree(tmp, rule="r" * 40)
            self.assertEqual(BENCH.check(root), [])


class CommittedFigureTests(unittest.TestCase):
    def test_this_checkout_is_inside_its_committed_figure(self):
        self.assertEqual(BENCH.check(REPO), [])

    def test_the_committed_figure_names_its_estimate_and_prices_a_current_model(self):
        data = json.loads((REPO / BENCH.STATIC).read_text(encoding="utf-8"))
        self.assertEqual(data["chars_per_token"], BENCH.CHARS_PER_TOKEN)
        self.assertGreater(data["total"]["est_tokens"], 0)
        self.assertTrue(any(name.startswith("claude-") for name in data["usd"]))


PRICES = {"claude-test": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5}}
TASK = {"id": "demo", "kind": "synthetic", "parent_sha": "HEAD", "good_sha": None, "prompt": ["do", "it"],
        "tests": {"oracle": "none"}, "max_turns": 5}


def result(cost=0.5, error=False, subtype="success"):
    return {"type": "result", "subtype": subtype, "is_error": error, "num_turns": 3, "total_cost_usd": cost,
            "usage": {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30,
                      "cache_read_input_tokens": 40}}


def turn(thread, read, model="claude-test-20260101"):
    return {"type": "assistant", "parent_tool_use_id": thread,
            "message": {"model": model, "usage": {"cache_read_input_tokens": read}}}


class Launch:
    """Stands in for the CLI: replays recorded output and records how it was called."""
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return types.SimpleNamespace(stdout=out, stderr="", returncode=0)


def git_repo(root):
    root = Path(root)
    root.mkdir(parents=True)
    (root / "file.txt").write_text("one\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t",
                                                 "commit", "-q", "-m", "chore: first"]):
        subprocess.run(["git", "-C", str(root)] + args, check=True, stdout=subprocess.DEVNULL)
    return root


def options(tmp, **over):
    opts = {"repo": git_repo(Path(tmp) / "source"), "home": Path(tmp) / "home", "claude": "claude",
            "model": "claude-test", "tag": "candidate", "reps": 2, "run_cap": 2.0, "spend_cap": 25.0,
            "prices": PRICES, "bare_config": Path(tmp) / "bare", "tmp": str(Path(tmp) / "runs"),
            "scorer": lambda task, workdir, repo: (True, ""), "stamp": {"date": "2026-01-01"}}
    (Path(tmp) / "runs").mkdir()
    opts["repo"].parent.joinpath("home").mkdir()
    opts.update(over)
    return opts


class ReplayArmTests(unittest.TestCase):
    def test_an_arm_gets_a_scrubbed_environment_and_only_bare_gets_the_profile(self):
        base = {"HOME": "/h", "USER": "u", "PATH": "/bin", "ANTHROPIC_BASE_URL": "x", "CLAUDE_CODE_SSE_PORT": "1"}
        self.assertEqual(BENCH.arm_env("harness", "/bare", base=base),
                         {"HOME": "/h", "USER": "u", "PATH": "/bin", "TERM": "dumb"})
        self.assertEqual(BENCH.arm_env("bare", "/bare", "frugal", base=base)["CLAUDE_CONFIG_DIR"], "/bare")
        self.assertNotIn("HARNESS_STANCE_COST", BENCH.arm_env("bare", "/bare", "frugal", base=base))
        self.assertEqual(BENCH.arm_env("harness", "/bare", "frugal", base=base)["HARNESS_STANCE_COST"], "frugal")

    def test_every_arm_runs_one_command_with_the_required_flags(self):
        command = BENCH.arm_command("claude", "claude-test", "prompt")
        for flag in ("--strict-mcp-config", "--no-session-persistence", "--verbose"):
            self.assertIn(flag, command)
        for flag, value in (("--model", "claude-test"), ("--output-format", "json"), ("--max-budget-usd", "2")):
            self.assertEqual(command[command.index(flag) + 1], value)
        fence = json.loads(command[command.index("--settings") + 1])["sandbox"]
        self.assertTrue(fence["enabled"] and fence["network"]["strictAllowlist"])
        self.assertFalse(fence["allowUnsandboxedCommands"])

    def test_a_workdir_under_home_in_a_checkout_or_below_instructions_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            for name in ("home/x", "checkout/.git", "tainted/CLAUDE.md", "clean"):
                (tmp / name).mkdir(parents=True)
            home = tmp / "home"
            self.assertIn("under the home", BENCH.unsafe_workdir(home / "x" / "run", home))
            self.assertIn("inside the checkout", BENCH.unsafe_workdir(tmp / "checkout" / "run", home))
            self.assertIn("would inherit", BENCH.unsafe_workdir(tmp / "tainted" / "run", home))
            self.assertIsNone(BENCH.unsafe_workdir(tmp / "clean" / "run", home))

    def test_the_recorded_harness_is_the_checkout_the_install_links_to_or_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            for name in ("checkout/bin", "checkout/claude", "home/.claude"):
                (tmp / name).mkdir(parents=True)
            (tmp / "checkout" / "bin" / "harness").write_text("", encoding="utf-8")
            (tmp / "checkout" / "claude" / "CLAUDE.md").write_text("", encoding="utf-8")
            self.assertIsNone(BENCH.installed_harness(tmp / "home"))
            (tmp / "home" / ".claude" / "CLAUDE.md").symlink_to(tmp / "checkout" / "claude" / "CLAUDE.md")
            self.assertEqual(BENCH.installed_harness(tmp / "home"), tmp / "checkout")

    def test_a_snapshot_keeps_the_history_its_gate_needs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp) / "source")
            for n in range(3):
                (repo / "file.txt").write_text("v%d\n" % n, encoding="utf-8")
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t",
                                "commit", "-qam", "chore: step %d" % n], check=True)
            subprocess.run(["git", "-C", str(repo), "tag", "v1"], check=True)
            at = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
            (repo / "file.txt").write_text("the fix\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t",
                            "commit", "-qam", "fix: it"], check=True)
            subprocess.run(["git", "-C", str(repo), "tag", "v2"], check=True)
            clone = BENCH.snapshot(repo, at, Path(tmp) / "clone")
            count = subprocess.check_output(["git", "-C", str(clone), "rev-list", "--all", "--count"])
            self.assertEqual(count.decode().strip(), "4")  # the ancestors the gate reads survive
            self.assertEqual(subprocess.check_output(["git", "-C", str(clone), "tag"]).decode().split(), ["v1"])

    def test_a_snapshot_cannot_reach_the_commit_that_solved_the_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(Path(tmp) / "source")
            first = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
            (repo / "file.txt").write_text("the fix\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t",
                            "commit", "-qam", "fix: it"], check=True)
            fix = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
            clone = BENCH.snapshot(repo, first, Path(tmp) / "clone")
            self.assertEqual((clone / "file.txt").read_text(encoding="utf-8"), "one\n")
            self.assertFalse(BENCH.reaches(clone, fix))
            self.assertTrue(BENCH.reaches(clone, first))
            count = subprocess.check_output(["git", "-C", str(clone), "rev-list", "--all", "--count"])
            self.assertEqual(count.decode().strip(), "1")


class ReplayCaptureTests(unittest.TestCase):
    def test_cost_tokens_and_first_turns_come_from_the_cli_json(self):
        parsed = BENCH.parse_result(json.dumps([turn(None, 1000), turn(None, 9000), turn("toolu_1", 500), result()]))
        self.assertEqual(parsed["cost_usd"], 0.5)
        self.assertEqual(parsed["tokens"], {"input_tokens": 10, "output_tokens": 20,
                                            "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40})
        self.assertEqual([t["cache_read"] for t in parsed["first_turns"]], [1000, 500])
        self.assertEqual(BENCH.parse_result(json.dumps(result()))["first_turns"], [])

    def test_model_usage_is_preferred_because_it_includes_subagents(self):
        data = dict(result(), modelUsage={"a": {"inputTokens": 1, "outputTokens": 2, "cacheCreationInputTokens": 3,
                                                "cacheReadInputTokens": 4}, "b": {"inputTokens": 5}})
        self.assertEqual(BENCH.parse_result(json.dumps(data))["tokens"]["input_tokens"], 6)

    def test_output_without_a_priced_result_is_an_error_not_a_zero(self):
        for bad in ("", "not json", "[]", json.dumps({"type": "result"})):
            with self.assertRaises(ValueError, msg=bad):
                BENCH.parse_result(bad)

    def test_normalised_cost_reprices_first_turn_reads_as_writes_or_declines(self):
        turns = [{"model": "claude-test-20260101", "cache_read": 1000000}]
        self.assertEqual(BENCH.normalised_cost(1.0, turns, PRICES), 3.3)  # + 1M x (2.5 - 0.2)
        self.assertIsNone(BENCH.normalised_cost(1.0, [], PRICES))
        self.assertIsNone(BENCH.normalised_cost(1.0, [{"model": "other", "cache_read": 5}], PRICES))


class ReplayRunTests(unittest.TestCase):
    def test_arms_interleave_and_the_leading_arm_alternates(self):
        order = [(t["id"], rep, arm) for t, rep, arm in BENCH.schedule([TASK], 2)]
        self.assertEqual(order, [("demo", 1, "bare"), ("demo", 1, "harness"),
                                 ("demo", 2, "harness"), ("demo", 2, "bare")])

    def test_a_seeded_over_cap_run_stops_before_launching(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch([])
            rows, stopped = BENCH.replay([TASK], options(tmp, spend_cap=1.5), launch)
            self.assertEqual((rows, stopped, launch.calls), ([], True, []))

    def test_the_cumulative_stop_counts_reported_cost_and_a_costless_error_at_the_run_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch([json.dumps(result(cost=1.2)), "garbage", json.dumps(result())])
            rows, stopped = BENCH.replay([TASK], options(tmp, spend_cap=5.0), launch)
            self.assertTrue(stopped)  # 1.2 + 2.0 spent, and 3.2 + 2.0 would pass 5.0
            self.assertEqual(len(launch.calls), 2)
            self.assertEqual([r["error"] for r in rows], [False, True])

    def test_an_errored_run_is_an_error_and_never_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch([json.dumps(result(error=True, subtype="error_max_budget_usd")), "garbage",
                             subprocess.TimeoutExpired("claude", 1), json.dumps(result())])
            out = Path(tmp) / "results.jsonl"
            rows, _ = BENCH.replay([TASK], options(tmp, scorer=lambda *a: (False, "")), launch, out=out)
            self.assertEqual([(r["error"], r["passed"]) for r in rows],
                             [(True, None), (True, None), (True, None), (False, False)])
            self.assertEqual(rows[0]["error_kind"], "error_max_budget_usd")
            self.assertEqual(rows[0]["cost_usd"], 0.5)  # an error's cost is still recorded
            self.assertEqual(len(out.read_text(encoding="utf-8").splitlines()), 4)

    def test_a_check_that_cannot_run_is_an_error(self):
        def broken(task, workdir, repo):
            raise KeyError("oracle")
        with tempfile.TemporaryDirectory() as tmp:
            rows, _ = BENCH.replay([TASK], options(tmp, reps=1, scorer=broken), Launch([json.dumps(result())] * 2))
            self.assertEqual([(r["error"], r["passed"], r["error_kind"]) for r in rows],
                             [(True, None, "check: KeyError")] * 2)

    def test_a_run_starts_in_a_removed_clone_with_the_arm_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch([json.dumps(result())] * 4)
            opts = options(tmp)
            BENCH.replay([TASK], opts, launch)
            command, kwargs = launch.calls[0]
            self.assertEqual(command[2], "do\nit")
            self.assertEqual(kwargs["env"]["CLAUDE_CONFIG_DIR"], str(opts["bare_config"]))
            self.assertNotIn("CLAUDE_CONFIG_DIR", launch.calls[1][1]["env"])
            self.assertFalse(Path(kwargs["cwd"]).exists())
            self.assertEqual(list(Path(opts["tmp"]).iterdir()), [])

    def test_a_run_under_the_home_directory_is_refused_before_launching(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch([])
            with self.assertRaises(SystemExit):
                BENCH.replay([TASK], options(tmp, home=Path(tmp)), launch)
            self.assertEqual(launch.calls, [])


def row(arm, rep, passed, cost, error=False):
    return {"arm": arm, "rep": rep, "passed": None if error else passed, "error": error, "cost_usd": cost,
            "cost_normalised_usd": cost, "date": "2026-01-01", "harness_version": "9.9.9", "harness_sha": "a" * 40,
            "tag": "candidate", "model": "claude-test", "cli_version": "1.0"}


class FixtureGateTests(unittest.TestCase):
    def test_a_red_gate_in_a_clean_snapshot_is_reported_against_the_task_not_the_agent(self):
        calls = []
        real, real_oracle = BENCH.repo_gate, BENCH._oracle
        BENCH.repo_gate = lambda workdir, commands, python=None: calls.append(1) or [("gate", 1)]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo = git_repo(Path(tmp) / "source")
                task = dict(TASK, parent_sha="HEAD", tests={"oracle": "none"})
                BENCH._oracle = lambda r, n: types.SimpleNamespace(check=lambda root: ["no"],
                                                                   solve=lambda root: None)
                errors = BENCH.verify_tasks([task], repo, Path(tmp) / "work", [["gate"]])
            self.assertTrue(calls)
            self.assertIn("already fails in a clean snapshot", errors[0])
        finally:
            BENCH.repo_gate, BENCH._oracle = real, real_oracle


class ReplaySummaryTests(unittest.TestCase):
    def test_cost_per_passed_task_is_the_mean_of_reps_and_failures_still_cost(self):
        rows = [row("bare", 1, True, 1.0), row("bare", 1, False, 1.0), row("bare", 2, True, 1.0),
                row("bare", 2, True, 1.0), row("harness", 1, True, 0.5), row("harness", 2, True, 0.7)]
        summary = BENCH.summarise(rows)
        self.assertEqual(summary["bare"], {"runs": 4, "errors": 0, "passed": 1.5, "cost_per_passed": 1.5})
        self.assertEqual(summary["harness"]["cost_per_passed"], 0.6)

    def test_errors_sit_outside_both_figures_and_are_counted(self):
        summary = BENCH.summarise([row("bare", 1, True, 1.0), row("bare", 1, None, 9.0, error=True)])
        self.assertEqual(summary["bare"], {"runs": 2, "errors": 1, "passed": 1.0, "cost_per_passed": 1.0})

    def test_the_threshold_needs_both_the_ratio_and_the_pass_count(self):
        def pair(harness_cost, harness_passed, bare_passed=4.0):
            return {"bare": {"cost_per_passed": 1.0, "passed": bare_passed},
                    "harness": {"cost_per_passed": harness_cost, "passed": harness_passed}}
        self.assertEqual(BENCH.verdict(pair(0.85, 3.0)), (0.85, "passed"))
        self.assertEqual(BENCH.verdict(pair(0.86, 4.0)), (0.86, "failed"))
        self.assertEqual(BENCH.verdict(pair(0.5, 2.5)), (0.5, "failed"))  # cheaper, passing too few
        self.assertEqual(BENCH.verdict(pair(None, 0.0)), (None, "failed"))  # passed nothing: no ratio needed
        self.assertEqual(BENCH.verdict(pair(None, 3.5)), (None, "inconclusive"))

    def test_history_holds_one_row_per_version_and_day_and_renders_without_em_dashes(self):
        rows = [row("bare", 1, True, 1.0), row("harness", 1, True, 0.5)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            BENCH.upsert_history(path, BENCH.history_row(rows, "s1"))
            kept = BENCH.upsert_history(path, BENCH.history_row(rows, "s1"))
            self.assertEqual(len(kept), 1)
            self.assertEqual(len(BENCH.upsert_history(path, BENCH.history_row(rows, "s2"))), 2)
        self.assertEqual((kept[0]["ratio"], kept[0]["status"]), (0.5, "passed"))
        text = BENCH.render_history(kept)
        self.assertIn("| 0.500 |", text)
        self.assertNotIn("\u2014", text)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tasks = BENCH.load_tasks(REPO / BENCH.TASKS)

    def test_two_solved_issues_and_two_synthetic_tasks_are_pinned_by_full_sha(self):
        self.assertEqual(sorted(t["kind"] for t in self.tasks), ["issue", "issue", "synthetic", "synthetic"])
        for task in self.tasks:
            self.assertRegex(task["parent_sha"], r"^[0-9a-f]{40}$")
            if task["kind"] == "issue":
                self.assertRegex(task["good_sha"], r"^[0-9a-f]{40}$")
            else:
                self.assertTrue((REPO / BENCH.ORACLES / (task["tests"]["oracle"] + ".py")).is_file())

    def test_a_prompt_never_names_its_held_back_check(self):
        for task in self.tasks:
            prompt = BENCH.prompt_of(task)
            for held in task["tests"].get("copy", []) + task["tests"].get("select", []) + ["oracle"]:
                self.assertNotIn(held, prompt, msg=task["id"])

    def test_a_malformed_task_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tasks.json"
            path.write_text(json.dumps({"tasks": [{"id": "x", "kind": "issue"}]}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                BENCH.load_tasks(path)


class OracleTests(unittest.TestCase):
    def hooks(self, tmp):
        folder = Path(tmp) / "policy" / "hooks"
        folder.mkdir(parents=True)
        for index in range(18):
            future = "from __future__ import annotations\n" if index == 0 else ""
            (folder / ("hook-%02d.py" % index)).write_text(
                '"""Hook %d does  one thing.\n\nMore.\n"""\n%simport os\n\n\ndef run():\n    def inner():\n'
                '        pass\n\n\nclass K:\n    def method(self):\n        pass\n' % (index, future), encoding="utf-8")
        return Path(tmp)

    def test_the_inventory_check_fails_empty_passes_solved_and_catches_one_wrong_count(self):
        oracle = BENCH._oracle(REPO, "hook_inventory")
        with tempfile.TemporaryDirectory() as tmp:
            root = self.hooks(tmp)
            self.assertEqual(oracle.check(root), ["hook-inventory.json is missing"])
            oracle.solve(root)
            self.assertEqual(oracle.check(root), [])
            data = json.loads((root / oracle.OUTPUT).read_text(encoding="utf-8"))
            self.assertEqual(data["hook-03.py"], {"summary": "Hook 3 does one thing.", "top_level_functions": 1})
            data["hook-03.py"]["top_level_functions"] = 2
            (root / oracle.OUTPUT).write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(len(oracle.check(root)), 1)

    def test_the_constant_check_fails_untouched_passes_solved_and_catches_a_broken_module(self):
        oracle = BENCH._oracle(REPO, "hook_ids")
        with tempfile.TemporaryDirectory() as tmp:
            root = self.hooks(tmp)
            self.assertEqual(len(oracle.check(root)), 18)
            oracle.solve(root)
            self.assertEqual(oracle.check(root), [])
            first = root / "policy" / "hooks" / "hook-00.py"
            first.write_text('HOOK_ID = "hook-00"\n' + first.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(len(oracle.check(root)), 1)  # before the __future__ import: no longer compiles


if __name__ == "__main__":
    unittest.main()
