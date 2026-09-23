"""The tier-restriction row: derived per client surface, never hand-written in the rendered docs."""
import json
import tempfile
import unittest
from pathlib import Path

from test_harness import REPO
from harness_core import catalog, compatibility


class TierRestrictionTests(unittest.TestCase):
    def test_each_runtime_declares_a_state_and_the_mechanism_behind_it(self):
        expected = {"claude-code": ("enforced", "claude/hooks/tier-agent-spawns.py"),
                    "codex": ("advisory", "primitives/stances/delegation/tiered.md")}
        for runtime, (state, mechanism) in expected.items():
            row = compatibility.tier_restriction(REPO, {"runtime": runtime})
            self.assertEqual(row, {"state": state, "mechanism": mechanism})
            self.assertTrue((REPO / mechanism).exists(), mechanism)

    def test_a_surface_without_hooks_falls_back_to_the_advisory_entry(self):
        row = compatibility.tier_restriction(REPO, {"runtime": "claude-code", "installs_hooks": False})
        self.assertEqual(row["state"], "advisory")
        self.assertTrue((REPO / row["mechanism"]).exists())
        marketplace = next(client for client in json.loads((REPO / "compatibility/catalog.json").read_text())["clients"]
                           if client["id"] == "claude-code-plugin-marketplace")
        self.assertIs(marketplace["installs_hooks"], False)

    def test_a_runtime_with_no_adapter_restricts_nothing(self):
        self.assertEqual(compatibility.tier_restriction(REPO, {"runtime": "cursor"}),
                         {"state": "none", "mechanism": None})

    def test_an_unknown_state_is_refused_rather_than_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adapters" / "claude-code").mkdir(parents=True)
            (root / "adapters/claude-code/capabilities.json").write_text(
                json.dumps({"tier_restriction": {"state": "mostly"}}))
            with self.assertRaises(ValueError):
                compatibility.tier_restriction(root, {"runtime": "claude-code"})

    def test_the_rendered_matrix_carries_the_row_and_the_two_gaps(self):
        self.assertEqual(catalog.projection_drift(REPO), [])
        data = compatibility.catalog(REPO)
        rendered = "\n\n".join(catalog.compatibility_capability_table(REPO, data))
        row = next(line for line in rendered.splitlines() if line.startswith("| tier restriction |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")][1:]
        self.assertEqual(set(cells), {"enforced", "advisory"})
        self.assertEqual(cells.count("enforced"), 3)
        self.assertIn("enforced by `claude/hooks/tier-agent-spawns.py`", rendered)
        self.assertIn("`--model` is deliberately never rewritten", rendered)
        for name in ("README.md", "docs/compatibility.md"):
            self.assertIn(row, (REPO / name).read_text())


if __name__ == "__main__":
    unittest.main()
