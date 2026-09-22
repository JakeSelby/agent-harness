# SPDX-License-Identifier: MIT
"""Rules and skills in a registered primitive root reach both runtimes.

`harness import` writes rules under an external root and registers it; these tests take that
root the rest of the way, through `harness sync` into a disposable home, and hold the four
properties the projection has to keep: the rules are linked and rendered, `harness diff` is
clean afterwards, `harness uninstall` takes back exactly what it adopted and leaves the
repository's own links alone, and a root the configuration names but the disk does not carry is
a warning rather than the end of the sync.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import isolate_home

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

from harness_core import importer  # noqa: E402

CFG = json.loads((REPO / "config.example.json").read_text())

CLAUDE = """# fixture-project

The prose above the first section.

## Commands

Run the suite before pushing.

## Review

One reviewer, within a week.
"""

SKILL = """---
name: fixture-root-skill
description: A skill a registered primitive root carries.
---

# Fixture root skill
"""


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


class ExternalRootProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self._environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._environ)))
        isolate_home(self.home)

    # ---------------------------------------------------------------- fixtures

    def imported_root(self, name="imported"):
        """A root `harness import` would have written, from a three-section CLAUDE.md."""
        source = self.base / "project" / "CLAUDE.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(CLAUDE, encoding="utf-8")
        root = self.base / "roots" / name
        files, _ = importer.plan(source, name)
        for item in files:
            path = root / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["text"], encoding="utf-8")
        return root, sorted(Path(item["path"]).name for item in files)

    def skill_root(self, name="second", skill="fixture-root-skill"):
        root = self.base / "roots" / name
        path = root / "skills" / skill / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SKILL, encoding="utf-8")
        return root

    def configure(self, *roots, **overrides):
        config = dict(CFG, primitive_roots=[str(r) for r in roots], **overrides)
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def sync(self, dry=False):
        return harness.cmd_sync(harness.argparse.Namespace(
            dry_run=dry, adopt=False, adopt_codex=False, print_only=False))

    def rules_dir(self, root):
        return (self.home / ".claude" / "rules" / harness.EXTERNAL_RULES_DIR
                / harness._root_slug(Path(root), {}))

    # ---------------------------------------------------------------- tests

    def test_imported_rules_are_linked_rendered_clean_and_uninstalled(self):
        root, names = self.imported_root()
        self.configure(root)
        with loud():
            self.assertEqual(self.sync(), 0)

        linked = self.rules_dir(root)
        for name in names:
            link = linked / name
            self.assertTrue(link.is_symlink(), str(link) + " was not linked")
            self.assertEqual(Path(os.readlink(link)), root / "rules" / name)
        agents = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Run the suite before pushing.", agents)
        self.assertIn("One reviewer, within a week.", agents)
        self.assertIn("<!-- primitive root: " + str(root) + " -->", agents)

        with loud() as out:
            self.assertEqual(harness.cmd_diff(harness.argparse.Namespace(quiet=False)), 0)
        self.assertNotIn("missing link", out.getvalue())

        repo_link = self.home / ".claude" / "rules" / "harness"
        self.assertTrue(repo_link.is_symlink())
        with loud():
            harness.cmd_uninstall(harness.argparse.Namespace())
        for name in names:
            self.assertFalse((linked / name).is_symlink(), name + " survived uninstall")
        self.assertFalse(repo_link.is_symlink(), "the repository's own link survived uninstall")

    def test_a_root_is_recorded_with_the_links_it_contributed(self):
        root, names = self.imported_root()
        self.configure(root)
        with loud():
            self.sync()
        manifest = json.loads((self.home / ".local" / "state" / "agent-harness"
                               / "manifest.json").read_text())
        external = [l for l in manifest["links"] if l.get("root")]
        self.assertTrue(external, "no link named the root it came from")
        self.assertEqual({l["root"] for l in external}, {str(root)})
        self.assertEqual(sorted(Path(l["path"]).name for l in external
                                if harness.EXTERNAL_RULES_DIR in l["path"]), names)

    def test_a_second_root_projects_its_skill_into_both_runtimes(self):
        root, _ = self.imported_root()
        second = self.skill_root()
        self.configure(root, second)
        with loud():
            self.assertEqual(self.sync(), 0)
        for link in (self.home / ".claude" / "skills" / "fixture-root-skill",
                     self.home / ".agents" / "skills" / "fixture-root-skill"):
            self.assertTrue(link.is_symlink(), str(link) + " was not linked")
            self.assertEqual(Path(os.readlink(link)), second / "skills" / "fixture-root-skill")
        with loud():
            harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertFalse((self.home / ".claude" / "skills" / "fixture-root-skill").is_symlink())

    def test_repository_rules_precede_external_rules_in_the_rendered_agents_file(self):
        root, _ = self.imported_root()
        self.configure(root)
        with loud():
            self.sync()
        agents = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        shipped = sorted((REPO / "primitives" / "rules").glob("*.md"))[-1]
        self.assertLess(agents.index("<!-- " + shipped.name + " -->"),
                        agents.index("<!-- primitive root: " + str(root) + " -->"))

    def test_a_missing_root_warns_once_and_the_rest_still_projects(self):
        root, names = self.imported_root()
        absent = self.base / "roots" / "gone"
        self.configure(absent, root)
        with loud() as out:
            self.assertEqual(self.sync(), 0)
        printed = out.getvalue()
        self.assertEqual(printed.count(str(absent) + " is not a directory"), 1)
        self.assertTrue((self.rules_dir(root) / names[0]).is_symlink())

    def test_a_dry_run_groups_the_projection_by_root_and_writes_nothing(self):
        root, names = self.imported_root()
        second = self.skill_root()
        self.configure(root, second)
        with loud() as out:
            self.assertEqual(self.sync(dry=True), 0)
        printed = out.getvalue()
        self.assertIn("root    " + str(root), printed)
        self.assertIn("root    " + str(second), printed)
        self.assertIn(names[0], printed)
        self.assertFalse((self.home / ".claude" / "rules" / harness.EXTERNAL_RULES_DIR).exists())
        self.assertFalse((self.home / ".claude" / "skills" / "fixture-root-skill").exists())
        self.assertFalse((self.home / ".codex" / "AGENTS.md").exists())

    def test_a_root_that_stops_carrying_a_rule_has_its_link_retired(self):
        root, names = self.imported_root()
        self.configure(root)
        with loud():
            self.sync()
        retired = self.rules_dir(root) / names[0]
        (root / "rules" / names[0]).unlink()
        with loud() as out:
            self.assertEqual(self.sync(), 0)
        self.assertIn("no longer in a registered primitive root", out.getvalue())
        self.assertFalse(retired.is_symlink())
        self.assertTrue((self.rules_dir(root) / names[-1]).is_symlink())


if __name__ == "__main__":
    unittest.main()
