"""Release publication depends on qualification and immutable source identity."""
import importlib.util
import json
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
