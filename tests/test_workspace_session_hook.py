# SPDX-License-Identifier: MIT
"""The workspace SessionStart hook: its own entry, which members it supplies, and how.

The hook runs through the real adapter as a subprocess, under a temporary HOME whose config
points `workspaces_dir` at a synthetic workspace. A member counts as loaded natively only when a
real parent process carries it as `--add-dir`, so the tests spawn one and pass its pid as
`CLAUDE_PID`. Run: python3 -m unittest tests.test_workspace_session_hook
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import lifecycle  # noqa: E402

ADAPTERS = {runtime: REPO / "adapters" / runtime / "hook.py" for runtime in ("claude-code", "codex")}
NATIVE_VAR = "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"
MARKER = "# harness:runtime-sessionstart-workspace"
# Variables the developer's own session sets, which would otherwise decide the tests' outcome.
INHERITED = ("CLAUDE_PID", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR", NATIVE_VAR)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(os.path.realpath(self.tmp.name))
        self.home = base / "home"
        self.ws = base / "ws"
        for name in ("root", "member-a", "member-b"):
            (self.ws / name).mkdir(parents=True)
        (self.ws / "member-a" / "CLAUDE.md").write_text("Codeword ALPHA.\n")
        (self.ws / "member-b" / "AGENTS.md").write_text("Codeword BRAVO.\n")
        self.workspace("demo", ["root", "member-a", "member-b"])
        self.configure(str(self.ws))

    def workspace(self, name, folders):
        entries = ",\n".join('    {"path": "%s"}' % folder for folder in folders)
        (self.ws / (name + ".code-workspace")).write_text(
            '{\n  // members, in order\n  "folders": [\n' + entries + ',\n  ],\n}\n')

    def configure(self, directory):
        path = self.home / ".config" / "agent-harness" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"workspaces_dir": directory} if directory else {}))

    def run_hook(self, cwd=None, runtime="claude-code", argument="workspace", **extra):
        env = without_harness_vars()
        for key in INHERITED:
            env.pop(key, None)
        env["HOME"] = str(self.home)
        env.update(extra)
        cwd = str(cwd or self.ws / "root")
        payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": cwd,
                              "session_id": "s"})
        argv = [sys.executable, str(ADAPTERS[runtime])] + ([argument] if argument else [])
        return subprocess.run(argv, input=payload, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=30)

    def context(self, out):
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        if not out.stdout.strip():
            return ""
        data = json.loads(out.stdout)
        return data.get("hookSpecificOutput", {}).get("additionalContext", "")

    def parent(self, *add_dirs):
        """A live process whose arguments carry `--add-dir`, standing in for the runtime."""
        argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        for path in add_dirs:
            argv += ["--add-dir", str(path)]
        proc = subprocess.Popen(argv)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return str(proc.pid)

    def line(self, text, folder):
        found = [row for row in text.splitlines() if row.startswith("- " + str(self.ws / folder) + ":")]
        self.assertEqual(len(found), 1, msg=text)
        return found[0]


class Delivery(Fixture):
    def test_unset_is_silent(self):
        self.configure(None)
        self.assertEqual(self.context(self.run_hook()), "")

    def test_a_folder_in_no_workspace_is_silent(self):
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir(parents=True)
        self.assertEqual(self.context(self.run_hook(cwd=elsewhere)), "")

    def test_a_single_workspace_supplies_every_other_member_inline(self):
        text = self.context(self.run_hook())
        self.assertIn("Workspace demo (decided by: single)", text)
        self.assertIn("supplied by this hook", self.line(text, "member-a"))
        self.assertIn("supplied by this hook", self.line(text, "member-b"))
        self.assertIn("Codeword ALPHA.", text)
        self.assertIn("Codeword BRAVO.", text)
        self.assertNotIn("- " + str(self.ws / "root") + ":", text)
        self.assertNotIn("request_directory", text)

    def test_an_ambiguous_folder_names_its_candidates_and_the_overrides_file(self):
        # The session's folder is first in none of the three, so no rule decides.
        self.workspace("demo", ["member-a", "root", "member-b"])
        self.workspace("other", ["member-b", "root"])
        self.workspace("third", ["member-a", "root"])
        text = self.context(self.run_hook())
        self.assertIn("demo, other, third", text)
        self.assertIn(str(self.ws / "overrides.json"), text)
        self.assertNotIn("Codeword", text)

    def test_a_missing_member_is_listed_and_skipped(self):
        self.workspace("demo", ["root", "member-a", "gone"])
        text = self.context(self.run_hook())
        self.assertIn(str(self.ws / "gone") + ": missing", text)

    def test_the_block_names_where_the_path_scoped_rules_are(self):
        rules = self.ws / "member-a" / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "scoped.md").write_text("---\npaths:\n  - src/**\n---\nScoped SECRETWORD.\n")
        text = self.context(self.run_hook())
        self.assertIn(str(rules / "scoped.md"), text)
        self.assertNotIn("SECRETWORD", text)

    def test_past_the_inline_limit_the_instructions_go_to_a_bundle_file(self):
        (self.ws / "member-a" / "CLAUDE.md").write_text("filler line\n" * 900 + "Codeword ALPHA.\n")
        text = self.context(self.run_hook())
        bundle = self.home / ".local" / "state" / "agent-harness" / "workspaces" / "demo.md"
        self.assertLess(len(text), 9000)
        self.assertIn(str(bundle), text)
        self.assertIn("before you answer or take any other action", text)
        self.assertNotIn("Codeword", text)
        self.assertIn("Codeword ALPHA.", bundle.read_text())
        self.assertIn("Codeword BRAVO.", bundle.read_text())
        self.assertEqual([p.name for p in bundle.parent.iterdir()], ["demo.md"])

    def test_the_desktop_app_is_told_to_request_a_folder_on_first_use(self):
        text = self.context(self.run_hook(CLAUDE_CODE_ENTRYPOINT="claude-desktop"))
        self.assertIn("request_directory", text)
        self.assertIn("do not request them all now", text)

    def test_a_broken_workspace_file_never_fails_the_session(self):
        (self.ws / "demo.code-workspace").write_text("{ not json")
        out = self.run_hook()
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        self.assertEqual(self.context(out), "")

    def test_a_malformed_config_never_fails_the_session(self):
        (self.home / ".config" / "agent-harness" / "config.json").write_text("[1, 2")
        self.assertEqual(self.context(self.run_hook()), "")


class NativeSkip(Fixture):
    def test_a_member_the_parent_loads_natively_is_not_supplied_again(self):
        pid = self.parent(self.ws / "member-a", self.ws / "member-b")
        text = self.context(self.run_hook(CLAUDE_PID=pid, **{NATIVE_VAR: "1"}))
        self.assertIn("loaded natively", self.line(text, "member-a"))
        self.assertNotIn("Codeword ALPHA.", text)

    def test_an_agents_only_member_is_supplied_even_when_added(self):
        pid = self.parent(self.ws / "member-a", self.ws / "member-b")
        text = self.context(self.run_hook(CLAUDE_PID=pid, **{NATIVE_VAR: "1"}))
        self.assertIn("supplied by this hook", self.line(text, "member-b"))
        self.assertIn("Codeword BRAVO.", text)

    def test_without_the_variable_an_added_member_is_still_supplied(self):
        pid = self.parent(self.ws / "member-a", self.ws / "member-b")
        text = self.context(self.run_hook(CLAUDE_PID=pid))
        self.assertIn("supplied by this hook", self.line(text, "member-a"))
        self.assertIn("Codeword ALPHA.", text)

    def test_a_member_not_among_the_parent_arguments_is_supplied(self):
        pid = self.parent(self.ws / "member-b")
        text = self.context(self.run_hook(CLAUDE_PID=pid, **{NATIVE_VAR: "1"}))
        self.assertIn("supplied by this hook", self.line(text, "member-a"))

    def test_a_relative_add_dir_resolves_against_the_session_folder(self):
        pid = self.parent("../member-a")
        text = self.context(self.run_hook(CLAUDE_PID=pid, **{NATIVE_VAR: "1"}))
        self.assertIn("loaded natively", self.line(text, "member-a"))

    def test_codex_is_supplied_every_member_whatever_its_parent_carries(self):
        pid = self.parent(self.ws / "member-a", self.ws / "member-b")
        text = self.context(self.run_hook(runtime="codex", CLAUDE_PID=pid, **{NATIVE_VAR: "1"}))
        self.assertIn("supplied by this hook", self.line(text, "member-a"))
        self.assertIn("Codeword ALPHA.", text)
        self.assertIn("Codeword BRAVO.", text)


class Parsing(unittest.TestCase):
    def setUp(self):
        self.hook = module("harness_workspace_session_test", REPO / "policy" / "hooks" / "workspace-session.py")

    def test_add_dir_takes_several_values_and_the_equals_form(self):
        base = os.path.realpath(tempfile.gettempdir())
        argv = ["-p", "prompt", "--add-dir", "/a", "/b", "--model", "haiku", "--add-dir=/c", "x"]
        self.assertEqual(self.hook.add_dirs(argv, base),
                         [os.path.realpath(p) for p in ("/a", "/b", "/c")])

    def test_a_path_with_a_space_is_matched_in_the_joined_command(self):
        argv = "claude --add-dir /x/my folder --model haiku".split()
        self.assertTrue(self.hook.add_dir_listed("/x/my folder", set(), argv))
        self.assertFalse(self.hook.add_dir_listed("/x/other", set(), argv))

    def test_an_unreadable_parent_has_no_arguments(self):
        self.assertEqual(self.hook.parent_command("not-a-pid"), [])
        self.assertEqual(self.hook.parent_command(None), [])


class Registration(unittest.TestCase):
    def test_both_runtimes_register_a_second_session_start_entry(self):
        for runtime in ADAPTERS:
            with self.subTest(runtime=runtime):
                entries = lifecycle.registration(REPO, runtime)["hooks"]["SessionStart"]
                self.assertEqual(len(entries), 2)
                command = entries[1]["hooks"][0]["command"]
                self.assertTrue(command.endswith(" workspace " + MARKER), msg=command)
                self.assertIn(str(ADAPTERS[runtime]), command)
                self.assertEqual(entries[1]["hooks"][0]["timeout"], 10)

    def test_the_plain_entry_never_runs_the_workspace_hook(self):
        with tempfile.TemporaryDirectory() as temp:
            env = without_harness_vars()
            env["HOME"] = temp
            out = subprocess.run([sys.executable, str(ADAPTERS["claude-code"]), "workspace"],
                                 input=json.dumps({"hook_event_name": "Stop", "cwd": temp}),
                                 env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual((out.returncode, out.stdout), (0, ""))


class Workers(unittest.TestCase):
    """A role worker must not run the user's hooks, so the workspace entry never reaches one."""

    def test_the_claude_worker_reads_no_user_settings(self):
        worker = module("harness_claude_worker_test", REPO / "adapters" / "claude-code" / "worker.py")
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            command = worker.prepare("claude", work, work, work, [], "brief", {"model": "m"},
                                     {"HOME": temp}, {})
        at = command.index("--setting-sources")
        self.assertEqual(command[at + 1], "")

    def test_the_codex_worker_gets_a_fresh_home_with_no_hooks_file(self):
        worker = module("harness_codex_worker_test", REPO / "adapters" / "codex" / "worker.py")
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "work"
            work.mkdir()
            env = {}
            worker.prepare("codex", work, work, work, [], "brief", {"model": "m"},
                           {"HOME": temp}, env)
            home = Path(env["CODEX_HOME"])
            self.assertEqual(home, work / "codex")
            self.assertFalse((home / "hooks.json").exists())


if __name__ == "__main__":
    unittest.main()
