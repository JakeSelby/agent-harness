# SPDX-License-Identifier: MIT
"""Unit tests for the BMad override templates and `harness integration ... bmad`. Run: python3 -m unittest discover tests

The surface each template relies on (override keys and layer ids) is pinned here, so a change
to a template is deliberate, and a fixture repository whose skills declare exactly that surface
exercises the check and the apply paths without a framework install.
"""
import importlib.machinery
import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

DESCRIPTOR = harness.frameworks.installable("bmad")
TEMPLATES = {p.name[: -len(".user.toml")]: p for p in (REPO / "templates" / "bmad" / "custom").glob("*.user.toml")}
AGENTS = {p.stem for p in (REPO / "claude" / "agents").glob("*.md")}
SPAWN = re.compile(r"Launch harness role `([\w-]+)`")
# The brief's own declaration of the role it belongs to, which the spawn hook enforces whatever
# `subagent_type` a native spawn carrying the brief names. `lib/harness_core/lifecycle.py`.
MARKER = re.compile(r"^harness-role: ([\w-]+)$", re.M)
LAYERS = ("blind-hunter", "edge-case-hunter", "verification-gap")
SURFACE = {
    "bmad-build": (
        {"workflow.implementation_handoff"},
        {("workflow.review_layers", i) for i in LAYERS} | {("workflow.oneshot_review_layers", "blind-hunter")},
    ),
    "bmad-build-auto": (
        {"workflow.implementation_handoff"},
        {("workflow.review_layers", i) for i in LAYERS + ("intent-alignment",)},
    ),
    "bmad-code-review": (
        set(),
        {("workflow.review_layers", i) for i in LAYERS + ("acceptance-auditor",)},
    ),
}


