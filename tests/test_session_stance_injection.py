# SPDX-License-Identifier: MIT
"""Session-start stance injection: text only when a selection differs, and never over budget.

A project or session selection reaches the model as the resolved variant's text in the
session-start context, counted against the always-loaded budget `citizen lint` enforces; a variant
that does not fit is named with a pointer to its file instead. docs/sync-model.md says why.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
import context_budget  # noqa: E402


def load_hook():
    spec = importlib.util.spec_from_file_location("harness_session_injection",
                                                  str(REPO / "policy" / "hooks" / "harness-session.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK = load_hook()


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
    env.update(extra)
    return env


def resolved(**variants):
    """What `citizen stances --json` would print for these `{dimension: (variant, behavior)}`."""
    return json.dumps({"stances": {name: {"variant": v, "source": "/stances/%s/%s.md" % (name, v),
                                          "behavior": text}
                                   for name, (v, text) in variants.items()}})


class Budget(unittest.TestCase):
    def test_the_hook_shares_the_lints_cap_and_token_estimate(self):
        self.assertEqual(HOOK.ALWAYS_LOADED_TOKEN_CAP, context_budget.TOKEN_CAP)
        self.assertEqual(HOOK.CHARS_PER_TOKEN, context_budget._harness.CHARS_PER_TOKEN)

    def test_every_entry_fits_when_the_budget_allows(self):
        entries = [("a full text " * 10, "a pointer"), ("b full text " * 10, "b pointer")]
        self.assertEqual(HOOK.fit_stances(entries, 1000), [entries[0][0], entries[1][0]])

    def test_a_tight_budget_keeps_every_pointer_and_upgrades_in_order(self):
        entries = [("a" * 400, "a pointer"), ("b" * 400, "b pointer"), ("c" * 40, "c pointer")]
        pointers = sum(HOOK.est_tokens(p) for _, p in entries)
        budget = pointers + (HOOK.est_tokens("a" * 400) - HOOK.est_tokens("a pointer")) + 10
        lines = HOOK.fit_stances(entries, budget)
        self.assertEqual(lines, ["a" * 400, "b pointer", "c" * 40])
        self.assertLessEqual(sum(HOOK.est_tokens(line) for line in lines), budget)

    def test_the_separators_between_stances_count_against_the_budget(self):
        # Each line fits on its own, but the joined text with its separators would not.
        entries = [("a" * 10, "p"), ("b" * 10, "q")]
        lines = HOOK.fit_stances(entries, 4)
        self.assertEqual(lines, ["a" * 10, "q"])
        self.assertLessEqual(HOOK.est_tokens("\n\n".join(lines)), 4)

    def test_no_budget_still_names_every_selection(self):
        entries = [("a" * 400, "a pointer")]
        self.assertEqual(HOOK.fit_stances(entries, -50), ["a pointer"])


class Injection(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        claude = self.repo / "claude"
        (claude / "rules").mkdir(parents=True)
        (claude / "CLAUDE.md").write_text("i" * 400)
        (claude / "rules" / "kept.md").write_text("k" * 800)
        (claude / "rules" / "dropped.md").write_text("d" * 4000)
        self.linked = self.repo / "linked-testing.md"
        self.linked.write_text("s" * 200)
        self.manifest = {"repo": str(self.repo),
                         "config": {"stances": {"testing": "required", "voice": "concise"},
                                    "off": {"rules": ["dropped"]}},
                         "links": [{"path": "/h/.claude/rules/harness-stances/testing.md",
                                    "target": str(self.linked)},
                                   {"path": "/h/.claude/rules/elsewhere.md",
                                    "target": str(self.repo / "claude" / "rules" / "dropped.md")}]}

    def run_hook(self, stdout, env, config=None):
        calls = []

        def fake(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout, "")

        with patch.dict(os.environ, env, clear=True), patch.object(HOOK.subprocess, "run", fake), \
                patch.object(HOOK, "remaining", return_value=60):
            lines = HOOK.resolved_overrides(self.repo, config or {"stances": {}}, self.manifest)
        return lines, calls

    def test_the_synced_layer_counts_linked_rules_and_stances_but_not_switched_off_ones(self):
        self.assertEqual(HOOK.synced_tokens(self.repo, self.manifest), 100 + 200 + 50)

    def test_an_installed_root_rule_counts_against_the_budget(self):
        root_rule = self.repo / "root-rule.md"
        root_rule.write_text("r" * 4000)
        before = HOOK.synced_tokens(self.repo, self.manifest)
        budget = HOOK.ALWAYS_LOADED_TOKEN_CAP - before
        text = "x" * int((budget - 600) * HOOK.CHARS_PER_TOKEN)
        out = resolved(testing=("off", text), voice=("concise", "C"))
        env = clean_env(HARNESS_STANCE_TESTING="off")
        fits, _ = self.run_hook(out, env)
        self.assertTrue(fits[0].endswith(text))
        self.manifest["links"].append({"path": "/h/.claude/rules/harness-roots/mine/extra.md",
                                       "target": str(root_rule)})
        self.assertEqual(HOOK.synced_tokens(self.repo, self.manifest), before + 1000)
        lines, _ = self.run_hook(out, env)
        self.assertIn("does not fit what is left of the always-loaded budget", lines[0])
        self.assertLessEqual(sum(HOOK.est_tokens(line) for line in lines),
                             HOOK.ALWAYS_LOADED_TOKEN_CAP - before - 1000)

    def test_no_selection_costs_nothing_and_runs_nothing(self):
        lines, calls = self.run_hook(resolved(testing=("off", "OFF TEXT")), clean_env())
        self.assertEqual((lines, calls), ([], []))

    def test_a_selection_equal_to_the_synced_one_injects_nothing(self):
        out = resolved(testing=("required", "REQUIRED TEXT"), voice=("concise", "CONCISE TEXT"))
        lines, calls = self.run_hook(out, clean_env(HARNESS_STANCE_TESTING="required"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(lines, [])

    def test_a_differing_selection_injects_its_text_and_names_the_synced_variant(self):
        out = resolved(testing=("off", "OFF TEXT"), voice=("concise", "CONCISE TEXT"))
        lines, _ = self.run_hook(out, clean_env(HARNESS_STANCE_TESTING="off"))
        self.assertEqual(lines, ["Effective session stance testing=off (replaces the synced "
                                 "`required` variant for this session):\nOFF TEXT"])

    def test_the_synced_selection_is_the_manifests_not_the_edited_config(self):
        out = resolved(testing=("required", "REQUIRED TEXT"), voice=("concise", "CONCISE TEXT"))
        lines, _ = self.run_hook(out, clean_env(HARNESS_STANCE_TESTING="required"),
                                 config={"stances": {"testing": "off"}})
        self.assertEqual(lines, [])

    def test_a_project_selection_is_injected_like_a_session_one(self):
        out = resolved(testing=("required", "R"), voice=("answer-card", "CARD TEXT"))
        lines, _ = self.run_hook(out, clean_env(HARNESS_PROJECT_CONFIG="/p/harness-project.json"))
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Effective session stance voice=answer-card"))
        self.assertTrue(lines[0].endswith("CARD TEXT"))

    def test_text_over_the_remaining_budget_becomes_a_pointer_and_the_total_fits(self):
        budget = HOOK.ALWAYS_LOADED_TOKEN_CAP - HOOK.synced_tokens(self.repo, self.manifest)
        big = "x" * int((budget + 50) * HOOK.CHARS_PER_TOKEN)
        out = resolved(testing=("off", big), voice=("answer-card", "CARD TEXT"))
        lines, _ = self.run_hook(out, clean_env(HARNESS_STANCE_TESTING="off",
                                                HARNESS_STANCE_VOICE="answer-card"))
        self.assertEqual(len(lines), 2)
        self.assertIn("does not fit what is left of the always-loaded budget", lines[0])
        self.assertIn("/stances/testing/off.md", lines[0])
        self.assertNotIn(big, lines[0])
        self.assertTrue(lines[1].endswith("CARD TEXT"))
        self.assertLessEqual(sum(HOOK.est_tokens(line) for line in lines), budget)

    def test_the_line_keeps_the_prefix_the_qualification_driver_reads(self):
        out = resolved(proof=("plain", "End with PLAIN."), testing=("required", "R"),
                       voice=("concise", "C"))
        lines, _ = self.run_hook(out, clean_env(HARNESS_STANCE_PROOF="plain"))
        self.assertTrue(lines[0].startswith("Effective session stance proof=plain"))


class EndToEnd(unittest.TestCase):
    def test_the_real_cli_resolution_is_injected_only_for_the_differing_dimension(self):
        with tempfile.TemporaryDirectory() as home:
            base = clean_env(HOME=home, HARNESS_HOME=home)
            with patch.dict(os.environ, base, clear=True):
                out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "stances",
                                      "--json"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            defaults = {k: v["variant"] for k, v in json.loads(out.stdout)["stances"].items()}
            other = next(p.stem for p in sorted((REPO / "primitives" / "stances" / "testing").glob("*.md"))
                         if p.stem != defaults["testing"])
            manifest = {"repo": str(REPO), "config": {"stances": defaults}, "links": []}
            env = dict(base, HARNESS_STANCE_TESTING=other)
            with patch.dict(os.environ, env, clear=True), patch.object(HOOK, "remaining", return_value=60):
                lines = HOOK.resolved_overrides(REPO, {"stances": {}}, manifest)
                same = dict(base, HARNESS_STANCE_TESTING=defaults["testing"])
                with patch.dict(os.environ, same, clear=True):
                    unchanged = HOOK.resolved_overrides(REPO, {"stances": {}}, manifest)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Effective session stance testing=" + other))
        text = (REPO / "primitives" / "stances" / "testing" / (other + ".md")).read_text().strip()
        self.assertTrue(lines[0].endswith(text))
        self.assertEqual(unchanged, [])


if __name__ == "__main__":
    unittest.main()
