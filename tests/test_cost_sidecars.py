# SPDX-License-Identifier: MIT
"""Unit tests for cost-variant sidecars: the schema, the `extends` chain and `posture: fixed`.

The resolver is loaded by path, the way every hook loads it. Custom variants are written into a
temporary primitive root, never into a real home.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / "claude" / "hooks"
COST = REPO / "primitives" / "stances" / "cost"
ROLES = REPO / "primitives" / "roles"

sys.path.insert(0, str(REPO / "lib"))
from harness_core import catalog  # noqa: E402

loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
harness = importlib.util.module_from_spec(importlib.util.spec_from_loader("harness", loader))
loader.exec_module(harness)

spec = importlib.util.spec_from_file_location("harness_posture", HOOKS / "posture.py")
posture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(posture)


def sidecar(name):
    return json.loads((COST / (name + ".json")).read_text(encoding="utf-8"))


class CustomRoot(unittest.TestCase):
    """A primitive root outside the checkout, the way a user's own variant is discovered."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "primitives"
        (self.root / "stances" / "cost").mkdir(parents=True)

    def write(self, name, data, prose="# Cost stance: custom\n"):
        path = self.root / "stances" / "cost" / (name + ".json")
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        path.with_suffix(".md").write_text(prose, encoding="utf-8")
        return path

    def resolve(self, variant, strict=True, delegation="tiered"):
        stances = dict(posture.DEFAULT_STANCES, cost=variant, delegation=delegation)
        return posture.cost_table(stances, {"primitive_roots": [str(self.root)]}, strict=strict)


class Extends(CustomRoot):
    def test_one_switch_overrides_and_every_other_value_is_inherited(self):
        self.write("careful", {"schema_version": 1, "extends": "balanced",
                               "switches": {"session_effort": "high"}})
        table = self.resolve("careful")
        base = self.resolve("balanced")
        self.assertEqual(table["switches"]["session_effort"], "high")
        self.assertEqual(base["switches"]["session_effort"], "medium")
        self.assertEqual({k: v for k, v in table["switches"].items() if k != "session_effort"},
                         {k: v for k, v in base["switches"].items() if k != "session_effort"})
        self.assertEqual(table["rows"], base["rows"])
        self.assertEqual(table["default_band"], base["default_band"])
        self.assertEqual([c["variant"] for c in table["extends_chain"]], ["careful", "balanced"])
        self.assertEqual(table["warnings"], [])

    def test_a_row_cell_merges_rather_than_replacing_the_row(self):
        self.write("careful", {"schema_version": 1, "extends": "balanced",
                               "rows": {"gatherer": {"effort": "medium"}}})
        row = self.resolve("careful")["rows"]["gatherer"]
        self.assertEqual(row["effort"], "medium")
        self.assertEqual(row["class"], sidecar("balanced")["rows"]["gatherer"]["class"])
        self.assertEqual(row["budget_output_tokens"],
                         sidecar("balanced")["rows"]["gatherer"]["budget_output_tokens"])

    def test_a_cycle_stops_resolution_and_warns_instead_of_hanging(self):
        self.write("ping", {"schema_version": 1, "extends": "pong"})
        self.write("pong", {"schema_version": 1, "extends": "ping"})
        table = self.resolve("ping")
        self.assertEqual([c["variant"] for c in table["extends_chain"]], ["ping", "pong"])
        self.assertTrue(any("cycle" in w for w in table["warnings"]), table["warnings"])

    def test_a_chain_longer_than_the_cap_stops_at_the_cap(self):
        names = ["deep%d" % n for n in range(posture.MAX_EXTENDS_DEPTH + 2)]
        for name, parent in zip(names, names[1:] + [None]):
            self.write(name, {"schema_version": 1, "extends": parent})
        table = self.resolve(names[0])
        self.assertEqual(len(table["extends_chain"]), posture.MAX_EXTENDS_DEPTH)
        self.assertTrue(any("deeper than" in w for w in table["warnings"]), table["warnings"])

    def test_a_variant_with_no_sidecar_resolves_to_the_base_variants_table(self):
        (self.root / "stances" / "cost" / "prose-only.md").write_text("# prose\n", encoding="utf-8")
        table = self.resolve("prose-only")
        self.assertEqual(table["cost_variant"], "prose-only")
        self.assertEqual([c["variant"] for c in table["extends_chain"]],
                         [posture.BASE_COST_VARIANT])
        self.assertEqual(table["rows"], self.resolve("balanced")["rows"])