def install(base, surfaces):
    """A repository with a BMad install whose skills declare exactly the given surfaces."""
    (base / "_bmad").mkdir(exist_ok=True)
    for skill, (keys, entries) in surfaces.items():
        d = base / ".claude" / "skills" / skill
        d.mkdir(parents=True, exist_ok=True)
        lines = ["[workflow]", 'on_complete = ""']
        for key in sorted(keys):
            lines.append(f'{key.split(".", 1)[1]} = """')
            lines.append("shipped text with an id = \"decoy\" inside the string")
            lines.append('"""')
        for array, ident in sorted(entries):
            lines += [f"[[{array}]]", f'id = "{ident}"', f'name = "{ident}"', 'instruction = """', "x", '"""']
        (d / "customize.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class Quiet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self._quiet = os.environ.get("HARNESS_QUIET")
        os.environ["HARNESS_QUIET"] = "1"

    def tearDown(self):
        if self._quiet is None:
            os.environ.pop("HARNESS_QUIET", None)
        else:
            os.environ["HARNESS_QUIET"] = self._quiet

    def bmad(self, action, force=False):
        ns = harness.argparse.Namespace(action=action, name="bmad", path=str(self.base), force=force)
        return harness.cmd_integration(ns)


class TemplateTests(unittest.TestCase):
    def test_the_pinned_skills_are_shipped(self):
        self.assertEqual(set(TEMPLATES), set(SURFACE))

    def test_every_template_declares_its_pinned_surface(self):
        for skill, path in TEMPLATES.items():
            with self.subTest(skill=skill):
                self.assertEqual(harness.toml_surface(path.read_text(encoding="utf-8")), SURFACE[skill])

    def test_every_spawn_names_a_shipped_agent(self):
        for skill, path in TEMPLATES.items():
            names = SPAWN.findall(path.read_text(encoding="utf-8"))
            with self.subTest(skill=skill):
                self.assertTrue(names)
                self.assertLessEqual(set(names), AGENTS)

    def test_every_layer_keeps_its_name_and_the_placeholders_it_reads(self):
        for skill, path in TEMPLATES.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertEqual(text.count("[[workflow."), text.count("\nname = "))
                self.assertEqual(text.count("[[workflow.") - text.count("[[workflow.oneshot"), text.count("{diff_file}"))
                self.assertIn("{claims_file}", text)

    def test_every_review_brief_declares_the_role_its_launch_sentence_names(self):
        text = TEMPLATES["bmad-code-review"].read_text(encoding="utf-8")
        self.assertEqual(MARKER.findall(text), SPAWN.findall(text))
        self.assertEqual(text.count("keep the brief's first line unchanged"), len(SPAWN.findall(text)))

    def test_the_handoff_names_the_shared_builder_role(self):
        for skill in ("bmad-build", "bmad-build-auto"):
            text = TEMPLATES[skill].read_text()
            self.assertIn("Launch harness role `builder`", text)
            self.assertNotIn("`model` set to", text)

    def test_surface_reader_handles_every_fence_and_a_commented_header(self):
        text = ("[workflow] # team\n"
                "a = '''\nid = \"inside\"\n'''\n"
                'b = """one line"""\n'
                "[[workflow.review_layers]] # shipped\n"
                'id = "x"\n')
        self.assertEqual(harness.toml_surface(text),
                         ({"workflow.a", "workflow.b"}, {("workflow.review_layers", "x")}))

    def test_surface_reader_skips_fenced_strings_and_comments(self):
        text = '[workflow]\n# id = "comment"\nkey = """\nid = "inside"\n"""\n[[workflow.lenses]]\ncode = "adversarial"\n'
        self.assertEqual(harness.toml_surface(text), ({"workflow.key"}, {("workflow.lenses", "adversarial")}))


class CheckTests(Quiet):
    def test_matching_install_has_no_drift(self):
        install(self.base, SURFACE)
        lines, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(drift, [])
        self.assertTrue(all("template not installed" in line for line in lines))
        self.assertEqual(self.bmad("check"), 0)

    def test_codex_only_projection_is_supported_and_conflicting_mirrors_rejected(self):
        install(self.base, SURFACE)
        (self.base / ".claude").rename(self.base / ".agents")
        self.assertEqual(harness.integration_check(DESCRIPTOR, self.base)[1], [])
        install(self.base, SURFACE)
        path = self.base / ".claude" / "skills" / "bmad-build" / "customize.toml"
        path.write_text(path.read_text() + "\n# divergent mirror\n")
        with self.assertRaisesRegex(ValueError, "projections disagree"):
            harness.integration_check(DESCRIPTOR, self.base)

    def test_renamed_id_and_removed_key_are_reported(self):
        keys, entries = SURFACE["bmad-build"]
        surfaces = dict(SURFACE)
        surfaces["bmad-build"] = (set(), {(a, i.replace("blind-hunter", "blind-seeker")) for a, i in entries})
        install(self.base, surfaces)
        _, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(len(drift), 3, drift)
        self.assertTrue(any("implementation_handoff" in d for d in drift))
        self.assertEqual(sum("blind-hunter" in d for d in drift), 2)
        self.assertEqual(self.bmad("check"), 1)

    def test_skills_not_installed_are_skipped(self):
        install(self.base, {"bmad-code-review": SURFACE["bmad-code-review"]})
        lines, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(drift, [])
        self.assertEqual(sum("skipped" in line for line in lines), 2)

    def test_missing_explicit_review_dependencies_fail_check_on_each_surface(self):
        install(self.base, SURFACE)
        review = self.base / ".claude/skills/gds-code-review/steps/review.md"
        review.parent.mkdir(parents=True)
        review.write_text("Invoke via the `bmad-review-adversarial-general` skill.")
        _, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(len(drift), 1)
        self.assertIn("invoked skill `bmad-review-adversarial-general` is missing", drift[0])
        dependency = self.base / ".claude/skills/bmad-review-adversarial-general/SKILL.md"
        dependency.parent.mkdir(parents=True)
        dependency.write_text("Review instructions")
        self.assertEqual(harness.integration_check(DESCRIPTOR, self.base)[1], [])

    def test_matching_customization_does_not_hide_divergent_workflow_mirrors(self):
        install(self.base, SURFACE)
        import shutil
        shutil.copytree(self.base / ".claude", self.base / ".agents")
        for surface in (".agents", ".claude"):
            (self.base / surface / "skills/bmad-build/workflow.md").write_text(surface)
        _, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(drift, ["bmad-build: mirrored Markdown/TOML sources disagree"])

    def test_a_repository_without_bmad_is_an_error(self):
        self.assertEqual(self.bmad("check"), 1)


class ApplyTests(Quiet):
    def setUp(self):
        super().setUp()
        install(self.base, SURFACE)
        self.custom = self.base / "_bmad" / "custom"

    def test_apply_installs_every_template_its_skills_declare(self):
        self.assertEqual(self.bmad("apply"), 0)
        for skill, path in TEMPLATES.items():
            with self.subTest(skill=skill):
                self.assertEqual((self.custom / path.name).read_text(encoding="utf-8"),
                                 path.read_text(encoding="utf-8"))
        _, drift = harness.integration_check(DESCRIPTOR, self.base)
        self.assertEqual(drift, [])

    def test_apply_skips_skills_the_repository_lacks(self):
        (self.base / ".claude" / "skills" / "bmad-build-auto" / "customize.toml").unlink()
        self.bmad("apply")
        self.assertFalse((self.custom / "bmad-build-auto.user.toml").exists())
        self.assertTrue((self.custom / "bmad-build.user.toml").exists())

    def test_apply_skips_a_drifting_template_and_installs_the_rest(self):
        keys, entries = SURFACE["bmad-build"]
        drifted = dict(SURFACE)
        drifted["bmad-build"] = (keys, {(a, i.replace("blind-hunter", "blind-seeker")) for a, i in entries})
        install(self.base, drifted)
        actions = harness.integration_apply(DESCRIPTOR, self.base, force=False)
        self.assertFalse((self.custom / "bmad-build.user.toml").exists())
        self.assertTrue((self.custom / "bmad-code-review.user.toml").exists())
        self.assertTrue(any(a.strip().startswith("skipped") and "bmad-build.user.toml" in a for a in actions), actions)
        self.assertEqual(self.bmad("check"), 1)

    def test_apply_is_silent_when_everything_is_in_place(self):
        self.assertTrue(harness.integration_apply(DESCRIPTOR, self.base, force=False))
        self.assertEqual(harness.integration_apply(DESCRIPTOR, self.base, force=False), [])

    def test_apply_keeps_a_differing_override_unless_forced(self):
        self.custom.mkdir(parents=True)
        mine = self.custom / "bmad-build.user.toml"
        mine.write_text("[workflow]\non_complete = \"mine\"\n", encoding="utf-8")
        self.bmad("apply")
        self.assertIn("mine", mine.read_text(encoding="utf-8"))
        lines, _ = harness.integration_check(DESCRIPTOR, self.base)
        self.assertTrue(any("differs" in line for line in lines))
        self.bmad("apply", force=True)
        self.assertEqual(mine.read_text(encoding="utf-8"), TEMPLATES["bmad-build"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
