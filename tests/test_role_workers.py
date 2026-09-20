"""Constrained workers preserve shared policy without importing native authority."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_harness import CFG, REPO, harness
from harness_core import catalog, workers, reconcile, lifecycle

PLAN = """# Fixture plan

> Build the requested fixture. Keep the change scoped.

## At a glance
- Outcome: a verified fixture.

## System design
```mermaid
flowchart LR
  A --> B
```

## Steps
1. Implement the fixture.
   *Exit:* tests pass.

## Decisions for the reviewer
None.

## Risks
- A failed check blocks publication.

---
# Addendum
Fixture details.
"""


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / "project"
        self.workspace.mkdir()
        self.state = self.base / "state"
        self.cfg = copy.deepcopy(CFG)
        self.env = {"HOME": str(self.base / "user"), "PATH": os.environ["PATH"]}
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()

    def fake(self, output=PLAN, exit_code=0):
        def execute(command, prompt, env, cwd, run_dir, timeout):
            if "--output-format" in command:
                (run_dir / "stdout.log").write_text(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": output}))
            else:
                Path(command[command.index("-o") + 1]).write_text(output)
            return exit_code
        return execute

    def run_worker(self, role="planner", runtime="codex", **kwargs):
        with patch.object(workers.shutil, "which", return_value="/native/cli"), \
             patch.object(workers.subprocess, "check_output", return_value="fixture-version"):
            return workers.run(REPO, self.cfg, runtime, role, self.workspace, "Inspect the fixture", self.state,
                               model="fixture-model", **kwargs)

    def test_shared_stances_and_role_body_reach_both_workers(self):
        for runtime in workers.RUNTIMES:
            fields, binding, instructions = workers.resolve(REPO, self.cfg, runtime, "reviewer", "fixture-model")
            self.assertEqual(fields["authority"], "read-only")
            self.assertEqual(binding["model"], "fixture-model")
            self.assertIn(catalog.role_contract(REPO, "reviewer")[1], instructions)
            self.assertIn((REPO / "primitives/stances/testing/required.md").read_text(), instructions)
        self.cfg["stances"]["testing"] = "off"
        self.assertIn((REPO / "primitives/stances/testing/off.md").read_text(), workers.resolve(REPO, self.cfg, "codex", "reviewer", "fixture-model")[2])

    def test_resolver_fails_before_launch_for_off_unknown_and_unconstrained_roles(self):
        for role in ("../planner", "missing", "builder"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                workers.resolve(REPO, self.cfg, "codex", role, "fixture-model")
        self.cfg["stances"]["delegation"] = "off"
        with self.assertRaisesRegex(ValueError, "delegation is off"):
            workers.resolve(REPO, self.cfg, "codex", "reviewer", "fixture-model")

    def test_a_role_runs_on_its_class_and_an_unmapped_class_is_never_guessed(self):
        self.assertEqual(workers.resolve(REPO, self.cfg, "claude-code", "reviewer")[1]["model"], "opus")
        self.assertEqual(workers.resolve(REPO, self.cfg, "claude-code", "reviewer", "chosen")[1]["model"], "chosen")
        self.assertEqual(workers.resolve(REPO, self.cfg, "codex", "reviewer")[1]["model"], "gpt-5.6-sol")
        self.cfg["tiers"] = {"codex": {"strong": "next-strong"}}
        self.assertEqual(workers.resolve(REPO, self.cfg, "codex", "reviewer")[1]["model"], "next-strong")
        self.cfg["role_bindings"] = {"codex": {"reviewer": {"model": "inherit"}}}
        with self.assertRaisesRegex(ValueError, "parent session"):
            workers.resolve(REPO, self.cfg, "codex", "reviewer")
        self.cfg["role_bindings"] = {"codex": {"reviewer": {"model": "selected-model"}}}
        self.assertEqual(workers.resolve(REPO, self.cfg, "codex", "reviewer")[1]["model"], "selected-model")
        self.cfg["role_bindings"]["codex"]["reviewer"]["sandbox_mode"] = "danger-full-access"
        with self.assertRaisesRegex(ValueError, "model and effort only"):
            workers.resolve(REPO, self.cfg, "codex", "reviewer")

    def test_role_authority_typo_is_not_projected_as_workspace_write(self):
        with patch.object(catalog, "frontmatter", return_value=({"name": "reviewer", "authority": "read-onyl"}, "body")):
            with self.assertRaisesRegex(ValueError, "authority"):
                catalog.role_projection(REPO, "codex", REPO / "primitives/roles/reviewer.md")

    def test_worker_environment_drops_parent_and_loader_overrides(self):
        env = workers.environment(dict(self.env, CODEX_HOME="/unsafe", CLAUDE_CODE_SAFE_MODE="0",
                                       NODE_OPTIONS="--require unsafe", PYTHONPATH="/unsafe", HARNESS_STANCE_DELEGATION="off"), self.base)
        for key in ("CODEX_HOME", "CLAUDE_CODE_SAFE_MODE", "NODE_OPTIONS", "PYTHONPATH", "HARNESS_STANCE_DELEGATION"):
            self.assertNotIn(key, env)
        self.assertNotEqual(env["HOME"], self.env["HOME"])

    def test_planner_publication_and_status_in_both_adapters(self):
        for runtime in workers.RUNTIMES:
            with patch.object(workers, "execute", side_effect=self.fake()):
                result = self.run_worker(runtime=runtime, artifact=runtime + ".md")
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(Path(result["artifact"]).read_text(), PLAN)
            self.assertEqual(Path(result["result_path"]).read_text(), PLAN)
            self.assertEqual(workers.status(self.state, result["id"])[0]["runtime_version"], "fixture-version")
            self.assertEqual(result["qualification"], "unqualified")

    def test_read_only_role_cannot_request_artifact(self):
        with self.assertRaisesRegex(ValueError, "artifact-write"):
            self.run_worker(role="reviewer", artifact="unexpected.md")
        with self.assertRaisesRegex(ValueError, "artifact-write"):
            self.run_worker()

    def test_invalid_or_failed_output_is_never_published(self):
        for text, code in (("", 0), ("not a plan", 0), (PLAN, 1), ("```markdown\n" + PLAN + "```", 0)):
            with patch.object(workers, "execute", side_effect=self.fake(text, code)):
                result = self.run_worker(artifact="failure.md")
            self.assertEqual(result["status"], "failed")
            self.assertFalse((self.workspace / ".agent-harness/plans/failure.md").exists())

    def test_paths_symlinks_and_existing_artifacts_are_refused_before_execution(self):
        for filename in ("../escape.md", "/outside.md", "nested/work.md", "text.txt"):
            with patch.object(workers, "execute") as execute:
                result = self.run_worker(artifact=filename)
            self.assertEqual(result["status"], "failed")
            execute.assert_not_called()
        (self.workspace / ".agent-harness").symlink_to(self.base, target_is_directory=True)
        with patch.object(workers, "execute") as execute:
            result = self.run_worker(artifact="escape.md")
        self.assertEqual(result["status"], "failed")
        execute.assert_not_called()
        (self.workspace / ".agent-harness").unlink()
        with workers.artifact_slot(self.workspace, "existing.md") as slot:
            workers.publish(slot, "original")
        with patch.object(workers, "execute") as execute:
            result = self.run_worker(artifact="existing.md")
        self.assertEqual(result["status"], "failed")
        execute.assert_not_called()
        self.assertEqual((self.workspace / ".agent-harness/plans/existing.md").read_text(), "original")

    def test_concurrent_destination_creation_is_preserved(self):
        with workers.artifact_slot(self.workspace, "race.md") as slot:
            path = self.workspace / ".agent-harness/plans/race.md"
            path.write_text("other writer")
            with self.assertRaises(FileExistsError):
                workers.publish(slot, PLAN)
            self.assertEqual(path.read_text(), "other writer")
        self.assertEqual([p.name for p in path.parent.iterdir()], ["race.md"])

    def test_timeout_and_cancellation_leave_no_artifact(self):
        for error, status in ((subprocess.TimeoutExpired("fixture", 1), "timed-out"), (KeyboardInterrupt(), "cancelled")):
            with patch.object(workers, "execute", side_effect=error):
                result = self.run_worker(artifact="interrupted.md")
            self.assertEqual(result["status"], status)
            self.assertFalse((self.workspace / ".agent-harness/plans/interrupted.md").exists())

    def test_status_rejects_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "worker id"):
            workers.status(self.state, "../../outside")

    def test_native_hooks_route_constrained_roles_to_workers(self):
        with patch.object(lifecycle, "selected", return_value="session-model"):
            for runtime, tool, inputs in (("codex", "spawn_agent", {"agent_type": "reviewer", "message": "review"}),
                                           ("claude-code", "Agent", {"subagent_type": "planner", "prompt": "plan"})):
                decision = lifecycle.dispatch(runtime, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inputs})["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("harness role run", decision["permissionDecisionReason"])
                self.assertNotIn("--model", decision["permissionDecisionReason"])
            # Only an adapter that maps no model for the role's class is told to pass the session's.
            with patch.object(catalog, "role_binding", return_value={}):
                reason = lifecycle.dispatch("codex", {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent",
                    "tool_input": {"agent_type": "reviewer", "message": "review"}})["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("--model <session-model>", reason)

    def test_execute_passes_brief_as_data_and_records_logs(self):
        run_dir = self.base / "run"
        run_dir.mkdir()
        prompt = "A literal brief; never an executable shell string."
        code = workers.execute([sys.executable, "-c", "import sys; print(sys.stdin.read()); print('diagnostic', file=sys.stderr)"],
                               prompt, dict(os.environ), self.workspace, run_dir, 5)
        self.assertEqual(code, 0)
        self.assertIn(prompt, (run_dir / "stdout.log").read_text())
        self.assertIn("diagnostic", (run_dir / "stderr.log").read_text())

    def test_execute_timeout_terminates_and_reaps_the_native_process(self):
        run_dir = self.base / "run"
        run_dir.mkdir()
        with self.assertRaises(subprocess.TimeoutExpired):
            workers.execute([sys.executable, "-u", "-c", "import os,time; print(os.getpid()); time.sleep(60)"],
                            "brief", dict(os.environ), self.workspace, run_dir, 1)
        pid = int((run_dir / "stdout.log").read_text().strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work = self.base / "work"
        self.work.mkdir()
        self.native = self.base / "native"
        self.native.mkdir()
        self.original = {"CODEX_HOME": str(self.native), "HOME": str(self.base / "user")}
        self.env = {}

    def prepare(self, runtime="codex"):
        return workers.adapter(REPO, runtime).prepare("/native/cli", self.work, REPO, self.base, [], "shared instructions",
                                                    {"model": "fixture-model", "model_reasoning_effort": "low"}, self.original, self.env)

    def test_codex_ignores_native_tools_hooks_permissions_and_retains_provider(self):
        self.original["FIXTURE_PROVIDER_AUTH"] = "private-fixture-value"
        (self.native / "auth.json").write_text("{}")
        config = {"model_provider": "fixture", "approval_policy": "on-request", "sandbox_mode": "danger-full-access",
                  "mcp_servers": {"unsafe": {"command": "unsafe"}}, "hooks": {"unsafe": True},
                  "model_providers": {"fixture": {"name": "Fixture", "base_url": "https://example.invalid", "env_key": "FIXTURE_PROVIDER_AUTH"}}}
        (self.native / "config.toml").write_text(reconcile.tomlkit.dumps(config))
        command = self.prepare()
        generated = reconcile.tomlkit.parse((self.work / "codex/config.toml").read_text()).unwrap()
        self.assertEqual(generated["sandbox_mode"], "read-only")
        self.assertEqual(generated["approval_policy"], "never")
        self.assertEqual(generated["model"], "fixture-model")
        self.assertEqual(generated["model_provider"], "fixture")
        self.assertEqual(generated["mcp_servers"], {})
        self.assertFalse(generated["agents"]["enabled"])
        self.assertFalse(generated["apps"]["_default"]["enabled"])
        for feature in ("image_generation", "remote_plugin", "multi_agent", "apps", "goals"):
            self.assertFalse(generated["features"][feature])
        self.assertFalse(generated["allow_login_shell"])
        self.assertNotIn("hooks", generated)
        self.assertIn("--strict-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertTrue((self.work / "codex/auth.json").is_symlink())
        self.assertNotIn(self.original["FIXTURE_PROVIDER_AUTH"], (self.work / "codex/config.toml").read_text())
        self.assertEqual(self.env["FIXTURE_PROVIDER_AUTH"], self.original["FIXTURE_PROVIDER_AUTH"])

    def test_inline_provider_credentials_fail_closed(self):
        (self.native / "config.toml").write_text(reconcile.tomlkit.dumps({"model_provider": "fixture",
            "model_providers": {"fixture": {"http_headers": {"Authorization": "fixture"}}}}))
        with self.assertRaisesRegex(ValueError, "environment references"):
            self.prepare()

    def test_claude_preserves_auth_and_exposes_only_read_tools(self):
        self.original["CLAUDE_CONFIG_DIR"] = str(self.native)
        self.original["USER"] = "fixture-user"
        command = self.prepare("claude-code")
        self.assertEqual(self.env["CLAUDE_CONFIG_DIR"], str(self.native))
        self.assertEqual(self.env["USER"], "fixture-user")
        self.assertEqual(self.env["HOME"], self.original["HOME"])
        self.assertEqual(command[command.index("--tools") + 1], "Read,Grep,Glob")
        for flag in ("--safe-mode", "--restricted", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
            self.assertIn(flag, command)
        self.assertNotIn("--bare", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertEqual(command[command.index("--permission-mode") + 1], "dontAsk")

    def test_provider_credential_reference_cannot_restore_execution_overrides(self):
        (self.native / "config.toml").write_text(reconcile.tomlkit.dumps({"model_provider": "fixture",
            "model_providers": {"fixture": {"env_key": "NODE_OPTIONS"}}}))
        self.original["NODE_OPTIONS"] = "--require unsafe"
        with self.assertRaisesRegex(ValueError, "execution settings"):
            self.prepare()
        self.assertNotIn("NODE_OPTIONS", self.env)

    def test_claude_error_envelope_is_not_a_result(self):
        (self.work / "stdout.log").write_text(json.dumps({"type": "result", "subtype": "error", "is_error": True, "result": "failure"}))
        with self.assertRaisesRegex(ValueError, "successful result"):
            workers.adapter(REPO, "claude-code").result(self.base, self.work)


if __name__ == "__main__":
    unittest.main()