class Schema(CustomRoot):
    def test_an_unknown_key_warns_and_is_ignored_rather_than_failing(self):
        self.write("odd", {"schema_version": 1, "extends": "balanced", "invented": True,
                           "switches": {"invented_switch": 1},
                           "rows": {"gatherer": {"invented_cell": 1, "effort": "medium"}}})
        for strict in (True, False):
            with self.subTest(strict=strict):
                table = self.resolve("odd", strict=strict)
                self.assertEqual(len(table["warnings"]), 3, table["warnings"])
                self.assertTrue(all("unknown" in w for w in table["warnings"]), table["warnings"])
                self.assertEqual(table["rows"]["gatherer"]["effort"], "medium")

    def test_a_sidecar_that_is_not_readable_json_is_strict_only(self):
        for body in ("{not json", '"a string"', "[]"):
            with self.subTest(body=body):
                self.write("broken", body)
                with self.assertRaises(ValueError):
                    self.resolve("broken")
                table = self.resolve("broken", strict=False)
                self.assertEqual([c["variant"] for c in table["extends_chain"]],
                                 [posture.BASE_COST_VARIANT])
                self.assertTrue(table["warnings"])

    def test_a_row_may_not_reach_the_top_class_or_pass_high_effort(self):
        self.write("greedy", {"schema_version": 1, "extends": "balanced",
                              "rows": {"builder": {"class": "frontier", "effort": "maximum"}}})
        table = self.resolve("greedy")
        self.assertEqual(len(table["warnings"]), 2, table["warnings"])
        self.assertEqual(table["rows"]["builder"]["class"],
                         sidecar("balanced")["rows"]["builder"]["class"])
        self.assertEqual(table["rows"]["builder"]["effort"],
                         sidecar("balanced")["rows"]["builder"]["effort"])

    def test_the_same_cells_are_lint_findings_for_a_shipped_sidecar(self):
        data = {"schema_version": 1, "rows": {"builder": {"class": "frontier", "effort": "maximum"}}}
        findings = posture.validate_sidecar(data)[1]
        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(all("builder" in f for f in findings), findings)

    def test_class_applies_only_when_delegation_resolves_to_tiered(self):
        for variant, applies in (("tiered", True), ("session-model", False), ("off", False)):
            with self.subTest(delegation=variant):
                table = self.resolve("balanced", delegation=variant)
                self.assertIs(table["class_applies"], applies)
                # The class is still reported; whether it applies is the reader's business.
                self.assertEqual(table["rows"]["builder"]["class"], "strong")


class Budgets(CustomRoot):
    def test_the_multiplier_scales_both_figures_and_the_base_is_still_reported(self):
        self.write("half", {"schema_version": 1, "extends": "balanced",
                            "switches": {"budget_multiplier": 0.5}})
        row = self.resolve("half")["rows"]["gatherer"]
        base = sidecar("balanced")["rows"]["gatherer"]
        self.assertEqual(row["base_budget_output_tokens"], base["budget_output_tokens"])
        self.assertEqual(row["budget_output_tokens"], 4300)  # 4250 rounds to the nearer 100
        self.assertEqual(row["budget_tool_calls"], 8)  # 7.5 tool calls rounds up to a whole one
        self.assertEqual(row["base_budget_tool_calls"], base["budget_tool_calls"])

    def test_an_unbudgeted_row_stays_unbudgeted_under_any_multiplier(self):
        self.write("half", {"schema_version": 1, "extends": "balanced",
                            "switches": {"budget_multiplier": 0.5}})
        row = self.resolve("half")["rows"]["planner"]
        self.assertIsNone(row["budget_output_tokens"])
        self.assertIsNone(row["base_budget_output_tokens"])

    def test_the_shipped_frugal_multiplier_is_applied_to_every_shipped_row(self):
        frugal = posture.cost_table(dict(posture.DEFAULT_STANCES, cost="frugal"))
        multiplier = sidecar("frugal")["switches"]["budget_multiplier"]
        for name, row in frugal["rows"].items():
            with self.subTest(row=name):
                if row["base_budget_output_tokens"] is None:
                    self.assertIsNone(row["budget_output_tokens"])
                    continue
                self.assertEqual(row["budget_output_tokens"],
                                 round(row["base_budget_output_tokens"] * multiplier / 100) * 100)


class FixedRoles(unittest.TestCase):
    def test_the_fixed_roles_are_the_ones_whose_frontmatter_says_so(self):
        self.assertEqual(posture.fixed_roles(),
                         {"reviewer", "spec-reviewer", "design-judge", "log-compressor"})

    def test_a_fixed_role_keeps_its_own_class_and_effort_and_takes_the_budgets(self):
        rows = posture.cost_table(dict(posture.DEFAULT_STANCES, cost="balanced"))["rows"]
        self.assertEqual(rows["reviewer"]["posture"], "fixed")
        self.assertIsNone(rows["reviewer"]["class"])
        self.assertIsNone(rows["reviewer"]["effort"])
        self.assertEqual(rows["reviewer"]["budget_output_tokens"],
                         sidecar("balanced")["rows"]["reviewer"]["budget_output_tokens"])
        self.assertEqual(rows["reviewer"]["budget_tool_calls"],
                         sidecar("balanced")["rows"]["reviewer"]["budget_tool_calls"])
        self.assertNotIn("posture", rows["builder"])
        self.assertEqual(rows["builder"]["class"], "strong")

    def test_the_frontmatter_field_is_validated_and_projections_do_not_carry_it(self):
        for name in sorted(p.stem for p in ROLES.glob("*.md")):
            fields, _ = catalog.role_contract(REPO, name)
            with self.subTest(role=name):
                self.assertIn(fields.get("posture", "fixed"), ("fixed",))
                self.assertNotIn("posture:", catalog.role_projection(REPO, "claude-code",
                                                                    ROLES / (name + ".md")))

    def test_an_unsupported_posture_value_is_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "primitives" / "roles").mkdir(parents=True)
        text = (ROLES / "reviewer.md").read_text(encoding="utf-8").replace(
            "posture: fixed", "posture: flexible")
        (root / "primitives" / "roles" / "reviewer.md").write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            catalog.role_contract(root, "reviewer")


