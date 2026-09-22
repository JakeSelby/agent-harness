# SPDX-License-Identifier: MIT
"""An existing instruction file becomes primitives, behind a printed plan.

`harness import` splits a CLAUDE.md, AGENTS.md, `.cursorrules` or `.cursor/rules/*.mdc` into
rules under an external primitive root. The first run prints what it would write and the sync
projection of the root that would carry it; only a second run writes. Nothing in the source is
dropped, a file the ownership journal already owns is refused, and a name two roots would both
define is refused before anything is written.
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

CLAUDE = """# project-fixture

House rules for this repository.

@shared/style.md

## Commands

```sh
## not a heading, a comment in a fence
make test
```

## Testing

Every change carries a test.

## Review

One reviewer, within a week.
"""

MDC = """---
description: TypeScript conventions
globs: ["src/**/*.ts", "src/**/*.tsx"]
alwaysApply: false
---

## Types

Prefer a named type to an inline object literal.
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


def written(files):
    """The rule bodies of a plan, keyed by their path under the root."""
    return {item["path"]: item["text"] for item in files}


def body_lines(text):
    return [line for line in text.splitlines() if line.strip()]


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def source(self, name, text, subdir="project-fixture"):
        path = self.root / subdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_three_sections_and_one_import_become_four_rules_with_front_matter(self):
        path = self.source("CLAUDE.md", CLAUDE)
        shared = self.source("style.md", "# Style\n\nTwo spaces, no tabs.\n",
                             subdir="project-fixture/shared")
        files, notices = importer.plan(path, today="2026-09-22")
        plan = written(files)
        self.assertEqual(sorted(plan), ["rules/commands.md", "rules/project-fixture-preamble.md",
                                        "rules/review.md", "rules/style.md", "rules/testing.md"])
        self.assertEqual(notices, [])
        self.assertTrue(plan["rules/testing.md"].startswith(
            "---\nsource: " + str(path.resolve()) + "\nimported: 2026-09-22\n"
            "heading: Testing\n---\n\n## Testing\n"))
        # The four rules the sections and the @import produce, beside the preamble.
        self.assertIn("Every change carries a test.", plan["rules/testing.md"])
        self.assertIn("Two spaces, no tabs.", plan["rules/style.md"])
        self.assertIn("source: " + str(shared.resolve()), plan["rules/style.md"])
        self.assertIn("heading: Style", plan["rules/style.md"])
        self.assertIn("@shared/style.md", plan["rules/project-fixture-preamble.md"])

    def test_a_heading_inside_a_fenced_block_is_text_and_not_a_section(self):
        path = self.source("CLAUDE.md", CLAUDE)
        plan = written(importer.plan(path, today="2026-09-22")[0])
        self.assertNotIn("rules/not-a-heading-a-comment-in-a-fence.md", plan)
        self.assertIn("## not a heading, a comment in a fence", plan["rules/commands.md"])

    def test_mdc_front_matter_is_preserved_on_every_rule_it_produces(self):
        path = self.source("types.mdc", MDC, subdir="project-fixture/.cursor/rules")
        files, _ = importer.plan(path, today="2026-09-22")
        plan = written(files)
        self.assertEqual(sorted(plan), ["rules/types.md"])
        self.assertIn('globs: ["src/**/*.ts", "src/**/*.tsx"]', plan["rules/types.md"])
        self.assertIn("description: TypeScript conventions", plan["rules/types.md"])
        self.assertIn("alwaysApply: false", plan["rules/types.md"])
        self.assertIn("heading: Types", plan["rules/types.md"])

    def test_unclassifiable_content_lands_in_one_unsorted_rule_with_nothing_lost(self):
        text = ("---\nthis line is not a field\n---\n\nPreamble prose.\n\n"
                "## ✨\n\nA section whose heading yields no identifier.\n\n"
                "## Testing\n\nFirst.\n\n## Testing\n\nSecond, same name.\n")
        path = self.source(".cursorrules", text)
        files, notices = importer.plan(path, today="2026-09-22")
        plan = written(files)
        self.assertIn("rules/project-fixture-unsorted.md", plan)
        unsorted = plan["rules/project-fixture-unsorted.md"]
        self.assertIn(importer.UNSORTED_NOTE, unsorted)
        self.assertEqual(len(notices), 2)
        self.assertIn("yields no identifier", notices[0])
        self.assertIn("second section named 'Testing'", notices[1])
        # Nothing is dropped: every non-blank source line survives somewhere, and the rules
        # together carry at least as many bytes as the file they came from.
        combined = "\n".join(plan.values())
        for line in body_lines(text):
            self.assertIn(line, combined, line)
        self.assertGreaterEqual(len("".join(plan.values()).encode("utf-8")),
                                len(text.encode("utf-8")))

    def test_an_unreadable_import_is_a_notice_and_its_line_is_kept(self):
        path = self.source("AGENTS.md", "# Fixture\n\n@shared/absent.md\n\n## Testing\n\nYes.\n")
        files, notices = importer.plan(path, today="2026-09-22")
        self.assertEqual(notices, ["@shared/absent.md does not resolve to a readable file; "
                                   "its line was kept"])
        self.assertIn("@shared/absent.md", written(files)["rules/project-fixture-preamble.md"])

    def test_a_file_of_no_recognised_kind_is_refused(self):
        with self.assertRaisesRegex(ValueError, "import reads CLAUDE.md"):
            importer.kind_of(self.root / "notes.md")

    def test_a_name_is_slugged_and_defaults_to_the_directory_or_the_mdc_stem(self):
        self.assertEqual(importer.slug("Release & Upkeep!"), "release-upkeep")
        self.assertEqual(importer.slug("403 handling"), "rule-403-handling")
        claude = self.source("CLAUDE.md", CLAUDE)
        self.assertEqual(importer.default_name(claude, "claude"), "project-fixture")
        mdc = self.source("types.mdc", MDC, subdir="project-fixture/.cursor/rules")
        self.assertEqual(importer.default_name(mdc, "mdc"), "types")


class ImportCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._environ)))
        isolate_home(self.home)
        self.project = Path(self.tmp.name) / "project-fixture"
        self.project.mkdir()
        self.source = self.project / "CLAUDE.md"
        self.source.write_text(CLAUDE, encoding="utf-8")
        (self.project / "shared").mkdir()
        (self.project / "shared" / "style.md").write_text("# Style\n\nTwo spaces.\n", encoding="utf-8")
        self.configure()

    def configure(self, **overrides):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(CFG, **overrides)), encoding="utf-8")

    def run_import(self, dry=False, root=None, name=None, path=None):
        return harness.cmd_import(harness.argparse.Namespace(
            path=str(path or self.source), root=root and str(root), name=name, dry_run=dry))

    def default_root(self):
        return self.home / ".config" / "agent-harness" / "imported" / "project-fixture"

    def user_config(self):
        return json.loads((self.home / ".config" / "agent-harness" / "config.json").read_text())

    def test_a_dry_run_prints_the_plan_and_the_sync_projection_and_writes_no_rule(self):
        with loud() as out:
            self.assertEqual(self.run_import(dry=True), 0)
        printed = out.getvalue()
        self.assertIn("write   " + str(self.default_root() / "rules" / "testing.md"), printed)
        self.assertIn("DRY RUN", printed)
        self.assertIn("Re-run without --dry-run to write this plan.", printed)
        self.assertFalse(self.default_root().exists())
        self.assertEqual(self.user_config().get("primitive_roots", []), [])

    def test_the_first_run_prints_and_the_second_writes_and_registers_the_root(self):
        with loud() as out:
            self.assertEqual(self.run_import(), 0)
        self.assertIn("Re-run without --dry-run", out.getvalue())
        self.assertFalse(self.default_root().exists())
        with loud() as out:
            self.assertEqual(self.run_import(), 0)
        rules = sorted(p.name for p in (self.default_root() / "rules").glob("*.md"))
        self.assertEqual(rules, ["commands.md", "project-fixture-preamble.md", "review.md",
                                 "style.md", "testing.md"])
        self.assertIn("Every change carries a test.",
                      (self.default_root() / "rules" / "testing.md").read_text())
        self.assertEqual(self.user_config()["primitive_roots"], [str(self.default_root())])
        self.assertIn("wrote   5 rule(s)", out.getvalue())
        state = json.loads((self.home / ".local" / "state" / "agent-harness" / "imports.json").read_text())
        self.assertEqual(state["pending"], {})

    def test_a_dry_run_counts_as_the_first_run_so_the_next_one_writes(self):
        with loud():
            self.assertEqual(self.run_import(dry=True), 0)
            self.assertEqual(self.run_import(), 0)
        self.assertTrue((self.default_root() / "rules" / "testing.md").is_file())

    def test_a_changed_source_reprints_rather_than_writing_the_plan_it_never_showed(self):
        with loud():
            self.assertEqual(self.run_import(dry=True), 0)
        self.source.write_text(CLAUDE + "\n## Security\n\nReport privately.\n", encoding="utf-8")
        with loud() as out:
            self.assertEqual(self.run_import(), 0)
        self.assertIn("Re-run without --dry-run", out.getvalue())
        self.assertFalse(self.default_root().exists())

    def test_a_file_the_ownership_journal_owns_is_refused_with_its_record(self):
        state = self.home / ".local" / "state" / "agent-harness"
        state.mkdir(parents=True)
        (state / "ownership.json").write_text(json.dumps({"schema_version": 1, "files": {
            str(self.source.resolve()): {"kind": "generated", "prior": None,
                                         "applied": CLAUDE}}}), encoding="utf-8")
        with loud() as out:
            self.assertEqual(self.run_import(), 2)
        printed = out.getvalue()
        self.assertIn("owned: " + str(self.source.resolve()), printed)
        self.assertIn('"kind": "generated"', printed)
        self.assertIn("import refused: nothing was written", printed)
        self.assertFalse(self.default_root().exists())

    def test_a_name_the_new_root_shares_with_another_root_is_refused_before_writing(self):
        root = Path(self.tmp.name) / "mine"
        skill = root / "skills" / "sandbox" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# my own sandbox skill\n", encoding="utf-8")
        with loud() as out:
            self.assertEqual(self.run_import(root=root), 2)
        printed = out.getvalue()
        self.assertIn("collision: skill 'sandbox' is defined in primitives/skills/sandbox/SKILL.md",
                      printed)
        self.assertIn(str(skill), printed)
        self.assertIn("import refused: nothing was written", printed)
        self.assertFalse((root / "rules").exists())

    def test_the_repository_primitives_directory_is_never_a_target(self):
        with self.assertRaisesRegex(SystemExit, "external primitive root"):
            self.run_import(root=REPO / "primitives")
        with self.assertRaisesRegex(SystemExit, "no such file"):
            self.run_import(path=self.project / "absent" / "CLAUDE.md")

    def test_a_registered_rules_only_root_still_resolves_stances(self):
        # The root an import registers carries no `stances/`; sync must not fail on that.
        with loud():
            self.assertEqual(self.run_import(dry=True), 0)
            self.assertEqual(self.run_import(), 0)
        cfg = harness.load_config()
        self.assertEqual(cfg["primitive_roots"], [str(self.default_root())])
        self.assertIn("testing", harness.resolve_stances(cfg))


if __name__ == "__main__":
    unittest.main()
