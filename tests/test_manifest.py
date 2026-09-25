# SPDX-License-Identifier: MIT
"""Module manifests (AD-22): six declared fields per module, enforced by `posture.selection()`.

Run: python3 -m unittest discover tests
"""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import catalog  # noqa: E402

spec = importlib.util.spec_from_file_location("harness_posture_manifest", str(REPO / "policy/hooks/posture.py"))
posture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(posture)

SWITCH_KINDS = sorted(kind for kind, entry in catalog.KINDS.items() if entry["value"] == "switch")
# One unit per switch kind in the fixture; `hooks` has no directory, so its unit is named by a layer.
UNITS = {"rules": "r1", "skills": "s1", "roles": "o1", "workflows": "w1", "hooks": "h1"}


def entry(**fields):
    return dict({"claims": ["does one thing"], "surface": ["resident-context"], "instruments": [],
                 "slot": None, "dependencies": [], "conflicts": []}, **fields)


def load_module(name, path):
    module_spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class Fixture(unittest.TestCase):
    """A checkout with one module of every switch kind, each with a sound manifest."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        (self.root / "lib" / "harness_core").mkdir(parents=True)
        shutil.copy(str(REPO / "lib" / "harness_core" / "catalog.py"), str(self.root / "lib" / "harness_core"))
        primitives = self.root / "primitives"
        for name in ("r1", "r2"):
            self.write(primitives / "rules" / (name + ".md"), "# rule\n")
        self.write(primitives / "skills" / "s1" / "SKILL.md", "---\nname: s1\n---\n")
        self.write(primitives / "roles" / "o1.md", "---\nname: o1\n---\n")
        self.write(primitives / "workflows" / "w1.md", "---\ndescription: w\n---\n")
        self.shipped = {"schema_version": 1, "rules": {"r1": entry(), "r2": entry()},
                        "skills": {"s1": entry()}, "roles": {"o1": entry()}, "workflows": {"w1": entry()}}
        self.hooks = {"schema_version": 1, "hooks": {"h1": entry(surface=["hook-events"])}}
        self.session = {"hooks": {"h1": "on"}}

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def resolve(self, strict=True, config=None):
        self.write(self.root / "primitives" / "manifests.json", json.dumps(self.shipped))
        self.write(self.root / "policy" / "hooks" / "manifests.json", json.dumps(self.hooks))
        self.write(self.root / "session.json", json.dumps(self.session))
        env = {"HARNESS_HOME": str(self.root / "home"), "HARNESS_SESSION_CONFIG": str(self.root / "session.json")}
        return posture.selection(env, strict=strict, config=config or {}, root=self.root)

    def manifest(self, kind):
        return (self.hooks if kind == "hooks" else self.shipped)[kind][UNITS[kind]]

    def refused(self, *needles):
        with self.assertRaises(ValueError) as caught:
            self.resolve()
        for needle in needles:
            self.assertIn(needle, str(caught.exception))
        return str(caught.exception)


class Fields(Fixture):
    def test_a_sound_manifest_for_every_switch_kind_resolves(self):
        self.assertEqual(sorted(UNITS), SWITCH_KINDS)
        result = self.resolve()
        for kind in SWITCH_KINDS:
            self.assertEqual(result[kind][UNITS[kind]], "on")

    def test_each_missing_field_fails_naming_the_module_and_the_field_for_every_switch_kind(self):
        for kind in SWITCH_KINDS:
            for field in posture.MANIFEST_FIELDS:
                with self.subTest(kind=kind, field=field):
                    self.setUp()
                    del self.manifest(kind)[field]
                    self.refused(kind + "/" + UNITS[kind], "'" + field + "'")

    def test_each_malformed_field_fails_naming_the_module_and_the_field(self):
        bad = {"claims": [[], [""], "one claim"], "surface": [[], ["somewhere"], "resident-context"],
               "instruments": ["detector:x", [3]], "slot": ["x", {"id": "x"}, {"id": "X", "cedes": False}],
               "dependencies": [["r2"], ["stances/testing"], ["rules/Bad"]], "conflicts": [["nope/x"]]}
        for field, values in bad.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.setUp()
                    self.shipped["rules"]["r1"][field] = value
                    self.refused("rules/r1", "'" + field + "'")

    def test_a_module_naming_itself_or_an_unknown_field_is_refused(self):
        self.shipped["rules"]["r1"]["conflicts"] = ["rules/r1"]
        self.refused("rules/r1", "itself")
        self.setUp()
        self.shipped["rules"]["r1"]["measured"] = True
        self.refused("rules/r1", "measured")

    def test_a_shipped_module_with_no_manifest_fails_naming_it(self):
        del self.shipped["skills"]["s1"]
        self.refused("skills/s1 has no manifest")

    def test_a_manifest_file_that_is_not_one_fails_naming_the_file(self):
        self.shipped["schema_version"] = 2
        self.refused("manifests.json", "schema_version")
        self.setUp()
        self.shipped["stances"] = {}
        self.refused("'stances', which is not a switch kind")

    def test_non_strict_resolution_does_not_enforce_manifests(self):
        del self.shipped["rules"]["r1"]["slot"]
        self.assertEqual(self.resolve(strict=False)["rules"]["r1"], "on")


class Refusals(Fixture):
    def test_two_modules_claiming_one_slot_fail_naming_both(self):
        self.shipped["rules"]["r1"]["slot"] = {"id": "planning", "cedes": False}
        self.shipped["skills"]["s1"]["slot"] = {"id": "planning", "cedes": False}
        self.refused("rules/r1", "skills/s1", "'planning'")

    def test_a_module_that_cedes_the_slot_resolves(self):
        self.shipped["rules"]["r1"]["slot"] = {"id": "planning", "cedes": True}
        self.shipped["skills"]["s1"]["slot"] = {"id": "planning", "cedes": False}
        self.assertEqual(self.resolve()["rules"]["r1"], "on")

    def test_a_slot_held_by_a_switched_off_module_is_free(self):
        self.shipped["rules"]["r1"]["slot"] = {"id": "planning", "cedes": False}
        self.hooks["hooks"]["h1"]["slot"] = {"id": "planning", "cedes": False}
        self.session["hooks"]["h1"] = "off"
        self.assertEqual(self.resolve()["hooks"]["h1"], "off")

    def test_a_dependency_not_switched_on_fails_naming_both(self):
        self.shipped["workflows"]["w1"]["dependencies"] = ["roles/o1", "hooks/h1"]
        self.session["roles"] = {"o1": "off"}
        message = self.refused("workflows/w1 depends on roles/o1")
        self.assertNotIn("hooks/h1", message)
        self.session = {}
        self.refused("workflows/w1 depends on hooks/h1")

    def test_a_dependency_nothing_installs_fails(self):
        self.shipped["roles"]["o1"]["dependencies"] = ["skills/absent"]
        self.refused("roles/o1 depends on skills/absent")

    def test_a_switched_off_module_asks_nothing_of_its_dependencies(self):
        self.shipped["workflows"]["w1"]["dependencies"] = ["roles/o1"]
        self.session["roles"] = {"o1": "off"}
        self.session["workflows"] = {"w1": "off"}
        self.assertEqual(self.resolve()["workflows"]["w1"], "off")

    def test_two_conflicting_modules_switched_on_fail_naming_both_once(self):
        self.shipped["rules"]["r1"]["conflicts"] = ["hooks/h1"]
        self.hooks["hooks"]["h1"]["conflicts"] = ["rules/r1"]
        message = self.refused("rules/r1 conflicts with hooks/h1")
        self.assertEqual(message.count("conflicts with"), 1)
        self.session["hooks"]["h1"] = "off"
        self.assertEqual(self.resolve()["rules"]["r1"], "on")


class UserRoots(Fixture):
    def setUp(self):
        super().setUp()
        self.user = Path(self.tmp.name) / "mine"
        self.write(self.user / "rules" / "own.md", "# mine\n")
        self.config = {"primitive_roots": [str(self.user)]}

    def test_a_user_module_without_a_manifest_still_resolves(self):
        self.assertEqual(self.resolve(config=self.config)["rules"]["own"], "on")

    def test_a_user_manifest_is_validated_and_enforced(self):
        self.write(self.user / "manifests.json", json.dumps(
            {"schema_version": 1, "rules": {"own": entry(conflicts=["rules/r1"])}}))
        with self.assertRaisesRegex(ValueError, "rules/own conflicts with rules/r1"):
            self.resolve(config=self.config)

    def test_a_user_manifest_cannot_redeclare_a_shipped_module(self):
        self.write(self.user / "manifests.json", json.dumps(
            {"schema_version": 1, "rules": {"r1": entry(conflicts=["rules/r2"])}}))
        with self.assertRaisesRegex(ValueError, "rules/r1 has a manifest in both"):
            self.resolve(config=self.config)


class Shipped(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((REPO / "primitives" / "manifests.json").read_text(encoding="utf-8"))
        self.declared, self.errors = posture.manifests({}, REPO)

    def test_every_shipped_module_declares_a_sound_manifest_and_nothing_else_does(self):
        self.assertEqual(self.errors, [])
        for kind in SWITCH_KINDS:
            entry_ = catalog.KINDS[kind]
            if not entry_["directory"]:
                continue
            with self.subTest(kind=kind):
                installed = posture._units_in(REPO / "primitives" / entry_["directory"], entry_["pattern"])
                self.assertEqual(set(self.declared[kind]), installed)

    def test_the_shipped_selection_resolves_strictly(self):
        result = posture.selection({"HARNESS_HOME": tempfile.gettempdir() + "/no-harness-home"}, config={}, root=REPO)
        self.assertEqual(set(result["rules"].values()), {"on"})

    def test_a_rule_lists_exactly_its_detectors_as_instruments(self):
        detectors = load_module("harness_rule_detectors_manifest", REPO / "policy/hooks/rule-detectors.py")
        for rule, manifest in self.declared["rules"].items():
            with self.subTest(rule=rule):
                expected = sorted("detector:" + d.id for d in detectors.DETECTORS.values() if d.rule == rule)
                self.assertEqual(sorted(manifest["instruments"]), expected)
                if rule in detectors.OPT_OUT:
                    self.assertEqual(manifest["instruments"], [])

    def test_a_role_depends_on_every_skill_it_declares(self):
        for path in sorted((REPO / "primitives" / "roles").glob("*.md")):
            fields, _ = catalog.frontmatter(path)
            declared = [s.strip() for s in fields.get("skills", "").split(",") if s.strip()]
            if declared == ["all"]:
                continue
            with self.subTest(role=path.stem):
                self.assertLessEqual({"skills/" + s for s in declared},
                                     set(self.declared["roles"][path.stem]["dependencies"]))

    def test_switching_off_a_dependency_of_a_shipped_module_is_refused(self):
        env = {"HARNESS_HOME": tempfile.gettempdir() + "/no-harness-home"}
        config = {"roles": {"builder": "off"}}
        with self.assertRaisesRegex(ValueError, "workflows/build depends on roles/builder"):
            posture.selection(env, config=config, root=REPO)
        config["workflows"] = {"build": "off"}
        self.assertEqual(posture.selection(env, config=copy.deepcopy(config), root=REPO)["roles"]["builder"], "off")


class Reports(unittest.TestCase):
    def test_a_module_with_no_instrument_reports_unmeasured(self):
        for manifest in (None, entry(), entry(instruments=[])):
            self.assertEqual(posture.measurement(manifest), "unmeasured")
        self.assertEqual(posture.measurement(entry(instruments=["detector:a/b"])), "measured by detector:a/b")

    def test_harness_selection_shows_an_uninstrumented_module_as_unmeasured(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(without_harness_vars(), HOME=home, HARNESS_HOME=home)
            out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "selection"],
                                 capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("rules.conciseness=on (default) unmeasured", out.stdout)
        self.assertIn("rules.secrets=on (default) measured by detector:secrets/", out.stdout)
        self.assertIn("roles.builder=on (default) unmeasured", out.stdout)
        self.assertNotIn("no effect", out.stdout)
        self.assertNotRegex(out.stdout, r"stances\.\S+ (unmeasured|measured)")


if __name__ == "__main__":
    unittest.main()