class ShippedValues(unittest.TestCase):
    def test_every_shipped_variant_has_a_sidecar_and_every_sidecar_has_prose(self):
        self.assertEqual(sorted(p.stem for p in COST.glob("*.json")),
                         sorted(p.stem for p in COST.glob("*.md")))

    def test_the_base_variant_reproduces_todays_class_and_effort_for_every_role(self):
        rows = sidecar("balanced")["rows"]
        efforts = json.loads((REPO / "adapters" / "claude-code" / "bindings.json")
                             .read_text(encoding="utf-8"))["roles"]
        for path in sorted(ROLES.glob("*.md")):
            fields, _ = catalog.role_contract(REPO, path.stem)
            with self.subTest(role=path.stem):
                self.assertIn(path.stem, rows)
                row = rows[path.stem]
                if fields["tier"] == catalog.TIER_CLASSES[0]:
                    # A row may never name the top class, so the role's own tier is all there is.
                    self.assertNotIn("class", row)
                    self.assertNotIn("effort", row)
                    continue
                self.assertEqual(row["class"], fields["tier"])
                self.assertEqual(row["effort"], efforts[path.stem]["effort"])

    def test_the_shipped_sidecars_are_valid_against_the_schema(self):
        for path in sorted(COST.glob("*.json")):
            with self.subTest(variant=path.stem):
                self.assertEqual(posture.validate_sidecar(sidecar(path.stem))[1], [])

    def test_the_prose_files_did_not_grow(self):
        for path in sorted(COST.glob("*.md")):
            with self.subTest(variant=path.stem):
                self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 8)


class LintAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "claude" / "hooks").mkdir(parents=True)
        shutil.copy2(HOOKS / "posture.py", self.root / "claude" / "hooks" / "posture.py")
        self.cost = self.root / "primitives" / "stances" / "cost"
        self.cost.mkdir(parents=True)

    def variant(self, prose, data):
        (self.cost / "thrifty.md").write_text(prose, encoding="utf-8")
        (self.cost / "thrifty.json").write_text(json.dumps(data), encoding="utf-8")

    def test_prose_and_data_must_agree_on_the_switches_a_reader_can_check(self):
        self.variant("Session effort runs low, fan-out stays at three.\n",
                     {"schema_version": 1, "switches": {"session_effort": "low",
                                                        "max_parallel": 3}})
        self.assertEqual(harness.check_cost_sidecars(self.root), [])
        self.variant("Session effort runs low, fan-out stays at three.\n",
                     {"schema_version": 1, "switches": {"session_effort": "high",
                                                        "max_parallel": 9}})
        hits = harness.check_cost_sidecars(self.root)
        self.assertEqual(len(hits), 2, hits)
        self.assertTrue(any("session_effort" in h for h in hits), hits)
        self.assertTrue(any("max_parallel" in h for h in hits), hits)

    def test_a_null_width_needs_no_number_in_the_prose(self):
        self.variant("Fan-out is as wide as the task needs; effort stays at the default.\n",
                     {"schema_version": 1, "switches": {"session_effort": "default",
                                                        "max_parallel": None}})
        self.assertEqual(harness.check_cost_sidecars(self.root), [])

    def test_lint_reports_an_unknown_key_in_a_shipped_sidecar(self):
        self.variant("Session effort runs low.\n",
                     {"schema_version": 1, "switches": {"session_effort": "low"}, "invented": 1})
        hits = harness.check_cost_sidecars(self.root)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("unknown key 'invented'", hits[0])

    def test_the_shipped_tree_passes_the_sidecar_lint(self):
        self.assertEqual(harness.check_cost_sidecars(REPO), [])

    def test_the_stances_command_carries_the_resolved_table(self):
        out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "stances", "--json"],
                             capture_output=True, text=True, cwd=str(self.root),
                             env={"HOME": str(self.root), "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 0, out.stderr)
        cost = json.loads(out.stdout)["cost"]
        self.assertEqual(cost["cost_variant"], "balanced")
        self.assertEqual(cost["default_band"], sidecar("balanced")["default_band"])
        self.assertEqual(cost["warnings"], [])
        self.assertEqual(cost["extends_chain"][0]["source"], str(COST / "balanced.json"))
        self.assertEqual(cost["rows"]["gatherer"]["budget_output_tokens"],
                         sidecar("balanced")["rows"]["gatherer"]["budget_output_tokens"])


if __name__ == "__main__":
    unittest.main()
