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


PRODUCT = json.loads((REPO / "product.json").read_text())
README = (REPO / "README.md").read_text()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            for found in strings(item):
                yield found
    elif isinstance(value, list):
        for item in value:
            for found in strings(item):
                yield found


class ProductCopyTests(unittest.TestCase):
    """The landing copy is data, so the page, the README and GitHub About cannot drift apart."""

    def test_the_hero_leads_the_headline_and_the_github_description(self):
        hero = PRODUCT["hero"]
        for key in ("title", "subtitle", "proof"):
            self.assertTrue(hero[key].strip(), msg=key)
        self.assertEqual(PRODUCT["headline"], hero["title"])
        self.assertTrue(PRODUCT["github_description"].startswith(hero["title"]),
                        msg=PRODUCT["github_description"])

    def test_every_documented_feature_points_at_a_path_that_exists(self):
        for group in PRODUCT["capabilities"]:
            for feature in group["features"]:
                with self.subTest(feature=feature["name"]):
                    self.assertTrue((REPO / feature["doc"]).exists(), msg=feature["doc"])

    def test_the_grid_stays_a_page_rather_than_a_catalog(self):
        self.assertTrue(4 <= len(PRODUCT["capabilities"]) <= 7, msg=len(PRODUCT["capabilities"]))
        ids = [group["id"] for group in PRODUCT["capabilities"]]
        self.assertEqual(len(ids), len(set(ids)))
        for group in PRODUCT["capabilities"]:
            with self.subTest(group=group["id"]):
                self.assertTrue(group["title"].strip() and group["pitch"].strip())
                self.assertTrue(3 <= len(group["features"]) <= 6, msg=len(group["features"]))

    def test_every_feature_line_stays_short_enough_to_read_in_a_card(self):
        for group in PRODUCT["capabilities"]:
            for feature in group["features"]:
                with self.subTest(feature=feature["name"]):
                    self.assertLessEqual(len(feature["line"]), 170, msg=feature["line"])

    def test_no_published_string_carries_an_em_dash(self):
        for value in strings(PRODUCT):
            self.assertNotIn("—", value, msg=value)

    def test_planned_work_names_an_issue_a_planned_client_or_a_document(self):
        planned = {client["id"] for client in
                   json.loads((REPO / "compatibility" / "catalog.json").read_text())["clients"]
                   if client["status"] == "planned"}
        entries = PRODUCT["on_the_way"]
        self.assertLessEqual(len(entries), 5)
        for entry in entries:
            with self.subTest(entry=entry["title"]):
                self.assertTrue(entry["line"].strip())
                if "issue" in entry:
                    self.assertIsInstance(entry["issue"], int)
                elif "catalog" in entry:
                    self.assertIn(entry["catalog"], planned)
                else:
                    self.assertTrue((REPO / entry["doc"]).exists(), msg=entry["doc"])

    def test_the_readme_carries_the_same_groups_and_features(self):
        for group in PRODUCT["capabilities"]:
            self.assertIn(group["title"], README, msg=group["title"])
            for feature in group["features"]:
                self.assertIn(feature["name"], README, msg=feature["name"])
