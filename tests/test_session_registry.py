# SPDX-License-Identifier: MIT
"""The session registry: what a running session can actually resolve.

Claude Code loads its agent registry when the session process starts and never reloads it, so
a worker definition on disk is not evidence that a running session can spawn it. A reroute to
a type the session cannot resolve fails the spawn outright, which is worse than not rerouting
at all. The SessionStart policy records the names the registry held; the spawn hook — and the
pricing hook that asks it where a spawn goes — reroutes only to a name in that record.

Run: python3 -m unittest discover tests
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
_loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
harness = importlib.util.module_from_spec(importlib.util.spec_from_loader("harness", _loader))
_loader.exec_module(harness)

SESSION_HOOK = REPO / "claude" / "hooks" / "harness-session.py"
SPAWN_HOOK = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
GUARD_HOOK = REPO / "claude" / "hooks" / "brief-guard.py"
AGENTS = REPO / "claude" / "agents"
WORKERS = ("worker-a", "worker-b", "worker-c")
SESSION = "session-one"


class RegistryCase(unittest.TestCase):
    """A disposable home the hooks resolve their posture, agents and records from."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text(json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5"}}) + "\n")
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True)
        (d / "config.json").write_text(json.dumps({"stances": {"delegation": "tiered"}}))

    def env(self, extra=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}
        env["HOME"] = str(self.home)
        env.update(extra or {})
        return env

    def agents_dir(self, config=None):
        return (Path(config) if config else self.home / ".claude") / "agents"

    def install_workers(self, *names, config=None):
        d = self.agents_dir(config)
        d.mkdir(parents=True, exist_ok=True)
        for name in names or WORKERS:
            (d / (name + ".md")).write_text((AGENTS / (name + ".md")).read_text(encoding="utf-8"))

    def sessions(self):
        return self.home / ".local" / "state" / "agent-harness" / "sessions"

    def record_path(self, session=SESSION):
        return self.sessions() / (session + ".json")

    def record(self, *names, session=SESSION):
        self.sessions().mkdir(parents=True, exist_ok=True)
        self.record_path(session).write_text(json.dumps({"agents": sorted(names), "at": 0}))

    def start(self, source="startup", session=SESSION, env=None):
        payload = {"hook_event_name": "SessionStart", "source": source, "session_id": session,
                   "cwd": str(self.home)}
        out = subprocess.run([sys.executable, str(SESSION_HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True, env=self.env(env), timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        return out

    def spawn(self, tool_input=None, session=SESSION, env=None, hook=None):
        payload = {"tool_name": "Agent", "transcript_path": str(self.transcript),
                   "tool_input": tool_input or {"prompt": "x"}}
        if session is not None:
            payload["session_id"] = session
        out = subprocess.run([sys.executable, str(hook or SPAWN_HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True, env=self.env(env), timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None


class RecordingTests(RegistryCase):
    """Only a new process has a new registry, so only a new process writes the record."""

    def test_startup_records_the_agents_present_then(self):
        self.install_workers("worker-a", "worker-b")
        self.start()
        self.assertEqual(json.loads(self.record_path().read_text())["agents"],
                         ["worker-a", "worker-b"])

    def test_resume_records_them_too(self):
        self.install_workers()
        self.start(source="resume")
        self.assertEqual(json.loads(self.record_path().read_text())["agents"], list(WORKERS))

    def test_the_record_carries_the_time_it_was_written(self):
        self.install_workers()
        before = int(time.time())
        self.start()
        self.assertGreaterEqual(json.loads(self.record_path().read_text())["at"], before)

    def test_clear_and_compact_leave_an_existing_record_alone(self):
        self.record("worker-b")
        self.install_workers()
        for source in ("clear", "compact", "a-source-nobody-has-shipped"):
            with self.subTest(source=source):
                self.start(source=source)
                self.assertEqual(json.loads(self.record_path().read_text())["agents"],
                                 ["worker-b"])

    def test_clear_and_compact_never_create_one(self):
        self.install_workers()
        for source in ("clear", "compact"):
            with self.subTest(source=source):
                self.start(source=source)
                self.assertFalse(self.record_path().exists())

    def test_a_session_with_no_agents_directory_records_an_empty_registry(self):
        self.start()
        self.assertEqual(json.loads(self.record_path().read_text())["agents"], [])

    def test_the_recorded_directory_follows_claude_config_dir(self):
        alt = self.home / "elsewhere"
        self.install_workers("worker-c", config=alt)
        self.install_workers("worker-a")
        self.start(env={"CLAUDE_CONFIG_DIR": str(alt)})
        self.assertEqual(json.loads(self.record_path().read_text())["agents"], ["worker-c"])

    def test_the_record_is_private_to_its_owner(self):
        self.install_workers()
        self.start()
        self.assertEqual(stat.S_IMODE(self.record_path().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.sessions().stat().st_mode), 0o700)

    def test_the_session_hook_stays_silent_about_the_record(self):
        self.install_workers()
        self.assertEqual(self.start().stdout.strip(), "")

    def test_a_session_id_that_is_not_a_file_name_writes_nothing(self):
        self.install_workers()
        for session in ("../escape", "has/slash", ""):
            with self.subTest(session=session):
                self.start(session=session)
                self.assertEqual(sorted(p.name for p in self.sessions().glob("*"))
                                 if self.sessions().is_dir() else [], [])


class PruneTests(RegistryCase):
    def test_a_stale_record_is_swept_and_the_current_one_never_is(self):
        self.record("worker-b", session="old-session")
        stale = time.time() - 15 * 86400
        os.utime(self.record_path("old-session"), (stale, stale))
        self.record("worker-b")
        os.utime(self.record_path(), (stale, stale))
        self.install_workers()
        self.start()
        self.assertFalse(self.record_path("old-session").exists())
        self.assertTrue(self.record_path().exists())

    def test_a_recent_record_of_another_session_is_kept(self):
        self.record("worker-b", session="other-session")
        self.install_workers()
        self.start()
        self.assertTrue(self.record_path("other-session").exists())


class RerouteTests(RegistryCase):
    """The defect: a reroute must never turn a spawn that would have worked into one that fails."""

    def routed(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("updatedInput", {}).get("subagent_type")

    def test_a_record_that_lists_the_worker_reroutes(self):
        self.install_workers()
        self.record(*WORKERS)
        out = self.spawn()
        self.assertEqual(self.routed(out), "worker-b")
        self.assertIn("routed to worker-b", out["systemMessage"])

    def test_a_worker_on_disk_but_not_in_the_record_is_not_routed_to(self):
        # The live defect: `harness sync` installed the workers into a session already running,
        # whose registry cannot resolve them.
        self.install_workers()
        self.record("reviewer", "gatherer")
        out = self.spawn()
        self.assertIsNone(self.routed(out))
        self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")
        self.assertIn("worker-b is installed but this session started before it was",
                      out["systemMessage"])
        self.assertIn("restart the session", out["systemMessage"])

    def test_that_notice_is_said_once_a_session(self):
        self.install_workers()
        self.record("reviewer")
        self.assertIn("started before it was", self.spawn()["systemMessage"])
        second = self.spawn()
        self.assertIsNone(self.routed(second))
        self.assertEqual(second["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")
        self.assertNotIn("started before it was", second.get("systemMessage", ""))
        self.record("reviewer", session="session-two")
        self.assertIn("started before it was",
                      self.spawn(session="session-two")["systemMessage"])

    def test_the_routed_notice_is_said_once_a_session(self):
        # Where an unnamed spawn goes is the standing arrangement, not news on every spawn.
        self.install_workers()
        self.record(*WORKERS)
        self.assertIn("routed to worker-b", self.spawn()["systemMessage"])
        second = self.spawn()
        self.assertEqual(self.routed(second), "worker-b")
        self.assertNotIn("systemMessage", second)
        self.record(*WORKERS, session="session-two")
        self.assertIn("routed to worker-b", self.spawn(session="session-two")["systemMessage"])

    def test_a_refusal_is_still_said_on_every_routed_spawn(self):
        # The caller asked for the top class and did not get it; that is news each time.
        self.install_workers()
        self.record(*WORKERS)
        for _ in range(2):
            out = self.spawn({"prompt": "x", "model": "fable"})
            self.assertEqual(self.routed(out), "worker-b")
            self.assertIn("not by request", out["systemMessage"])

    def test_no_record_at_all_reroutes_nothing(self):
        # A session that started before this fix shipped: no record, so no evidence, so no reroute.
        self.install_workers()
        out = self.spawn()
        self.assertIsNone(self.routed(out))
        self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")
        self.assertIn("started before it was", out["systemMessage"])

    def test_a_spawn_that_carries_no_session_id_reroutes_nothing(self):
        self.install_workers()
        self.record(*WORKERS)
        self.assertIsNone(self.routed(self.spawn(session=None)))

    def test_an_unreadable_record_reroutes_nothing_and_raises_nothing(self):
        self.install_workers()
        for body in ("{not json", "[]", "", json.dumps({"agents": "worker-b"}),
                     json.dumps({"agents": [17]})):
            with self.subTest(body=body):
                self.sessions().mkdir(parents=True, exist_ok=True)
                self.record_path().write_text(body)
                out = self.spawn()
                self.assertIsNone(self.routed(out))
                self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["model"], "sonnet")

    def test_a_missing_definition_still_says_it_is_missing(self):
        # Two different reasons not to route; the record cannot mask the plainer one.
        self.record(*WORKERS)
        out = self.spawn()
        self.assertIsNone(self.routed(out))
        self.assertIn("no worker-b definition is installed", out["systemMessage"])

    def test_both_sides_follow_claude_config_dir(self):
        alt = self.home / "elsewhere"
        self.install_workers(config=alt)
        env = {"CLAUDE_CONFIG_DIR": str(alt)}
        self.start(env=env)
        self.assertEqual(json.loads(self.record_path().read_text())["agents"], list(WORKERS))
        self.assertEqual(self.routed(self.spawn(env=env)), "worker-b")
        # The same record, with the definitions back where the default directory would be.
        self.assertIsNone(self.routed(self.spawn()))

    def test_a_started_session_can_spawn_end_to_end(self):
        self.install_workers()
        self.start()
        self.assertEqual(self.routed(self.spawn()), "worker-b")


class GuardTests(RegistryCase):
    """`brief-guard` prices a spawn by the worker it is about to be routed to — and only then."""

    def prompt(self, **kwargs):
        out = self.spawn(hook=GUARD_HOOK, **kwargs)
        return out["hookSpecificOutput"]["updatedInput"]["prompt"]

    def test_a_spawn_the_session_cannot_resolve_is_priced_by_nothing(self):
        self.install_workers()
        self.record("reviewer")
        self.assertNotIn("Expected spend", self.prompt())

    def test_a_spawn_the_session_can_resolve_is_priced_by_its_band(self):
        self.install_workers()
        self.record(*WORKERS)
        self.assertIn("about 39,000 output tokens", self.prompt())  # band B

    def test_the_guard_never_spends_the_once_per_session_notice(self):
        # Both hooks answer one event. If pricing consumed the memory, the spawn hook would go
        # silent about a reroute it refused and nobody would learn to restart the session.
        self.install_workers()
        self.record("reviewer")
        self.assertNotIn("Expected spend", self.prompt())
        self.assertIn("started before it was", self.spawn()["systemMessage"])


class UninstallTests(unittest.TestCase):
    """The records are this install's state, so they leave with it, exactly as the feed does."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self._environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._environ)))
        for key in [k for k in os.environ if k.startswith("HARNESS_")]:
            del os.environ[key]
        os.environ["HOME"] = str(self.home)
        os.environ["HARNESS_QUIET"] = "1"

    def test_uninstall_removes_the_session_directory(self):
        state = self.home / ".local" / "state" / "agent-harness"
        (state / "sessions").mkdir(parents=True)
        (state / "sessions" / (SESSION + ".json")).write_text(json.dumps({"agents": [], "at": 0}))
        (state / "manifest.json").write_text(json.dumps({"repo": str(REPO), "links": []}))
        (state / "usage.jsonl").write_text("")
        self.assertEqual(harness.cmd_uninstall(harness.argparse.Namespace()), 0)
        self.assertFalse((state / "sessions").exists())
        self.assertTrue((state / "usage.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
