"""Projection preserves identities, relations, authored measurements and explicit omissions."""
import copy
import unittest
from test_harness import harness
from harness_core import integrations as api, viewer_profile as profile


def fixture():
    return {"profile": "architecture-diagram", "schema_version": 1, "document_id": "library",
            "packages": [{"id": "domain", "label": "Domain"}],
            "nodes": [{"id": "A", "kind": "class", "label": "Book", "package_id": "domain",
                       "source": {"path": "src/library/book.clj", "line": 1, "namespace": "library.book"}},
                      {"id": "a", "kind": "interface", "label": "Repository", "package_id": "domain"}],
            "relations": [{"id": "uses", "from": "A", "to": "a", "kind": "dependency"}]}


class ProfileTests(unittest.TestCase):
    def test_identity_mapping_does_not_coerce_case_or_use_labels(self):
        doc = fixture()
        edn, mapping, omitted = profile.project(doc)
        self.assertNotEqual(mapping["nodes"]["A"], mapping["nodes"]["a"])
        self.assertIn(mapping["nodes"]["A"].encode(), edn)
        self.assertIn(b":ns \"library.book\"", edn)
        self.assertEqual(mapping["relations"]["uses"]["from"], mapping["nodes"]["A"])
        doc["nodes"][0]["label"] = "Renamed"
        self.assertEqual(profile.project(doc)[1], mapping)
        self.assertIn("no generic navigation", omitted[0])

    def test_metrics_preserve_measured_zero_and_never_invent_missing_zero(self):
        doc = fixture()
        doc["nodes"][0]["metrics"] = {"coverage": {"availability": "measured", "value": 0},
                                      "crap": {"availability": "missing"}}
        edn, _, omitted = profile.project(doc)
        self.assertIn(b":coverage 0", edn)
        self.assertNotIn(b":crap", edn)
        self.assertTrue(any("crap: missing" in x for x in omitted))
        for value in (-1, 1.1, float("inf"), float("nan"), True):
            doc["nodes"][0]["metrics"]["coverage"]["value"] = value
            with self.subTest(value=value), self.assertRaises(api.IntegrationError):
                profile.project(doc)

    def test_all_supported_relations_map_without_disappearing(self):
        for kind in profile.RELATIONS:
            doc = fixture()
            doc["relations"][0]["kind"] = kind
            edn, mapping, _ = profile.project(doc)
            self.assertIn((":kind :" + kind).encode(), edn)
            self.assertEqual(mapping["relations"]["uses"]["kind"], kind)

    def test_unknown_required_fields_relations_and_hierarchical_packages_fail(self):
        for mutate in (lambda d: d.update(required_unknown=3),
                       lambda d: d["relations"][0].update(kind="imports"),
                       lambda d: d["packages"][0].update(parent_id="other"),
                       lambda d: d["nodes"][0].update(kind="function")):
            doc = fixture()
            mutate(doc)
            with self.assertRaises(api.IntegrationError):
                profile.project(doc)

    def test_optional_fields_are_reported_and_empty_data_is_valid(self):
        doc = fixture()
        doc["optional"] = {"evidence": ["observation"]}
        doc["nodes"][0]["optional"] = {"delta": "added"}
        _, _, omitted = profile.project(doc)
        self.assertIn("optional.evidence", omitted)
        self.assertIn("nodes[0].optional.delta", omitted)
        doc.update(nodes=[], relations=[], packages=[])
        self.assertIn(b":packages []", profile.project(doc)[0])

    def test_duplicates_endpoints_membership_versions_and_limits_fail(self):
        changes = [
            lambda d: d["nodes"].append(copy.deepcopy(d["nodes"][0])),
            lambda d: d["relations"].append(copy.deepcopy(d["relations"][0])),
            lambda d: d["relations"][0].update(to="unknown"),
            lambda d: d["nodes"][0].update(package_id="unknown"),
            lambda d: d.update(schema_version=True),
            lambda d: d.update(schema_version=2),
            lambda d: d.update(nodes=[{}] * 2001),
        ]
        for mutate in changes:
            doc = fixture()
            mutate(doc)
            with self.assertRaises(api.IntegrationError):
                profile.project(doc)

    def test_source_traversal_is_rejected_and_text_is_escaped(self):
        for path in ("../private.clj", "/private/file.clj", "src\\file.clj"):
            doc = fixture()
            doc["nodes"][0]["source"]["path"] = path
            with self.assertRaises(api.IntegrationError):
                profile.project(doc)
        doc = fixture()
        doc["nodes"][0]["label"] = 'Quote " \\ and\nUnicode \u2603'
        edn = profile.project(doc)[0]
        self.assertIn(b'Quote \\" \\\\ and\\nUnicode \\u2603', edn)

    def test_malformed_availability_and_oversized_numbers_are_structured_errors(self):
        for record in ({"availability": []}, {"availability": "measured", "value": 10 ** 400},
                       {"availability": "measured", "value": 2 ** 63}):
            doc = fixture()
            doc["nodes"][0]["metrics"] = {"killed": record}
            with self.assertRaises(api.IntegrationError):
                profile.project(doc)
