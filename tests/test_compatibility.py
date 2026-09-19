"""Published support cannot be inferred from generated files or empty evidence."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from test_harness import REPO
from harness_core import compatibility


class CompatibilityTests(unittest.TestCase):
    def test_current_catalog_is_honest_and_blocks_release(self):
        data = compatibility.catalog(REPO)
        self.assertEqual(len([row for row in data["clients"] if row.get("required_for_release")]), 7)
        self.assertTrue(all(row["status"] in compatibility.STATES for row in data["clients"]))

    def test_qualified_claim_without_native_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPO / "compatibility", root / "compatibility")
            shutil.copy(REPO / "VERSION", root / "VERSION")
            path = root / "compatibility" / "catalog.json"
            data = json.loads(path.read_text()); data["clients"][0]["status"] = "qualified"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "missing acceptance"):
                compatibility.catalog(root)

    def test_custom_stance_reports_advisory_coverage_for_both_adapters(self):
        result = compatibility.coverage(REPO, {"feedback": "direct"})
        for runtime in ("codex", "claude-code"):
            self.assertEqual(result[runtime]["feedback"]["mode"], "instruction")
