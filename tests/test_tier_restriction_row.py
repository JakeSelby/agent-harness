# SPDX-License-Identifier: MIT
"""The tier-restriction row: derived per client surface, and `enforced` means a spawn is rewritten.

Run: python3 -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import REPO
from harness_core import catalog, compatibility, lifecycle

RUNTIMES = ("claude-code", "codex")


def ladder(runtime):
    """The adapter's class table, strongest first, as the spawn hook reads it."""
    tiers = json.loads((REPO / "adapters" / runtime / "bindings.json").read_text())["tiers"]
    return [tiers[name] for name in ("frontier", "strong", "standard", "light")]


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

    def test_an_unknown_state_is_refused_on_either_branch(self):
        cases = ({"state": "mostly"},
                 {"state": "enforced", "without_hooks": {"state": "sometimes"}},
                 {"state": "enforced", "without_hooks": "advisory"})
        for entry in cases:
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "adapters" / "claude-code").mkdir(parents=True)
                (root / "adapters/claude-code/capabilities.json").write_text(
                    json.dumps({"tier_restriction": entry}))
                # A client that installs hooks never reads the fallback, and still must not ship a
                # broken one, so both branches are validated whichever is resolved.
                with self.assertRaises(ValueError):
                    compatibility.tier_restriction(root, {"runtime": "claude-code"})

    def test_installs_hooks_must_be_a_boolean(self):
        data = json.loads((REPO / "compatibility/catalog.json").read_text())
        data["release_state"] = "candidate"  # no released commit to resolve outside a checkout
        data["clients"][0]["installs_hooks"] = "false"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "compatibility").mkdir()
            (root / "compatibility/catalog.json").write_text(json.dumps(data))
            (root / "VERSION").write_text(data["harness_version"] + "\n")
            with self.assertRaises(ValueError) as raised:
                compatibility.catalog(root)
        self.assertIn("installs_hooks", str(raised.exception))

    def test_the_rendered_matrix_carries_the_row_and_its_conditions(self):
        self.assertEqual(catalog.projection_drift(REPO), [])
        data = compatibility.catalog(REPO)
        rendered = "\n\n".join(catalog.compatibility_capability_table(REPO, data))
        row = next(line for line in rendered.splitlines() if line.startswith("| tier restriction |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")][1:]
        self.assertEqual(set(cells), {"enforced", "advisory"})
        self.assertEqual(cells.count("enforced"), 3)
        self.assertIn("enforced by `claude/hooks/tier-agent-spawns.py`", rendered)
        for condition in ("the `model` settings key is one this harness never writes",
                          "is `tiered`", "maps at least two models"):
            self.assertIn(condition, rendered)
        for name in ("README.md", "docs/compatibility.md"):
            self.assertIn(row, (REPO / name).read_text())

    def test_a_mechanismless_matrix_renders_no_dangling_clause(self):
        data = compatibility.catalog(REPO)
        with patch.object(compatibility, "tier_restriction",
                          return_value={"state": "none", "mechanism": None}):
            rendered = "\n\n".join(catalog.compatibility_capability_table(REPO, data))
        self.assertIn("| tier restriction | none |", rendered)
        self.assertNotIn("carried .", rendered)
        self.assertIn("**none**.", rendered)


class EnforcedMeansRewrittenTests(unittest.TestCase):
    """`enforced` is a claim about behaviour, so the row is checked against the coordinator."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"HOME": str(self.base), "PATH": os.environ["PATH"],
                                "HARNESS_STANCE_DELEGATION": "tiered"}, clear=True).start()

    def spawn(self, runtime):
        rungs = ladder(runtime)
        transcript = self.base / (runtime + ".jsonl")
        transcript.write_text(json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "model": rungs[1]}}) + "\n")
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
                   "session_id": "session-" + runtime, "transcript_path": str(transcript),
                   "tool_input": {"prompt": "do a thing", "model": rungs[0]}}
        return lifecycle.dispatch(runtime, payload), rungs

    def test_the_row_matches_what_the_coordinator_does_with_a_top_class_request(self):
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime):
                declared = compatibility.tier_restriction(REPO, {"runtime": runtime})["state"]
                result, rungs = self.spawn(runtime)
                updated = result.get("hookSpecificOutput", {}).get("updatedInput", {})
                if declared == "enforced":
                    self.assertEqual(updated.get("model"), rungs[1])
                else:
                    # Other hooks still see this call; none of them touches the class asked for.
                    self.assertEqual(updated.get("model", rungs[0]), rungs[0])


if __name__ == "__main__":
    unittest.main()
