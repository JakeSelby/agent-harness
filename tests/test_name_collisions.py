# SPDX-License-Identifier: MIT
"""Duplicate primitive names are refused, and project definitions are reported as shadows.

Two roots defining one skill, agent or command name leave the runtime to pick a winner
silently, first-wins. `harness lint` and `harness sync` name both sources instead; sync refuses
before it writes. A project-level definition is a warning, never a failure.
"""
import importlib.machinery
import importlib.util
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

from harness_core import collisions  # noqa: E402

CFG = json.loads((REPO / "config.example.json").read_text())


@contextlib.contextmanager
def loud():
    prior = os.environ.pop("HARNESS_QUIET", None)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            yield buf
    finally:
        if prior is not None:
            os.environ["HARNESS_QUIET"] = prior


def write_skill(root, name, text="# fixture skill\n"):
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_flat(root, kind, name, text="# fixture\n"):
    path = root / kind / (name + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class CollisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def config(self, *roots):
        return dict(CFG, primitive_roots=[str(r) for r in roots])

    def test_the_shipped_roots_alone_carry_no_collision(self):
        self.assertEqual(collisions.collisions(REPO, dict(CFG, primitive_roots=[])), [])
        self.assertEqual(harness.check_collisions(REPO), [])

    def test_two_roots_defining_one_skill_name_are_refused_with_both_paths(self):
        # The clash docs/bmad.md records: two installs projecting one skill name into
        # ~/.claude/skills/, which the runtime resolves first-wins and never reports.
        first, second = self.root / "a", self.root / "b"
        mine = write_skill(first, "plan-project")
        theirs = write_skill(second, "plan-project", "# a different version of the same name\n")
        found = collisions.collisions(REPO, self.config(first, second))
        self.assertEqual([(name, kind) for name, kind, _ in found], [("plan-project", "skill")])
        self.assertEqual(found[0][2], [str(mine), str(theirs)])
        lines = collisions.findings(REPO, self.config(first, second))
        self.assertIn("collision: skill 'plan-project' is defined in " + str(mine) +
                      " and " + str(theirs), lines)
        self.assertIn("first-wins", lines[-1])

    def test_a_duplicate_agent_or_command_name_is_refused_the_same_way(self):
        first, second = self.root / "a", self.root / "b"
        for kind, name in (("roles", "fixture-role"), ("workflows", "fixture-flow")):
            write_flat(first, kind, name)
            write_flat(second, kind, name)
        found = collisions.collisions(REPO, self.config(first, second))
        self.assertEqual([(name, kind) for name, kind, _ in found],
                         [("fixture-role", "agent"), ("fixture-flow", "command")])
        for _, _, paths in found:
            self.assertEqual(len(paths), 2)

    def test_a_shipped_name_redefined_in_a_custom_root_names_the_repository_path(self):
        custom = self.root / "mine"
        write_flat(custom, "roles", "builder")
        findings = collisions.findings(REPO, self.config(custom))
        self.assertIn("collision: agent 'builder' is defined in primitives/roles/builder.md and "
                      + str(custom / "roles" / "builder.md"), findings)

    def test_a_project_definition_is_a_shadow_and_never_a_collision(self):
        project = self.root / "project"
        agent = project / ".claude" / "agents" / "builder.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("# the project's own builder\n", encoding="utf-8")
        skill = project / ".claude" / "skills" / "sandbox" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# the project's own sandbox\n", encoding="utf-8")
        cfg = self.config()
        self.assertEqual(collisions.collisions(REPO, cfg), [])
        lines = collisions.shadows(REPO, cfg, project)
        self.assertEqual(lines, [
            "shadowed: project agent 'builder' at " + str(agent) +
            " outranks the user-level definition in primitives/roles/builder.md",
            "shadowed: project skill 'sandbox' at " + str(skill) +
            " outranks the user-level definition in primitives/skills/sandbox/SKILL.md"])
        self.assertEqual(collisions.shadows(REPO, cfg, None), [])

    def test_a_project_name_the_harness_does_not_define_is_not_reported(self):
        project = self.root / "project"
        skill = project / ".claude" / "skills" / "entirely-its-own" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# unrelated\n", encoding="utf-8")
        self.assertEqual(collisions.shadows(REPO, self.config(), project), [])

    def test_a_relative_primitive_root_is_ignored_rather_than_read(self):
        self.assertEqual(collisions.roots(REPO, {"primitive_roots": ["relative/path", 7, ""]}),
                         [REPO / "primitives"])


class SyncRefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._environ)))
        os.environ["HOME"] = str(self.home)
        for key in list(os.environ):
            if key.startswith("HARNESS_"):
                del os.environ[key]
        os.environ["HARNESS_QUIET"] = "1"

    def configure(self, **overrides):
        config = dict(CFG, **overrides)
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def sync(self, dry=False):
        return harness.cmd_sync(harness.argparse.Namespace(
            dry_run=dry, adopt=False, adopt_codex=False, print_only=False))

    def test_sync_refuses_a_collision_with_exit_2_and_writes_nothing(self):
        custom = Path(self.tmp.name) / "mine"
        write_skill(custom, "sandbox", "# my own sandbox skill\n")
        self.configure(primitive_roots=[str(custom)])
        for dry in (True, False):
            with loud() as out:
                self.assertEqual(self.sync(dry=dry), 2)
            printed = out.getvalue()
            self.assertIn("collision: skill 'sandbox' is defined in primitives/skills/sandbox/SKILL.md",
                          printed)
            self.assertIn(str(custom / "skills" / "sandbox" / "SKILL.md"), printed)
            self.assertIn("sync refused: nothing was written", printed)
        self.assertFalse((self.home / ".claude" / "skills").exists())

    def test_sync_reports_a_project_shadow_as_a_notice_and_still_succeeds(self):
        project = Path(self.tmp.name) / "project"
        skill = project / ".claude" / "skills" / "sandbox" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# the project's own sandbox\n", encoding="utf-8")
        self.configure()
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(project)
        with loud() as out:
            self.assertEqual(self.sync(), 0)
        self.assertIn("notice  shadowed: project skill 'sandbox'", out.getvalue())


if __name__ == "__main__":
    unittest.main()
