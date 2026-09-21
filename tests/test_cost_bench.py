"""The static context figure is counted, priced and gated without calling a model."""
import importlib.util
import json
import tempfile
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


if __name__ == "__main__":
    unittest.main()
