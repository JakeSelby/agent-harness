"""The static figure prices each counted file on its own, and the CI check names every file whose
estimate moved since the committed figure. No test here calls a model."""
import contextlib
import io
import json
import tempfile
import unittest
from unittest import mock

from test_cost_bench import BENCH, tree
from test_harness import REPO


def committed(root, drop_files=False):
    figure = BENCH.measure(root)
    if drop_files:
        figure.pop("files")
    (root / "benchmarks").mkdir(exist_ok=True)
    (root / BENCH.STATIC).write_text(json.dumps(figure), encoding="utf-8")


def run_check(root):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(BENCH, "ROOT", root), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        code = BENCH.main(["static", "--check"])
    return code, out.getvalue(), err.getvalue()


def assert_sums(case, figure):
    files = figure["files"]
    case.assertEqual(len(files), figure["total"]["files"])
    case.assertEqual(sum(f["chars"] for f in files.values()), figure["total"]["chars"])
    case.assertLessEqual(abs(sum(f["est_tokens"] for f in files.values())
                             - figure["total"]["est_tokens"]), len(files) / 2.0)
    for model, total in figure["usd"].items():
        for kind in ("session_start", "later_turn"):
            summed = sum(f["usd"][model][kind] for f in files.values())
            case.assertAlmostEqual(summed, total[kind], delta=1e-6 * (len(files) + 1), msg=model)


class PerFileFigureTests(unittest.TestCase):
    def test_every_counted_file_is_priced_on_its_own_and_sums_to_the_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            figure = BENCH.measure(tree(tmp))
        files = figure["files"]
        self.assertEqual(sorted(files), ["claude/CLAUDE.md", "claude/agents/worker.md",
                                         "claude/output-styles/style.md", "claude/rules/one.md",
                                         "claude/skills/demo/SKILL.md", "claude/stances/cost/balanced.md"])
        self.assertEqual(files["claude/rules/one.md"], {
            "group": "always_loaded", "chars": 400, "est_tokens": 100,
            "usd": {"claude-test": {"session_start": 0.0002, "later_turn": 0.00005}}})
        self.assertEqual(files["claude/agents/worker.md"]["group"], "listings")
        self.assertNotIn("claude/stances/cost/max.md", files)  # the worst case is not per file
        assert_sums(self, figure)

    def test_the_committed_figure_sums_to_its_own_totals(self):
        figure = json.loads((REPO / BENCH.STATIC).read_text(encoding="utf-8"))
        self.assertIn("files", figure["scopes"])
        assert_sums(self, figure)


class FileDeltaTests(unittest.TestCase):
    def test_a_seeded_200_token_growth_names_the_file_and_fails_until_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            committed(root)
            tree(tmp, rule="r" * 1200)  # +800 characters, +200 estimated tokens
            code, out, err = run_check(root)
            self.assertEqual(code, 1)
            self.assertIn("cost-bench: claude/rules/one.md +200 tokens, +0.000400 USD per session "
                          "start, +0.000100 USD per later turn on claude-test", out)
            self.assertIn("grew from 145 to 345", err)
            (root / BENCH.ALLOW).write_text(json.dumps([{"harness_version": "9.9.9", "est_tokens": 345,
                                                         "reason": "seeded rule growth"}]), encoding="utf-8")
            code, out, err = run_check(root)
            self.assertEqual((code, err), (0, ""))
            self.assertIn("claude/rules/one.md +200 tokens", out)

    def test_an_unmoved_checkout_prints_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            committed(root)
            self.assertEqual(run_check(root), (0, "", ""))

    def test_new_and_removed_files_are_named_and_the_largest_move_comes_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            committed(root)
            (root / "claude" / "output-styles" / "style.md").unlink()
            (root / "claude" / "rules" / "two.md").write_text("t" * 80, encoding="utf-8")
            lines = BENCH.file_deltas(root)
        self.assertEqual([line.split(",")[0] for line in lines],
                         ["claude/rules/two.md (new) +20 tokens",
                          "claude/output-styles/style.md (removed) -10 tokens"])

    def test_dollars_are_priced_on_the_highest_cache_read_rate_and_name_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            prices = json.loads((root / "policy" / "prices.json").read_text(encoding="utf-8"))
            prices["models"]["claude-dear"] = {"cache_read": 3.0, "cache_write": 4.0}
            (root / "policy" / "prices.json").write_text(json.dumps(prices), encoding="utf-8")
            committed(root)
            tree(tmp, rule="r" * 404)
            (root / "policy" / "prices.json").write_text(json.dumps(prices), encoding="utf-8")
            lines = BENCH.file_deltas(root)
        self.assertEqual(lines, ["claude/rules/one.md +1 tokens, +0.000004 USD per session start, "
                                 "+0.000003 USD per later turn on claude-dear"])

    def test_a_baseline_without_per_file_figures_says_so_and_still_gates_the_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp)
            committed(root, drop_files=True)
            code, out, err = run_check(root)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("has no per-file figures", out)

    def test_no_baseline_prints_no_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(BENCH.file_deltas(tree(tmp)), [])


if __name__ == "__main__":
    unittest.main()
