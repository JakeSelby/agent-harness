"""Authoring and resolution tests for shared primitives and generated adapters."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_harness import harness, CFG, REPO
from harness_core import catalog


class CatalogTests(unittest.TestCase):
    def test_every_native_role_has_one_shared_source_and_round_trips(self):
        self.assertEqual(catalog.projection_drift(REPO), [])
        for source in (REPO / "primitives/roles").glob("*.md"):
            fields, body = catalog.frontmatter(source)
            self.assertNotIn("model", fields)
            self.assertNotIn("tools", fields)
            claude = catalog.role_projection(REPO, "claude-code", source)
            codex = catalog.role_projection(REPO, "codex", source)
            self.assertIn(body, claude)
            instructions = next(line for line in codex.splitlines() if line.startswith("developer_instructions = "))
            self.assertEqual(json.loads(instructions.partition(" = ")[2]), body)
            self.assertIn('sandbox_mode = "read-only"' if fields["authority"] != "workspace-write"
                          else 'sandbox_mode = "workspace-write"', codex)

    def test_catalog_uses_neutral_unique_source_ids(self):
        items = catalog.catalog(REPO)["primitives"]
        self.assertEqual(len(items), len({(x["kind"], x["id"]) for x in items}))
        self.assertTrue(all(x["source"].startswith("primitives/") for x in items))
        self.assertEqual(len([x for x in items if x["kind"] == "roles"]), 7)

    def test_custom_stance_switch_changes_both_instruction_projections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "stances/feedback").mkdir(parents=True)
            for choice in ("direct", "gentle"):
                (root / "stances/feedback" / (choice + ".md")).write_text("Use " + choice + " feedback.\n")
            cfg = dict(CFG, primitive_roots=[temp], stances=dict(CFG["stances"], feedback="direct"))
            direct = catalog.resolve_stances(REPO, cfg)
            self.assertEqual(direct["feedback"].read_text(), "Use direct feedback.\n")
            self.assertIn("Use direct feedback.", harness.render_codex_agents(direct, None))
            cfg["stances"]["feedback"] = "gentle"
            gentle = catalog.resolve_stances(REPO, cfg)
            self.assertEqual(gentle["feedback"].read_text(), "Use gentle feedback.\n")
            self.assertIn("Use gentle feedback.", harness.render_codex_agents(gentle, None))
            (root / "constraints.json").write_text(json.dumps({"stances": [
                {"when": {"feedback": "gentle"}, "excludes": {"testing": CFG["stances"]["testing"]},
                 "reason": "fixture conflict"}]}))
            with self.assertRaisesRegex(ValueError, "fixture conflict"):
                catalog.resolve_stances(REPO, cfg)

    def test_unknown_and_traversal_choices_are_rejected(self):
        for name, variant in (("../escape", "x"), ("testing", "../x"), ("missing", "off")):
            cfg = dict(CFG, stances=dict(CFG["stances"], **{name: variant}))
            with self.assertRaises(ValueError):
                catalog.resolve_stances(REPO, cfg)

    def test_duplicate_custom_authority_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "stances/testing").mkdir(parents=True)
            (root / "stances/testing/off.md").write_text("different policy")
            with self.assertRaisesRegex(ValueError, "duplicate stance authority"):
                catalog.resolve_stances(REPO, dict(CFG, primitive_roots=[temp]))

    def test_project_selection_precedes_session_and_cannot_change_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project.json"
            project.write_text(json.dumps({"stances": {"testing": "off"}}))
            with patch.object(harness, "config_path", return_value=Path(temp) / "user.json"):
                env = {"HARNESS_PROJECT_CONFIG": str(project)}
                self.assertEqual(harness.load_config(env)["stances"]["testing"], "off")
                env["HARNESS_STANCE_TESTING"] = "required"
                self.assertEqual(harness.load_config(env)["stances"]["testing"], "required")
                project.write_text(json.dumps({"permissions": "bypass"}))
                with self.assertRaisesRegex(SystemExit, "stances only"):
                    harness.load_config(env)
