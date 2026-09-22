"""A client's qualification never becomes a capability's; the two files must say the same thing."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_harness import REPO
from harness_core import compatibility

CASES = ["installation", "cost-posture"]


def adapter(root, runtime, stances, role_execution=None):
    path = root / "adapters" / runtime
    path.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": 1, "runtime": runtime, "stances": stances,
            "custom_stance_default": {"mode": "instruction", "qualification": "unqualified"},
            "role_execution": role_execution or {"qualification": "unqualified"}}
    (path / "capabilities.json").write_text(json.dumps(body))
    return root


def catalog(status="qualified", runtime="fixture"):
    return {"required_cases": list(CASES),
            "clients": [{"id": runtime + "-cli", "runtime": runtime, "status": status}]}


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_shipped_catalog_and_adapters_agree(self):
        self.assertEqual(compatibility.reconciliation_errors(REPO), [])

    def test_qualified_capability_without_a_covering_case_is_a_disagreement(self):
        adapter(self.root, "fixture", {"cost": {"mode": "instruction", "qualification": "qualified"}})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog()),
                         ["fixture cost is qualified with no acceptance case covering it"])

    def test_case_covering_an_unqualified_capability_is_a_disagreement(self):
        adapter(self.root, "fixture", {"cost": {"mode": "instruction", "qualification": "unqualified",
                                                "acceptance_cases": ["cost-posture"]}})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog()),
                         ["fixture cost is unqualified yet acceptance cases cover it: cost-posture"])

    def test_role_execution_is_reconciled_like_a_stance(self):
        adapter(self.root, "fixture", {}, {"qualification": "qualified"})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog()),
                         ["fixture role_execution is qualified with no acceptance case covering it"])

    def test_a_case_the_catalog_does_not_require_proves_nothing(self):
        adapter(self.root, "fixture", {"cost": {"qualification": "qualified",
                                                "acceptance_cases": ["invented"]}})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog()),
                         ["fixture cost names acceptance cases the catalog does not require: invented"])

    def test_a_capability_cannot_be_qualified_where_no_client_is(self):
        adapter(self.root, "fixture", {"cost": {"qualification": "qualified",
                                                "acceptance_cases": ["cost-posture"]}})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog("unqualified")),
                         ["fixture cost is qualified while no fixture client is"])

    def test_covered_capability_on_a_qualified_client_agrees(self):
        adapter(self.root, "fixture", {"cost": {"qualification": "qualified",
                                                "acceptance_cases": ["cost-posture"]}})
        self.assertEqual(compatibility.reconciliation_errors(self.root, catalog()), [])


class DerivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = adapter(Path(self.temp.name), "fixture",
                            {"cost": {"mode": "instruction", "qualification": "qualified",
                                      "acceptance_cases": ["cost-posture"]},
                             "voice": {"mode": "instruction", "qualification": "unqualified"}})

    def states(self, status):
        data = catalog(status)
        return compatibility.capability_states(self.root, data, data["clients"][0])

    def test_a_covered_capability_is_qualified_on_a_qualified_client(self):
        state = self.states("qualified")["cost"]
        self.assertEqual((state["state"], state["cases"]), ("qualified", ["cost-posture"]))

    def test_no_capability_inherits_the_clients_qualification(self):
        self.assertEqual(self.states("qualified")["voice"]["state"], "unqualified")

    def test_an_unqualified_client_qualifies_no_capability_of_its_runtime(self):
        state = self.states("unqualified")["cost"]
        self.assertEqual((state["state"], state["declared"]), ("unqualified", "qualified"))

    def test_a_runtime_without_an_adapter_declares_no_capability(self):
        data = {"required_cases": list(CASES),
                "clients": [{"id": "planned", "runtime": "absent", "status": "planned"}]}
        self.assertEqual(compatibility.capability_states(self.root, data, data["clients"][0]), {})


class CommandTests(unittest.TestCase):
    def test_json_carries_the_capability_states_beside_every_client(self):
        done = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "compatibility", "--json"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        rows = {row["id"]: row for row in data["clients"]}
        row = rows["claude-code-cli-macos"]
        # The command reports the catalog's own state rather than a pinned one, so a release
        # candidate whose required clients await re-qualification still passes this.
        catalogued = {entry["id"]: entry["status"] for entry in compatibility.catalog(REPO)["clients"]}
        self.assertEqual(row["status"], catalogued["claude-code-cli-macos"])
        self.assertIn("role_execution", row["capabilities"])
        self.assertTrue(all(state["state"] in compatibility.STATES
                            for row in data["clients"] for state in row["capabilities"].values()))


if __name__ == "__main__":
    unittest.main()
