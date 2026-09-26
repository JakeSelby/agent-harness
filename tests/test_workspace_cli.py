# SPDX-License-Identifier: MIT
"""`citizen workspace create|list|open` and the `workspaces_dir` config key.

Every run is a subprocess under a temporary HOME, with synthetic workspaces beside it, so no real
configuration, workspace or session store is read or written.
"""
import importlib.machinery
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "bin" / "harness"
loader = importlib.machinery.SourceFileLoader("harness", str(CLI))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)


class CoerceTests(unittest.TestCase):
    def test_an_absolute_path_is_accepted(self):
        self.assertEqual(harness.coerce_config_value("workspaces_dir", "/srv/workspaces"), "/srv/workspaces")

    def test_a_tilde_path_is_expanded(self):
        value = harness.coerce_config_value("workspaces_dir", "~/workspaces")
        self.assertTrue(Path(value).is_absolute())
        self.assertFalse(value.startswith("~"))

    def test_a_relative_or_empty_path_is_refused(self):
        for value in ("workspaces", ""):
            with self.subTest(value=value), self.assertRaises(SystemExit) as caught:
                harness.coerce_config_value("workspaces_dir", value)
            self.assertIn("absolute", str(caught.exception))

    def test_the_refusal_for_an_unknown_key_names_it(self):
        with self.assertRaises(SystemExit) as caught:
            harness.coerce_config_value("workspace_dir", "/x")
        self.assertIn("workspaces_dir", str(caught.exception))


class CliFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.home = self.root / "home"
        (self.home / ".config" / "agent-harness").mkdir(parents=True)
        self.dir = self.root / "ws"
        self.dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, name):
        path = self.root / "repos" / name
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def workspace(self, name, *paths):
        (self.dir / (name + ".code-workspace")).write_text(
            "{\n  // synthetic\n  \"folders\": [%s],\n}\n" % ", ".join(
                json.dumps({"path": p}) for p in paths))

    def run_cli(self, *argv, cwd=None):
        env = dict(without_harness_vars(), HOME=str(self.home), HARNESS_HOME=str(self.home))
        return subprocess.run([sys.executable, str(CLI)] + list(argv), capture_output=True,
                              text=True, env=env, cwd=cwd or str(self.root))

    def configure(self):
        done = self.run_cli("config", "set", "workspaces_dir", str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)


class ConfigSetTests(CliFixture):
    def test_config_set_writes_the_key_and_get_reads_it_back(self):
        self.configure()
        cfg = json.loads((self.home / ".config" / "agent-harness" / "config.json").read_text())
        self.assertEqual(cfg["workspaces_dir"], str(self.dir))
        self.assertEqual(self.run_cli("config", "get", "workspaces_dir").stdout.strip(), str(self.dir))

    def test_config_set_refuses_a_relative_path_and_writes_nothing(self):
        done = self.run_cli("config", "set", "workspaces_dir", "relative/ws")
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((self.home / ".config" / "agent-harness" / "config.json").exists())


class ListTests(CliFixture):
    def test_unset_says_how_to_set_it_and_exits_one(self):
        done = self.run_cli("workspace", "list")
        self.assertEqual(done.returncode, 1)
        self.assertIn("citizen config set workspaces_dir", done.stderr)

    def test_members_sizes_shared_folders_and_ignored_overrides(self):
        a, b, c = self.repo("a"), self.repo("b"), self.repo("c")
        Path(a, "CLAUDE.md").write_text("x" * 1500)
        self.workspace("demo", a, b, str(self.root / "gone"))
        self.workspace("other", b, c)
        self.workspace("third", c, a)
        (self.dir / "overrides.json").write_text(json.dumps({a: "demo", c: "ghost"}))
        self.configure()
        done = self.run_cli("workspace", "list")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertIn("demo: 2 member(s), 1,500 characters of instructions", out)
        self.assertIn("  3. %s  (missing)" % (self.root / "gone"), out)
        self.assertIn("  %s -> demo (override)" % a, out)
        self.assertIn("  %s -> other (first)" % b, out)
        self.assertIn("  %s -> third (first)" % c, out)
        self.assertIn("  %s -> ghost: no such workspace" % c, out)

    def test_an_unsettled_folder_lists_its_candidates(self):
        shared = self.repo("shared")
        self.workspace("one", shared, self.repo("x"))
        self.workspace("two", shared, self.repo("y"))
        self.configure()
        out = self.run_cli("workspace", "list").stdout
        self.assertIn("%s -> none: candidates one, two" % shared, out)
        self.assertIn("overrides.json", out)


