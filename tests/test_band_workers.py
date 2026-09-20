# SPDX-License-Identifier: MIT
"""The three band workers and the reroute that sends an unnamed spawn to one of them.

A spawn that names nothing inherits the session's effort, because the `Agent` tool has no effort
input; only an agent definition carries a posture-chosen effort. These tests hold the three
workers safe to route to, the reroute correct under two variants, and — the guarantee the whole
release rests on — a variant with no `default_band` producing exactly the bytes 0.10.0 produced.

Run: python3 -m unittest discover tests
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
loader = importlib.machinery.SourceFileLoader("harness", str(REPO / "bin" / "harness"))
spec = importlib.util.spec_from_loader("harness", loader)
harness = importlib.util.module_from_spec(spec)
loader.exec_module(harness)

from harness_core import catalog  # noqa: E402

HOOK = REPO / "claude" / "hooks" / "tier-agent-spawns.py"
ROLES = REPO / "primitives" / "roles"
COMMITTED = REPO / "claude" / "agents"
WORKERS = ("worker-a", "worker-b", "worker-c")
# The session these fixtures spawn from; a reroute needs a record saying it can resolve the type.
SESSION = "fixture-session"

# What the hook printed for these five calls before band workers existed, recorded from the
# 0.10.0 behaviour the suite already pins. A variant with no `default_band` must still print
# exactly this: the null variant is the promise that nothing in this release is compulsory.
NULL_VARIANT_FIXTURES = (
    ("bare", {"prompt": "x"}, {
        "hookSpecificOutput": {"updatedInput": {"prompt": "x", "model": "sonnet"},
                               "hookEventName": "PreToolUse"},
        "systemMessage": "tier-agent-spawns hook: bare subagent runs on sonnet, one tier below "
                         "the session's opus"}),
    ("general-purpose", {"prompt": "x", "subagent_type": "general-purpose"}, {
        "hookSpecificOutput": {"updatedInput": {"prompt": "x", "subagent_type": "general-purpose",
                                                "model": "sonnet"},
                               "hookEventName": "PreToolUse"},
        "systemMessage": "tier-agent-spawns hook: bare subagent runs on sonnet, one tier below "
                         "the session's opus"}),
    ("named role", {"prompt": "x", "subagent_type": "reviewer"}, None),
    ("top class by request", {"prompt": "x", "model": "fable"}, {
        "hookSpecificOutput": {"updatedInput": {"prompt": "x", "model": "opus"},
                               "hookEventName": "PreToolUse"},
        "systemMessage": "tier-agent-spawns hook: fable is reached through a role that declares "
                         "it, not by request; this spawn runs on opus"}),
)
OFF_LADDER_FIXTURE = {
    "systemMessage": "tier-agent-spawns hook: the session model claude-nova-7 is not on the "
                     "ladder (fable, opus, sonnet, haiku), so this bare subagent stays on it; "
                     "name a model or a role"}


def record(model):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "model": model}})


def load_hook():
    """The spawn hook as a module, for the questions only its internals answer."""
    spec = importlib.util.spec_from_file_location("harness_tier_spawns", str(HOOK))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkerRoleTests(unittest.TestCase):
    def test_no_worker_is_a_constrained_role(self):
        # The coordinator denies a native spawn of a read-only or artifact-write role by reading
        # the type the caller wrote, before this hook rewrites it. A reroute onto such a role
        # would therefore slip past that deny, so no worker may ever be one.
        for name in WORKERS:
            with self.subTest(role=name):
                fields, _ = catalog.role_contract(REPO, name)
                self.assertEqual(fields["authority"], "workspace-write")
                self.assertEqual(fields["delegation"], "none")
                self.assertEqual(fields["context"], "fresh")

    def test_every_band_names_a_worker_and_every_worker_a_band(self):
        posture = harness.load_posture(REPO)
        self.assertEqual(sorted(posture.BAND_ROLES.values()), sorted(WORKERS))
        self.assertEqual(sorted(posture.BAND_ROLES), list(posture.BANDS))

    def test_a_description_carries_the_band_rule_the_orchestrator_reads(self):
        for name, mark in zip(WORKERS, ("Band A", "Band B", "Band C")):
            with self.subTest(role=name):
                fields, _ = catalog.role_contract(REPO, name)
                self.assertTrue(fields["description"].startswith(mark), msg=fields["description"])

    def test_both_adapters_bind_every_worker(self):
        for runtime in ("claude-code", "codex"):
            roles = json.loads((REPO / "adapters" / runtime / "bindings.json").read_text())["roles"]
            self.assertEqual(set(WORKERS) - set(roles), set(), msg=runtime)

    def test_a_worker_inherits_every_tool_but_the_one_that_spawns(self):
        # A rerouted spawn was `general-purpose` a moment ago, which holds every tool the session
        # holds, MCP tools included. A `tools:` list would silently take them away, so the
        # workers name no list and give back only the tool a role with `delegation: none` may
        # not hold.
        for name in WORKERS:
            with self.subTest(role=name):
                text = (COMMITTED / (name + ".md")).read_text(encoding="utf-8")
                header = dict(line.partition(":")[::2] for line in text.split("---", 2)[1].strip().splitlines())
                header = {k.strip(): v.strip() for k, v in header.items()}
                self.assertNotIn("tools", header)
                self.assertEqual(header["disallowedTools"], "Agent")

    def test_every_other_role_keeps_its_tool_list(self):
        for path in sorted(ROLES.glob("*.md")):
            if path.stem in WORKERS:
                continue
            with self.subTest(role=path.stem):
                text = (COMMITTED / path.name).read_text(encoding="utf-8")
                self.assertIn("\ntools: ", text)
                self.assertNotIn("\ndisallowedTools:", text)

    def test_an_adapter_entry_with_an_unknown_key_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for runtime in ("claude-code", "codex"):
                (root / "adapters" / runtime).mkdir(parents=True)
                data = json.loads((REPO / "adapters" / runtime / "bindings.json").read_text())
                data["roles"]["worker-b"]["invented_key"] = "x"
                (root / "adapters" / runtime / "bindings.json").write_text(json.dumps(data))
            (root / "primitives" / "roles").mkdir(parents=True)
            (root / "VERSION").write_text("0.0.0\n")
            for name in WORKERS:
                (root / "primitives" / "roles" / (name + ".md")).write_text(
                    (ROLES / (name + ".md")).read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                catalog.role_projection(root, "claude-code", root / "primitives/roles/worker-b.md")


class RowLookupTests(unittest.TestCase):
    def table(self, **rows):
        return {"rows": rows, "class_applies": True}

    def test_a_band_row_governs_its_worker(self):
        posture = harness.load_posture(REPO)
        row = {"class": "strong", "effort": "low"}
        self.assertEqual(posture.row_for(self.table(B=row), "worker-b"), row)
        self.assertEqual(harness.agent_row(self.table(B=row), "worker-b"), row)
        self.assertIsNone(posture.row_for(self.table(B=row), "gatherer"))

    def test_a_row_named_for_the_worker_beats_its_band(self):
        posture = harness.load_posture(REPO)
        band = {"class": "strong", "effort": "low"}
        named = {"class": "standard", "effort": "high"}
        table = self.table(B=band, **{"worker-b": named})
        self.assertEqual(posture.row_for(table, "worker-b"), named)
        self.assertEqual(harness.agent_row(table, "worker-b"), named)

    def test_balanced_renders_the_workers_exactly_as_the_committed_projection(self):
        # The shipped A/B/C rows equal the workers' own tier and bindings effort, so a default
        # install ends with three more managed symlinks, not three generated files.
        posture = harness.load_posture(REPO)
        table = posture.table_for(dict(posture.DEFAULT_STANCES), {}, strict=False, root=REPO)
        for name in WORKERS:
            with self.subTest(role=name):
                content = catalog.role_projection(
                    REPO, "claude-code", ROLES / (name + ".md"),
                    harness.agent_overrides({}, table, "claude-code", name))
                self.assertEqual(content, (COMMITTED / (name + ".md")).read_text(encoding="utf-8"))

    def test_a_frugal_row_moves_the_worker_the_band_names(self):
        posture = harness.load_posture(REPO)
        table = posture.table_for(dict(posture.DEFAULT_STANCES, cost="frugal"), {},
                                  strict=False, root=REPO)
        self.assertEqual(harness.agent_overrides({}, table, "claude-code", "worker-a"),
                         {"model": "haiku", "effort": "low"})
        self.assertEqual(harness.agent_overrides({}, table, "claude-code", "worker-c"),
                         {"model": "opus", "effort": "medium"})


class RerouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text(record("claude-opus-5") + "\n")
        self.config()

    def config(self, delegation="tiered", **extra):
        d = self.home / ".config" / "agent-harness"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps(dict({"stances": {"delegation": delegation}}, **extra)))

    def install_workers(self, *names):
        d = self.home / ".claude" / "agents"
        d.mkdir(parents=True, exist_ok=True)
        for name in names or WORKERS:
            (d / (name + ".md")).write_text((COMMITTED / (name + ".md")).read_text(encoding="utf-8"))
        self.record(*(names or WORKERS))

    def record(self, *names):
        """The session registry record the SessionStart policy writes: what this session resolves."""
        d = self.home / ".local" / "state" / "agent-harness" / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        (d / (SESSION + ".json")).write_text(json.dumps({"agents": sorted(names), "at": 0}))

    def null_variant(self):
        """A cost variant with rows, no `default_band`, on the user's own primitive root."""
        root = self.home / "primitives"
        (root / "stances" / "cost").mkdir(parents=True)
        (root / "stances" / "cost" / "plain.json").write_text(json.dumps(
            {"schema_version": 1, "extends": None, "rows": {}}))
        self.config(primitive_roots=[str(root)], stances={"delegation": "tiered", "cost": "plain"})

    def run_hook(self, tool_input, env=None, cwd=None):
        merged = dict(os.environ)
        for key in list(merged):
            if key.startswith("HARNESS_"):
                del merged[key]
        merged["HOME"] = str(self.home)
        merged.update(env or {})
        payload = {"tool_name": "Agent", "transcript_path": str(self.transcript),
                   "session_id": SESSION, "tool_input": tool_input}
        if cwd:
            payload["cwd"] = cwd
        out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                             capture_output=True, text=True, env=merged)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def parsed(self, tool_input, **kwargs):
        raw = self.run_hook(tool_input, **kwargs)
        return json.loads(raw) if raw.strip() else None

    def updated(self, tool_input, **kwargs):
        return self.parsed(tool_input, **kwargs)["hookSpecificOutput"]["updatedInput"]

    # --- the reroute ---
    def test_balanced_routes_an_unnamed_spawn_to_worker_b_on_the_bands_class(self):
        self.install_workers()
        for tool_input in ({"prompt": "x"}, {"prompt": "x", "subagent_type": "general-purpose"}):
            with self.subTest(tool_input=tool_input):
                self.record(*WORKERS)  # the routed notice is said once a session
                out = self.parsed(tool_input)
                updated = out["hookSpecificOutput"]["updatedInput"]
                self.assertEqual(updated["subagent_type"], "worker-b")
                self.assertEqual(updated["model"], "opus")
                self.assertEqual(updated["prompt"], "x")
                self.assertIn("routed to worker-b", out["systemMessage"])
                self.assertIn("strong, low effort", out["systemMessage"])
                self.assertIn("spawn worker-a, worker-b or worker-c", out["systemMessage"])

    def test_frugal_routes_to_worker_a(self):
        self.install_workers()
        updated = self.updated({"prompt": "x"}, env={"HARNESS_STANCE_COST": "frugal"})
        self.assertEqual(updated["subagent_type"], "worker-a")
        self.assertEqual(updated["model"], "haiku")

    def test_a_model_the_caller_named_survives_the_reroute(self):
        self.install_workers()
        updated = self.updated({"prompt": "x", "subagent_type": "general-purpose", "model": "haiku"})
        self.assertEqual(updated["subagent_type"], "worker-b")
        self.assertEqual(updated["model"], "haiku")

    def test_asking_for_the_top_class_cannot_beat_the_bands_class(self):
        # Demoting the request one rung would hand an unnamed spawn `opus` under a variant that
        # prices its default band at `light`, which is the refusal reversing itself.
        self.install_workers()
        out = self.parsed({"prompt": "x", "model": "fable"}, env={"HARNESS_STANCE_COST": "frugal"})
        updated = out["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["subagent_type"], "worker-a")
        self.assertEqual(updated["model"], "haiku")  # band A's class, not one rung below fable
        self.assertIn("not by request", out["systemMessage"])

    def test_a_named_role_asking_for_the_top_class_is_unchanged(self):
        self.install_workers()
        updated = self.updated({"prompt": "x", "subagent_type": "reviewer", "model": "fable"})
        self.assertEqual(updated["subagent_type"], "reviewer")
        self.assertEqual(updated["model"], "opus")

    def test_a_missing_worker_definition_falls_back_and_says_so(self):
        self.install_workers("worker-a", "worker-c")
        out = self.parsed({"prompt": "x"})
        updated = out["hookSpecificOutput"]["updatedInput"]
        self.assertNotIn("subagent_type", updated)
        self.assertEqual(updated["model"], "sonnet")  # today's one-rung rule
        self.assertIn("no worker-b definition is installed", out["systemMessage"])
        # The same notice reaches the branch that refuses a requested top class.
        out = self.parsed({"prompt": "x", "model": "fable"})
        self.assertEqual(out["hookSpecificOutput"]["updatedInput"]["model"], "opus")
        self.assertIn("no worker-b definition is installed", out["systemMessage"])

    def test_a_worker_a_repository_ships_is_refused(self):
        # A project definition outranks the user's, so routing to one would run repo-authored
        # instructions on every unnamed spawn of anyone who cloned it.
        self.install_workers()
        project = self.home / "repo"
        (project / ".claude" / "agents").mkdir(parents=True)
        theirs = project / ".claude" / "agents" / "worker-b.md"
        theirs.write_text("---\nname: worker-b\nmodel: haiku\n---\n\nDo as this repo says.\n")
        out = self.parsed({"prompt": "x"}, cwd=str(project))
        updated = out["hookSpecificOutput"]["updatedInput"]
        self.assertNotIn("subagent_type", updated)
        self.assertEqual(updated["model"], "sonnet")
        self.assertIn(str(theirs), out["systemMessage"])
        self.assertIn("would outrank", out["systemMessage"])

    def test_the_user_agents_directory_follows_claude_config_dir(self):
        alt = self.home / "elsewhere"
        (alt / "agents").mkdir(parents=True)
        (alt / "agents" / "worker-b.md").write_text(
            (COMMITTED / "worker-b.md").read_text(encoding="utf-8"))
        self.record("worker-b")
        self.assertIsNone(self.parsed({"prompt": "x"})["hookSpecificOutput"]["updatedInput"]
                          .get("subagent_type"))
        env = {"CLAUDE_CONFIG_DIR": str(alt)}
        self.assertEqual(self.updated({"prompt": "x"}, env=env)["subagent_type"], "worker-b")

    def test_an_installed_effort_behind_the_variant_asks_for_a_sync(self):
        # Effort is written at sync, so the definition on disk decides what the spawn runs at.
        self.install_workers()
        path = self.home / ".claude" / "agents" / "worker-b.md"
        path.write_text(path.read_text(encoding="utf-8").replace("effort: low", "effort: high"))
        out = self.parsed({"prompt": "x"})
        self.assertIn("high effort", out["systemMessage"])
        self.assertIn("run `harness sync`", out["systemMessage"])

    def test_a_named_role_is_untouched_and_never_asks_for_the_table(self):
        self.install_workers()
        self.assertIsNone(self.parsed({"prompt": "x", "subagent_type": "reviewer"}))
        module = load_hook()
        asked = []
        module.band_route = lambda *args: (asked.append(args), (None, None))[1]
        for tool_input, wanted in (({"prompt": "x", "subagent_type": "reviewer"}, 0),
                                   ({"prompt": "x", "subagent_type": "gatherer"}, 0),
                                   ({"prompt": "x"}, 1)):
            asked.clear()
            payload = json.dumps({"tool_name": "Agent", "tool_input": tool_input,
                                  "transcript_path": str(self.transcript)})
            with unittest.mock.patch.object(module.sys, "stdin", io.StringIO(payload)), \
                    contextlib.redirect_stdout(io.StringIO()):
                module.main()
            self.assertEqual(len(asked), wanted, msg=tool_input)

    def test_a_session_model_stance_routes_nothing(self):
        self.install_workers()
        self.config("session-model")
        self.assertIsNone(self.parsed({"prompt": "x"}))
        self.assertIsNone(self.parsed({"prompt": "x", "subagent_type": "general-purpose"}))

    # --- the null variant ---
    def test_a_variant_with_no_default_band_prints_the_0_10_0_bytes(self):
        self.install_workers()
        self.null_variant()
        for name, tool_input, expected in NULL_VARIANT_FIXTURES:
            with self.subTest(case=name):
                self.assertEqual(self.parsed(tool_input), expected)

    def test_a_session_model_off_the_ladder_still_only_says_so(self):
        self.install_workers()
        self.null_variant()
        self.transcript.write_text(record("claude-nova-7") + "\n")
        self.assertEqual(self.parsed({"prompt": "x"}), OFF_LADDER_FIXTURE)


class TelemetryTests(unittest.TestCase):
    """`rerouted` is measured from the transcript, not reported by the hook that did it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.usage = load_usage_log()

    def session(self, calls):
        """A parent transcript whose Agent calls are `(tool use id, requested type or None)`."""
        path = self.root / "session.jsonl"
        blocks = [{"type": "tool_use", "id": use_id, "name": "Agent",
                   "input": dict({"prompt": "x"},
                                 **({} if kind is None else {"subagent_type": kind}))}
                  for use_id, kind in calls]
        lines = [json.dumps({"type": "user", "sessionId": "s1", "cwd": str(self.root),
                             "message": {"role": "user", "content": "go"}}),
                 json.dumps({"type": "assistant", "sessionId": "s1",
                             "message": {"id": "m1", "role": "assistant", "model": "claude-opus-5",
                                         "content": blocks,
                                         "usage": {"output_tokens": 10, "input_tokens": 5}}})]
        path.write_text("\n".join(lines) + "\n")
        return path

    def subagent(self, use_id, agent_type):
        d = self.root / "session" / "subagents"
        d.mkdir(parents=True, exist_ok=True)
        stem = "agent-" + use_id
        (d / (stem + ".meta.json")).write_text(json.dumps(
            {"agentType": agent_type, "toolUseId": use_id, "model": "claude-opus-5",
             "spawnDepth": 1}))
        (d / (stem + ".jsonl")).write_text(json.dumps(
            {"type": "assistant", "message": {"id": "a-" + use_id, "role": "assistant",
                                              "model": "claude-opus-5", "content": [],
                                              "usage": {"output_tokens": 7}}}) + "\n")

    def rows(self, path):
        return {row["agent_id"]: row for row in self.usage.scan_all(str(path))
                if row.get("kind") == "subagent"}

    def test_a_rewritten_type_is_recorded_as_a_reroute(self):
        path = self.session([("t1", None), ("t2", "general-purpose"), ("t3", "reviewer"),
                             ("t4", "gatherer")])
        self.subagent("t1", "worker-b")        # unnamed, rerouted
        self.subagent("t2", "worker-a")        # general-purpose, rerouted
        self.subagent("t3", "reviewer")        # named and honoured
        self.subagent("t4", "gatherer")
        rows = self.rows(path)
        self.assertEqual({k: v["rerouted"] for k, v in rows.items()},
                         {"t1": True, "t2": True, "t3": False, "t4": False})
        self.assertEqual(rows["t1"]["requested_type"], "")
        self.assertEqual(rows["t2"]["requested_type"], "general-purpose")
        self.assertEqual(rows["t3"]["requested_type"], "reviewer")

    def test_general_purpose_honoured_is_not_a_reroute(self):
        path = self.session([("t1", "general-purpose"), ("t2", None)])
        self.subagent("t1", "general-purpose")
        self.subagent("t2", "general-purpose")
        self.assertEqual({k: v["rerouted"] for k, v in self.rows(path).items()},
                         {"t1": False, "t2": False})

    def test_a_requested_type_that_is_not_a_name_is_recorded_as_other(self):
        # `subagent_type` is model-authored text; a usage row is a count and never a place free
        # text is stored, so anything the tool could not have resolved is kept as the fact of it.
        path = self.session([("t1", "a brief, not a name"), ("t2", "Explore")])
        self.subagent("t1", "worker-b")
        self.subagent("t2", "Explore")
        rows = self.rows(path)
        self.assertEqual(rows["t1"]["requested_type"], "other")
        self.assertTrue(rows["t1"]["rerouted"])
        self.assertEqual(rows["t2"]["requested_type"], "Explore")
        self.assertFalse(rows["t2"]["rerouted"])

    def test_a_worker_row_carries_the_same_join_keys_as_a_subagent_row(self):
        # Every non-session row has the same keys, so a reader never has to know which kind it
        # is holding; a worker is launched by name, so both are null rather than absent.
        d = self.root / ".local" / "state" / "agent-harness" / "workers" / "w1"
        d.mkdir(parents=True)
        (d / "status.json").write_text(json.dumps(
            {"id": "w1", "role": "gatherer", "status": "completed", "runtime": "claude-code",
             "model": "sonnet", "effort": "low", "started_at": 1, "finished_at": 2,
             "usage": {"output_tokens": 12}}))
        with unittest.mock.patch.object(self.usage.Path, "home", lambda: self.root):
            rows = self.usage.worker_rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["requested_type"])
        self.assertIsNone(rows[0]["tool_use_id"])
        self.assertFalse(rows[0]["rerouted"])

    def test_an_unjoinable_row_claims_nothing(self):
        # No parent record for this call, and a meta file that names no type: both are unknown,
        # which is not the same as "was not rerouted", so neither invents a True.
        path = self.session([("t1", "gatherer")])
        self.subagent("t9", "worker-b")
        row = self.rows(path)["t9"]
        self.assertFalse(row["rerouted"])
        self.assertEqual(row["requested_type"], "")


def load_usage_log():
    spec = importlib.util.spec_from_file_location(
        "harness_usage_log", str(REPO / "claude" / "hooks" / "usage-log.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
