# SPDX-License-Identifier: MIT
"""Sync renders the Claude agent definitions from the resolved cost variant.

0.10.0 symlinked `claude/agents/*.md` into the Claude home, so a cost variant could not reach
the native file. These tests hold the replacement honest: `balanced` renders exactly the
committed projection, another variant moves only the roles its rows name, a user's binding
still wins, and a machine synced by the previous release migrates without losing anything the
user put there.
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

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

from harness_core import catalog  # noqa: E402

ROLES = sorted(p.stem for p in (REPO / "primitives" / "roles").glob("*.md"))
COMMITTED = REPO / "claude" / "agents"


def fields(text):
    """The frontmatter of a rendered agent definition as a flat mapping."""
    return {k.strip(): v.strip() for k, _, v in
            (line.partition(":") for line in text.split("---", 2)[1].strip().splitlines())}


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


class RenderedAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self._old_environ = dict(os.environ)
        os.environ["HOME"] = str(self.home)
        for key in list(os.environ):
            if key.startswith("HARNESS_"):
                del os.environ[key]
        os.environ["HARNESS_QUIET"] = "1"
        self.agents = self.home / ".claude" / "agents"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_environ)
        self.tmp.cleanup()

    def configure(self, **overrides):
        config = json.loads((REPO / "config.example.json").read_text())
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def sync(self, dry=False, adopt=False):
        return harness.cmd_sync(harness.argparse.Namespace(
            dry_run=dry, adopt=adopt, adopt_codex=False, print_only=False))

    def rendered(self, role):
        return (self.agents / (role + ".md")).read_text(encoding="utf-8")

    def link_as_0_10_0(self):
        """The previous release's install: one managed symlink per role, recorded in the manifest."""
        manifest = {"version": 1, "repo": str(REPO)}
        harness.link_dir_files(COMMITTED, self.agents, manifest, False, False, [])
        harness.write_json_atomic(harness.manifest_path(), manifest)
        return manifest

    def test_balanced_renders_the_committed_projection_byte_for_byte(self):
        self.assertEqual(self.sync(), 0)
        for role in ROLES:
            path = self.agents / (role + ".md")
            self.assertTrue(path.is_file() and not path.is_symlink(), msg=role)
            self.assertEqual(self.rendered(role),
                             (COMMITTED / (role + ".md")).read_text(encoding="utf-8"), msg=role)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(harness._diff_lines(), [])

    def test_a_frugal_row_moves_the_gatherer_and_leaves_a_fixed_role_alone(self):
        self.configure(stances={"cost": "frugal"})
        self.assertEqual(self.sync(), 0)
        gatherer = fields(self.rendered("gatherer"))
        self.assertEqual(gatherer["model"], "sonnet")
        self.assertEqual(gatherer["effort"], "low")
        self.assertEqual(self.rendered("reviewer"),
                         (COMMITTED / "reviewer.md").read_text(encoding="utf-8"))

    def test_without_a_tiered_delegation_the_row_changes_effort_and_not_the_model(self):
        self.configure(stances={"cost": "frugal", "delegation": "session-model"})
        self.assertEqual(self.sync(), 0)
        self.assertEqual(fields(self.rendered("gatherer"))["model"],
                         fields((COMMITTED / "gatherer.md").read_text(encoding="utf-8"))["model"])
        self.assertEqual(fields(self.rendered("builder"))["effort"], "low")

    def test_a_user_binding_beats_the_cost_row(self):
        self.configure(stances={"cost": "frugal"},
                       role_bindings={"claude-code": {"gatherer": {"model": "haiku"}}})
        self.assertEqual(self.sync(), 0)
        self.assertEqual(fields(self.rendered("gatherer"))["model"], "haiku")
        self.assertEqual(fields(self.rendered("gatherer"))["effort"], "low")

    def test_a_linked_install_migrates_to_generated_files(self):
        self.link_as_0_10_0()
        self.assertTrue((self.agents / "gatherer.md").is_symlink())
        self.assertEqual(self.sync(), 0)
        for role in ROLES:
            path = self.agents / (role + ".md")
            self.assertFalse(path.is_symlink(), msg=role)
            self.assertEqual(path.read_text(encoding="utf-8"),
                             (COMMITTED / (role + ".md")).read_text(encoding="utf-8"), msg=role)
        manifest = harness.read_json(harness.manifest_path()) or {}
        self.assertEqual([l for l in manifest.get("links", [])
                          if Path(l["path"]).parent == self.agents], [])
        self.assertEqual(harness._diff_lines(), [])

    def test_a_redirected_agent_link_is_preserved_and_reported(self):
        self.link_as_0_10_0()
        mine = self.home / "my-gatherer.md"
        mine.write_text("mine", encoding="utf-8")
        link = self.agents / "gatherer.md"
        link.unlink()
        link.symlink_to(mine)
        with loud() as out:
            self.assertEqual(self.sync(), 2)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.read_text(encoding="utf-8"), "mine")
        self.assertIn("gatherer.md", out.getvalue())
        self.assertIn("preserved", out.getvalue())

    def test_a_dry_run_names_the_change_and_writes_nothing(self):
        self.configure(stances={"cost": "frugal"})
        with loud() as out:
            self.assertEqual(self.sync(dry=True), 0)
        printed = [l for l in out.getvalue().splitlines() if l.startswith("  agent ")]
        self.assertTrue(any("gatherer" in l and "sonnet" in l and "low" in l for l in printed), printed)
        self.assertFalse(any("reviewer" in l for l in printed), printed)
        self.assertFalse((self.agents / "gatherer.md").exists())

    def test_a_balanced_dry_run_names_no_role(self):
        with loud() as out:
            self.assertEqual(self.sync(dry=True), 0)
        self.assertEqual([l for l in out.getvalue().splitlines() if l.startswith("  agent ")], [])

    def test_uninstall_removes_the_generated_definitions(self):
        self.assertEqual(self.sync(), 0)
        harness.cmd_uninstall(harness.argparse.Namespace())
        for role in ROLES:
            path = self.agents / (role + ".md")
            self.assertFalse(path.exists() or path.is_symlink(), msg=role)

    def test_a_hand_written_definition_is_never_replaced_without_adopt(self):
        self.agents.mkdir(parents=True)
        (self.agents / "gatherer.md").write_text("mine", encoding="utf-8")
        self.assertEqual(self.sync(), 2)
        self.assertEqual(self.rendered("gatherer"), "mine")
        self.assertEqual(self.sync(adopt=True), 0)
        self.assertEqual(self.rendered("gatherer"),
                         (COMMITTED / "gatherer.md").read_text(encoding="utf-8"))
        harness.cmd_uninstall(harness.argparse.Namespace())
        self.assertEqual((self.agents / "gatherer.md").read_text(encoding="utf-8"), "mine")

    def test_the_committed_projection_is_still_what_generate_checks(self):
        self.assertEqual(catalog.projection_drift(REPO), [])


