"""Release publication depends on qualification and immutable source identity."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import REPO


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class ReleaseTests(unittest.TestCase):
    def test_native_gaps_block_preflight_even_with_a_clean_tree(self):
        module = load("release_preflight")
        with patch.object(module, "git", return_value=""), patch.object(module.compatibility, "release_errors", return_value=["fixture is unqualified"]):
            errors = module.check(REPO)
        self.assertTrue(any("unqualified" in error for error in errors))

    def test_release_notes_use_current_product_and_support_data(self):
        text = load("release_notes").notes()
        self.assertIn(json.loads((REPO / "product.json").read_text())["headline"], text)
        data = json.loads((REPO / "compatibility" / "catalog.json").read_text())
        for client in data["clients"]:
            self.assertIn(client["id"] + ": " + client["status"], text)
        version = (REPO / "VERSION").read_text().strip()
        self.assertIn("blob/v" + version + "/docs/compatibility-policy.md", text)
        self.assertIn("## Migration", text)
        self.assertIn("harness sync --dry-run", text)
        self.assertIn("architecture-viewer preview is inert", text)
        self.assertIn("### Recovery", text)

    def test_release_notes_reject_stale_or_incomplete_migration_metadata(self):
        module = load("release_notes")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("VERSION", "product.json"):
                (root / name).write_bytes((REPO / name).read_bytes())
            (root / "compatibility").mkdir()
            path = root / "compatibility/migration.json"
            for value in ({"schema_version": 1, "harness_version": "different", "summary": "x",
                           "actions": ["x"], "recovery": ["x"]},
                          {"schema_version": 1, "harness_version": (REPO / "VERSION").read_text().strip(),
                           "summary": "x", "actions": [], "recovery": ["x"]}):
                path.write_text(json.dumps(value))
                with self.subTest(value=value), patch.object(module.compatibility, "catalog", return_value={"clients": []}), self.assertRaises(ValueError):
                    module.notes(root)
