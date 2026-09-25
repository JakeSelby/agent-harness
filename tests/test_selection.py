# SPDX-License-Identifier: MIT
"""The selection document and its one resolver, `posture.selection()`.

Every unit of every kind resolves over one ladder — default, mode, user, project, session — and
every consumer reads the same answer: the hooks through `posture`, the CLI through `load_config`
and `harness selection`, an isolated worker through the selection its launching session holds.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import catalog, workers  # noqa: E402

loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

spec = importlib.util.spec_from_file_location("harness_posture_selection", str(REPO / "policy/hooks/posture.py"))
posture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(posture)

SELECTABLE = sorted(kind for kind, entry in catalog.KINDS.items() if entry["value"])


class Ladder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.roots = self.dir / "roots"
        (self.roots / "modes").mkdir(parents=True)

    def file(self, name, data):
        path = self.dir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def mode(self, name, data):
        (self.roots / "modes" / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")

    def user(self, **data):
        return dict({"primitive_roots": [str(self.roots)]}, **data)

    def resolve(self, user=None, strict=True, **env):
        return posture.selection(dict({"HARNESS_HOME": str(self.dir)}, **env), strict=strict,
                                 config=self.user() if user is None else user)

    def test_every_unit_of_every_kind_is_listed_at_its_default(self):
        result = self.resolve()
        self.assertEqual(sorted(k for k in result if k not in ("mode", "sources")), SELECTABLE)
        self.assertIsNone(result["mode"])
        self.assertEqual(result["sources"]["mode"], "default")
        self.assertEqual(result["stances"], posture.DEFAULT_STANCES)
        rules = sorted(p.stem for p in (REPO / "primitives" / "rules").glob("*.md"))
        self.assertEqual(sorted(result["rules"]), rules)
        skills = sorted(p.parent.name for p in (REPO / "primitives" / "skills").glob("*/SKILL.md"))
        self.assertEqual(sorted(result["skills"]), skills)
        for kind in SELECTABLE:
            with self.subTest(kind=kind):
                self.assertEqual(set(result["sources"][kind].values()) or {"default"}, {"default"})
                if catalog.KINDS[kind]["value"] == "switch":
                    self.assertEqual(set(result[kind].values()) or {"on"}, {"on"})

    def test_each_source_beats_the_one_below_it(self):
        self.mode("focus", {"stances": {"testing": "from-mode", "commits": "from-mode",
                                        "voice": "from-mode", "autonomy": "from-mode"},
                            "rules": {"secrets": "off"}})
        project = self.file("project.json", {"stances": {"voice": "from-project", "autonomy": "from-project"}})
        session = self.file("session.json", {"stances": {"autonomy": "from-session"}})
        result = self.resolve(user=self.user(mode="focus", stances={"commits": "from-user",
                                                                    "voice": "from-user",
                                                                    "autonomy": "from-user"}),
                              HARNESS_PROJECT_CONFIG=project, HARNESS_SESSION_CONFIG=session)
        expected = {"licensing": ("permissive-commercial", "default"),
                    "testing": ("from-mode", "mode:focus"), "commits": ("from-user", "user"),
                    "voice": ("from-project", "project"), "autonomy": ("from-session", "session")}
        for unit, (value, source) in expected.items():
            with self.subTest(unit=unit):
                self.assertEqual((result["stances"][unit], result["sources"]["stances"][unit]), (value, source))
        self.assertEqual((result["rules"]["secrets"], result["sources"]["rules"]["secrets"]), ("off", "mode:focus"))
        self.assertEqual((result["mode"], result["sources"]["mode"]), ("focus", "user"))

    def test_the_environment_sugar_is_the_session_layers_last_word(self):
        self.mode("quiet", {"stances": {"voice": "from-mode"}})
        session = self.file("session.json", {"mode": "loud", "stances": {"testing": "from-file"}})
        result = self.resolve(HARNESS_SESSION_CONFIG=session, HARNESS_MODE="quiet",
                              HARNESS_STANCE_TESTING="from-env")
        self.assertEqual((result["stances"]["testing"], result["sources"]["stances"]["testing"]),
                         ("from-env", "session"))
        self.assertEqual((result["mode"], result["sources"]["mode"]), ("quiet", "session"))
        self.assertEqual(result["sources"]["stances"]["voice"], "mode:quiet")

    def test_the_session_file_is_read_after_the_project_file(self):
        project = self.file("project.json", {"rules": {"secrets": "off"}})
        session = self.file("session.json", {"rules": {"secrets": "on"}})
        result = self.resolve(HARNESS_PROJECT_CONFIG=project, HARNESS_SESSION_CONFIG=session)
        self.assertEqual((result["rules"]["secrets"], result["sources"]["rules"]["secrets"]), ("on", "session"))

    def test_a_project_file_setting_rules_is_honoured(self):
        project = self.file("project.json", {"rules": {"decisions-and-plans": "off"},
                                             "hooks": {"validate-plan-card": "off"}})
        result = self.resolve(HARNESS_PROJECT_CONFIG=project)
        self.assertEqual(result["rules"]["decisions-and-plans"], "off")
        self.assertEqual(result["sources"]["rules"]["decisions-and-plans"], "project")
        # A unit nothing enumerates yet is still reported with the layer that named it.
        self.assertEqual((result["hooks"]["validate-plan-card"], result["sources"]["hooks"]["validate-plan-card"]),
                         ("off", "project"))

    def test_a_non_selection_key_is_refused_by_name_in_every_file_layer(self):
        for variable, key in (("HARNESS_PROJECT_CONFIG", "identity"), ("HARNESS_SESSION_CONFIG", "permissions"),
                              ("HARNESS_PROJECT_CONFIG", "primitive_roots"), ("HARNESS_SESSION_CONFIG", "telemetry"),
                              ("HARNESS_PROJECT_CONFIG", "codex")):
            with self.subTest(variable=variable, key=key):
                named = self.file("layer.json", {"stances": {"testing": "off"}, key: {}})
                with self.assertRaisesRegex(ValueError, variable + ".*'" + key + "'"):
                    self.resolve(**{variable: named})
                # A hook takes the layers it can read; the refused file selects nothing at all.
                self.assertEqual(self.resolve(strict=False, **{variable: named})["stances"]["testing"],
                                 posture.DEFAULT_STANCES["testing"])

    def test_a_mode_file_carrying_a_non_selection_key_is_refused(self):
        self.mode("sneaky", {"permissions": "bypass"})
        with self.assertRaisesRegex(ValueError, "mode file .*'permissions'"):
            self.resolve(user=self.user(mode="sneaky"))

    def test_an_unknown_mode_resolves_to_nothing(self):
        result = self.resolve(user=self.user(mode="not-shipped"))
        self.assertEqual((result["mode"], result["sources"]["mode"]), ("not-shipped", "user"))
        self.assertEqual(result["stances"], posture.DEFAULT_STANCES)

    def test_a_switch_unit_is_on_or_off(self):
        project = self.file("project.json", {"rules": {"secrets": "maybe"}})
        with self.assertRaisesRegex(ValueError, "rules.secrets"):
            self.resolve(HARNESS_PROJECT_CONFIG=project)
        self.assertEqual(self.resolve(strict=False, HARNESS_PROJECT_CONFIG=project)["rules"]["secrets"], "on")
        for bad in (None, "", 1):
            with self.subTest(value=bad):
                project = self.file("project.json", {"rules": {"secrets": bad}})
                with self.assertRaisesRegex(ValueError, "rules.secrets"):
                    self.resolve(HARNESS_PROJECT_CONFIG=project)
                self.assertEqual(self.resolve(strict=False, HARNESS_PROJECT_CONFIG=project)["rules"]["secrets"], "on")

    def test_a_kind_is_an_object(self):
        for variable in ("HARNESS_PROJECT_CONFIG", "HARNESS_SESSION_CONFIG"):
            for bad in ([], None, "off"):
                with self.subTest(variable=variable, value=bad):
                    named = self.file("layer.json", {"rules": bad, "stances": {"testing": "off"}})
                    with self.assertRaisesRegex(ValueError, re.escape("sets rules to " + json.dumps(bad))):
                        self.resolve(**{variable: named})
                    # A hook drops only the malformed kind and keeps the rest of the file.
                    result = self.resolve(strict=False, **{variable: named})
                    self.assertEqual((result["rules"]["secrets"], result["stances"]["testing"]), ("on", "off"))

    def test_the_output_reads_back_unchanged_as_a_session_file(self):
        project = self.file("project.json", {"rules": {"secrets": "off"}, "stances": {"testing": "off"}})
        first = self.resolve(HARNESS_PROJECT_CONFIG=project)
        again = self.resolve(HARNESS_SESSION_CONFIG=self.file("session.json", first))
        for kind in SELECTABLE:
            self.assertEqual(again[kind], first[kind])

    def test_the_stance_only_readers_agree_with_the_selection(self):
        project = self.file("project.json", {"stances": {"testing": "off"}})
        env = {"HARNESS_HOME": str(self.dir), "HARNESS_PROJECT_CONFIG": project, "HARNESS_STANCE_VOICE": "plain"}
        result = posture.selection(env)
        self.assertEqual(posture.resolve(env)["stances"],
                         {k: v for k, v in result["stances"].items() if v is not None})
        self.assertEqual(posture.selected("voice", env=env), "plain")


class Kinds(unittest.TestCase):
    def test_every_kind_names_its_directory_value_and_projection(self):
        for kind, entry in catalog.KINDS.items():
            with self.subTest(kind=kind):
                # `hooks` has no directory, so the catalog enumerates its units instead.
                extra = {"units"} if kind == "hooks" else set()
                self.assertEqual(set(entry), {"directory", "pattern", "value", "projection"} | extra)
                self.assertIn(entry["value"], ("variant", "switch", None))
        self.assertEqual(SELECTABLE, ["hooks", "roles", "rules", "skills", "stances", "workflows"])
        self.assertEqual(sorted(posture.selection_kinds(REPO)), SELECTABLE)

    def test_a_hook_without_its_catalog_knows_stances_only(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(list(posture.selection_kinds(Path(temp))), ["stances"])

    def test_the_primitive_catalog_lists_kinds_with_a_directory_and_the_hook_ids(self):
        kinds = {entry["kind"] for entry in catalog.catalog(REPO)["primitives"]}
        self.assertTrue({"rules", "stances", "skills", "roles", "workflows", "hooks"} <= kinds)


class Consumers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.config = self.dir / "user.json"
        self.config.write_text(json.dumps({"stances": {"voice": "answer-card"}}), encoding="utf-8")

    def session(self, data):
        path = self.dir / "session.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def run_cli(self, *args, **env):
        merged = dict(without_harness_vars(), HOME=str(self.dir), HARNESS_HOME=str(self.dir), **env)
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness")] + list(args),
                              capture_output=True, text=True, env=merged)

    def test_load_config_reads_the_session_file_between_project_and_environment(self):
        with patch.object(harness, "config_path", return_value=self.config):
            env = {"HARNESS_SESSION_CONFIG": self.session({"stances": {"testing": "off"}})}
            cfg = harness.load_config(env)
            self.assertEqual((cfg["stances"]["testing"], cfg["stances"]["voice"]), ("off", "answer-card"))
            env["HARNESS_STANCE_TESTING"] = "required"
            self.assertEqual(harness.load_config(env)["stances"]["testing"], "required")
            env = {"HARNESS_SESSION_CONFIG": self.session({"identity": {"name": "x"}})}
            with self.assertRaisesRegex(SystemExit, "'identity'"):
                harness.load_config(env)

    def test_sync_leaves_every_session_layer_in_the_session(self):
        for name in ("HARNESS_PROJECT_CONFIG", "HARNESS_SESSION_CONFIG", "HARNESS_MODE"):
            self.assertIn(name, harness.SESSION_SCOPED)

    def test_a_worker_resolves_the_selection_of_the_session_that_launched_it(self):
        env = {"HARNESS_HOME": str(self.dir),
               "HARNESS_SESSION_CONFIG": self.session({"stances": {"testing": "off"}, "rules": {"secrets": "off"}})}
        with patch.object(harness, "config_path", return_value=self.config):
            cfg = harness.load_config(env)
        ready = workers.resolution(REPO, cfg, "claude-code", "gatherer", model="some-model")
        chosen = (REPO / "primitives" / "stances" / "testing" / "off.md").read_text(encoding="utf-8")
        self.assertIn(chosen, ready["instructions"])
        recorded = workers.session_selection(REPO, env)
        self.assertEqual(recorded, posture.selection(env, strict=False))
        self.assertEqual((recorded["stances"]["testing"], recorded["sources"]["stances"]["testing"]), ("off", "session"))
        self.assertEqual(recorded["rules"]["secrets"], "off")

    def test_harness_selection_json_lists_every_kind_with_sources(self):
        out = self.run_cli("selection", "--json",
                           HARNESS_PROJECT_CONFIG=self.session({"rules": {"secrets": "off"}}))
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(sorted(k for k in data if k not in ("mode", "sources")), SELECTABLE)
        self.assertEqual((data["rules"]["secrets"], data["sources"]["rules"]["secrets"]), ("off", "project"))
        text = self.run_cli("selection")
        self.assertIn("rules.secrets=on (default)", text.stdout)

    def test_harness_selection_refuses_a_project_identity_naming_the_key(self):
        out = self.run_cli("selection", "--json", HARNESS_PROJECT_CONFIG=self.session({"identity": {}}))
        self.assertEqual(out.returncode, 1)
        self.assertIn("'identity'", out.stderr)

    def test_the_session_start_notice_names_a_session_file_or_mode_selection(self):
        spec = importlib.util.spec_from_file_location("harness_session_hook", str(REPO / "policy/hooks/harness-session.py"))
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        base = dict(without_harness_vars(), HOME=str(self.dir), HARNESS_HOME=str(self.dir))
        session = self.session({"stances": {"testing": "off"}})
        with patch.object(hook, "remaining", return_value=60):
            with patch.dict(os.environ, base, clear=True):
                self.assertEqual(hook.resolved_overrides(REPO, {"stances": {}}), [])
            for extra in ({"HARNESS_SESSION_CONFIG": session}, {"HARNESS_MODE": "not-shipped"}):
                with self.subTest(extra=sorted(extra)), patch.dict(os.environ, dict(base, **extra), clear=True):
                    lines = hook.resolved_overrides(REPO, {"stances": {"testing": "required"}})
                    self.assertTrue(lines)
                    self.assertEqual(any(line.startswith("Effective session stance testing=off") for line in lines),
                                     "HARNESS_SESSION_CONFIG" in extra)

    def test_harness_stances_json_keeps_its_keys(self):
        out = self.run_cli("stances", "--json", HARNESS_SESSION_CONFIG=self.session({"stances": {"testing": "off"}}))
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertTrue({"schema_version", "precedence", "stances", "adapter_coverage", "conflicts"} <= set(data))
        self.assertEqual(set(data["stances"]["testing"]), {"variant", "source", "behavior"})
        self.assertEqual(data["stances"]["testing"]["variant"], "off")
        self.assertEqual(data["sources"]["testing"], "session")


if __name__ == "__main__":
    unittest.main()