class RoleOverrideTests(unittest.TestCase):
    """The precedence rule itself, without a sync around it."""

    def test_a_row_without_a_class_only_sets_effort(self):
        self.assertEqual(catalog.role_overrides(REPO, "claude-code", {"effort": "high"}),
                         {"effort": "high"})

    def test_a_fixed_role_row_carries_neither_cell(self):
        row = {"class": None, "effort": None, "budget_tool_calls": 30}
        self.assertEqual(catalog.role_overrides(REPO, "claude-code", row), {})

    def test_the_class_resolves_through_the_adapter_table_and_never_a_model_name(self):
        tiers = json.loads((REPO / "adapters" / "claude-code" / "bindings.json").read_text())["tiers"]
        out = catalog.role_overrides(REPO, "claude-code", {"class": "standard"})
        self.assertEqual(out["model"], tiers["standard"])

    def test_the_user_binding_is_applied_last(self):
        out = catalog.role_overrides(REPO, "claude-code", {"class": "standard", "effort": "low"},
                                     binding={"model": "inherit", "effort": "high"})
        self.assertEqual(out, {"model": "inherit", "effort": "high"})

    def test_codex_takes_its_own_effort_key(self):
        out = catalog.role_overrides(REPO, "codex", {"effort": "medium"})
        self.assertEqual(out, {"model_reasoning_effort": "medium"})


if __name__ == "__main__":
    unittest.main()