class OpenTests(CliFixture):
    def setUp(self):
        super().setUp()
        self.first, self.second, self.third = self.repo("root"), self.repo("a"), self.repo("b")
        self.workspace("demo", self.first, self.second, str(self.root / "gone"), self.third)
        self.configure()

    def dry(self, *extra):
        done = self.run_cli("workspace", "open", "demo", "--dry-run", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        cd, command = done.stdout.strip().splitlines()
        return cd, shlex.split(command), done.stderr

    def test_claude_runs_in_the_first_folder_with_one_add_dir_per_other(self):
        cd, command, stderr = self.dry()
        self.assertEqual(cd, "cd " + shlex.quote(self.first))
        self.assertEqual(command, ["HARNESS_WORKSPACE=demo", "claude",
                                   "--add-dir", self.second, "--add-dir", self.third])
        self.assertIn("skipping missing folder", stderr)

    def test_codex_takes_the_first_folder_as_its_working_root(self):
        _, command, _ = self.dry("--codex")
        self.assertEqual(command, ["HARNESS_WORKSPACE=demo", "codex", "-C", self.first,
                                   "--add-dir", self.second, "--add-dir", self.third])

    def test_passthrough_arguments_go_before_the_add_dir_flags(self):
        _, command, _ = self.dry("--", "-p", "which codewords?", "--model", "haiku")
        self.assertEqual(command[1:6], ["claude", "-p", "which codewords?", "--model", "haiku"])
        self.assertEqual(command[6:], ["--add-dir", self.second, "--add-dir", self.third])

    def test_an_unknown_workspace_is_refused(self):
        done = self.run_cli("workspace", "open", "ghost", "--dry-run")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no workspace ghost", done.stderr)

    def test_open_execs_the_runtime_with_the_workspace_in_its_environment(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        report = self.root / "report.json"
        fake = bin_dir / "claude"
        fake.write_text("#!%s\nimport json, os, sys\njson.dump({'cwd': os.getcwd(), 'argv': sys.argv[1:], "
                        "'ws': os.environ.get('HARNESS_WORKSPACE')}, open(%r, 'w'))\n"
                        % (sys.executable, str(report)))
        fake.chmod(0o755)
        env = dict(without_harness_vars(), HOME=str(self.home), HARNESS_HOME=str(self.home),
                   PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        done = subprocess.run([sys.executable, str(CLI), "workspace", "open", "demo", "--", "hi"],
                              capture_output=True, text=True, env=env, cwd=str(self.root))
        self.assertEqual(done.returncode, 0, done.stderr)
        seen = json.loads(report.read_text())
        self.assertEqual(seen, {"cwd": self.first, "ws": "demo",
                                "argv": ["hi", "--add-dir", self.second, "--add-dir", self.third]})


class CreateTests(CliFixture):
    def test_create_writes_the_folders_in_order_and_links_each_session_key(self):
        a, b = self.repo("a"), self.repo("b")
        done = self.run_cli("workspace", "create", "pair", a, b, "--no-harness", cwd=str(self.dir))
        self.assertEqual(done.returncode, 0, done.stderr)
        from harness_core import workspaces
        parsed = workspaces.parse_workspace(str(self.dir / "pair.code-workspace"))
        self.assertEqual(parsed["members"], [a, b])
        projects = self.home / ".claude" / "projects"
        for folder in (a, b):
            key = projects / folder.replace("/", "-")
            self.assertTrue(key.is_symlink())
            self.assertEqual(key.resolve(), (self.home / ".claude" / "workspaces" / "pair").resolve())

    def test_create_refuses_to_overwrite_without_force(self):
        a = self.repo("a")
        self.run_cli("workspace", "create", "pair", a, "--no-harness", cwd=str(self.dir))
        done = self.run_cli("workspace", "create", "pair", a, "--no-harness", cwd=str(self.dir))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--force", done.stderr)


if __name__ == "__main__":
    unittest.main()
