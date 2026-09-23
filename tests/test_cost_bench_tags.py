"""A pinned `--tag` is synced into a config directory of its own, and the profile the owner runs
under is neither read nor written while it happens. No test here launches an agent: the harness
under sync is a stub that records the environment it was given."""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from test_cost_bench import BENCH
from test_harness import REPO

STUB = """#!/usr/bin/env python3
import json, os, pathlib, sys

root = pathlib.Path(__file__).resolve().parent.parent
config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR")
                      or (pathlib.Path(os.environ.get("HOME", "/nowhere")) / ".claude"))
config.mkdir(parents=True, exist_ok=True)
(config / "CLAUDE.md").write_text("synced %s" % (root / "VERSION").read_text().strip(), encoding="utf-8")
(config / "env.json").write_text(json.dumps(dict(os.environ), sort_keys=True), encoding="utf-8")
settings = config / "settings.json"
if settings.is_file():  # merged in place, as the real sync merges its hooks into it
    settings.write_text(settings.read_text() + ' {"hooks": "hooks/harness"}', encoding="utf-8")
(config / "rules").mkdir(exist_ok=True)
link = config / "rules" / ("stub-%s.md" % (root / "VERSION").read_text().strip())
if not link.is_symlink():
    link.symlink_to(root / "VERSION")
state = pathlib.Path(os.environ["HOME"]) / ".local" / "state" / "agent-harness"
state.mkdir(parents=True, exist_ok=True)
(state / "manifest.json").write_text(json.dumps({"links": [{"path": str(link), "target": str(root / "VERSION")}]}))
(state / "ownership.json").write_text(json.dumps({"files": {
    str(config / "CLAUDE.md"): {"kind": "generated"}, str(config / "env.json"): {"kind": "generated"},
    str(settings): {"kind": "json", "created": not settings.is_file()}}}))
sys.exit(int(os.environ.get("STUB_EXIT") or 0) or (0 if sys.argv[1:] == ["sync"] else 3))
"""

TASK = {"id": "demo", "kind": "synthetic", "parent_sha": "HEAD", "good_sha": None,
        "prompt": ["do", "it"], "tests": {"oracle": "none"}, "max_turns": 5}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t"] + list(args),
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def harness_repo(root, exit_code=0, records=True):
    """A checkout shaped like this one: a VERSION, a `bin/harness` that projects into whatever
    CLAUDE_CONFIG_DIR names, and a tag `v1` one version behind the branch. `records=False` is a
    sync that writes its links but records nothing, as a tag with its state elsewhere would."""
    root = Path(root)
    (root / "bin").mkdir(parents=True)
    stub = STUB.replace('or 0) or (0', 'or %d) or (0' % exit_code)
    if not records:
        stub = stub[:stub.index("state = pathlib")] + stub[stub.index("sys.exit("):]
    (root / "bin" / "harness").write_text(stub, encoding="utf-8")
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "chore: one")
    git(root, "tag", "v1")
    (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")
    git(root, "commit", "-qam", "chore: two")
    git(root, "tag", "v2")
    return root


def listing(root):
    """Every path under `root` with its size and modification time: what a write would move."""
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(root).rglob("*") if p.is_file())


class TagResolutionTests(unittest.TestCase):
    def test_a_ref_that_does_not_resolve_is_named_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            self.assertEqual(len(BENCH.resolve_tag(repo, "v1")), 40)
            with self.assertRaises(SystemExit) as caught:
                BENCH.resolve_tag(repo, "v9")
            self.assertIn("v9", str(caught.exception))

    def test_a_tag_is_synced_from_its_own_checkout_and_stamped_from_it(self):
        """The branch is two versions ahead: a pinned row labelled 2.0.0 would name a harness that
        never ran."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            wanted = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "v1^{commit}"])
            synced = BENCH.sync_tag(repo, "v1", Path(tmp) / "work")
            self.assertEqual(synced["version"], "1.0.0")
            self.assertEqual(synced["sha"], wanted.decode().strip())
            self.assertEqual((synced["config"] / "CLAUDE.md").read_text(encoding="utf-8"), "synced 1.0.0")

    def test_a_sync_that_fails_is_an_error_naming_the_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo", exit_code=7)
            with self.assertRaises(SystemExit) as caught:
                BENCH.sync_tag(repo, "v1", Path(tmp) / "work")
            self.assertIn("v1", str(caught.exception))

    def test_every_temporary_directory_goes_even_when_the_tag_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            seen = []
            with BENCH.synced_tag(repo, "v1") as synced:
                seen.append(synced["parent"])
                self.assertTrue(synced["checkout"].is_dir())
            self.assertFalse(seen[0].exists())
            with self.assertRaises(ValueError):
                with BENCH.synced_tag(repo, "v1") as synced:
                    seen.append(synced["parent"])
                    raise ValueError("a run in the middle of the schedule")
            self.assertFalse(seen[1].exists())


class LiveProfileTests(unittest.TestCase):
    def test_syncing_a_tag_neither_reads_nor_writes_the_profile_the_owner_runs(self):
        """The contamination class this guard exists for: a sync that let HOME or an ambient
        CLAUDE_CONFIG_DIR through would rewrite the live profile and render the owner's identity
        into the arm. Both are set to sentinels here, and neither may be named or touched."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = harness_repo(tmp / "repo")
            live = tmp / "sentinel-home" / ".claude"
            live.mkdir(parents=True)
            (live / "CLAUDE.md").write_text("the owner's", encoding="utf-8")
            ambient = tmp / "sentinel-config"
            ambient.mkdir()
            (ambient / "CLAUDE.md").write_text("the owner's other", encoding="utf-8")
            before = (listing(live), listing(ambient))
            with mock.patch.dict(os.environ, {"HOME": str(tmp / "sentinel-home"),
                                              "CLAUDE_CONFIG_DIR": str(ambient)}):
                synced = BENCH.sync_tag(repo, "v1", tmp / "work")
            self.assertEqual((listing(live), listing(ambient)), before)
            env = json.loads((synced["config"] / "env.json").read_text(encoding="utf-8"))
            self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(synced["config"]))
            self.assertEqual(env["HOME"], str(synced["home"]))
            self.assertNotIn(str(tmp / "sentinel-home"), json.dumps(env))
            self.assertNotIn(str(ambient), json.dumps(env))
            self.assertEqual((synced["config"] / "CLAUDE.md").read_text(encoding="utf-8"), "synced 1.0.0")

    def test_a_sync_target_that_is_the_live_profile_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base = {"HOME": str(tmp / "home"), "CLAUDE_CONFIG_DIR": str(tmp / "other")}
            for target in (tmp / "home" / ".claude", tmp / "other", tmp / "home" / ".claude" / "inner",
                           tmp / "home", tmp, Path("/")):
                with self.assertRaises(SystemExit, msg=str(target)) as caught:
                    BENCH.refuse_live_config(target, base)
                self.assertIn("live profile", str(caught.exception))
            with self.assertRaises(SystemExit) as caught:
                BENCH.refuse_live_config(tmp / "bench", base, bare=tmp / "bench")
            self.assertIn("bare profile", str(caught.exception))
            self.assertIsNone(BENCH.refuse_live_config(tmp / "bench", base, bare=tmp / "bare"))
            self.assertIsNone(BENCH.refuse_live_config(tmp / "home" / ".claude-bench", base))

    def test_the_harness_arms_fence_admits_the_checkout_its_profile_links_into(self):
        """`harness sync` fills a profile with links into the checkout it synced from, so an arm
        fenced to the profile alone reads none of the harness it is supposed to be running."""
        opts = {"harness_source": "/pinned/checkout"}
        self.assertEqual(BENCH.arm_admits("harness", opts), ["/pinned/checkout"])
        self.assertEqual(BENCH.arm_admits("bare", opts), [])
        self.assertEqual(BENCH.arm_admits("harness", {}), [])
        fence = BENCH.fence("/profile", ["/pinned/checkout"])["sandbox"]["filesystem"]
        for key in ("allowRead", "allowWrite"):
            self.assertIn("/profile", fence[key])
        self.assertIn("/pinned/checkout", fence["allowRead"])
        # Read-only: an arm that could write it could rewrite its own rules mid-run.
        self.assertNotIn("/pinned/checkout", fence["allowWrite"])
        self.assertNotIn("/pinned/checkout", BENCH.fence("/profile")["sandbox"]["filesystem"]["allowRead"])


def replay_args(work, repo, **over):
    values = {"tasks": str(Path(work) / "tasks.json"), "task": None, "verify_tasks": False,
              "tag": ["v1"], "model": "claude-test", "reps": 1, "run_cap": 2.0, "spend_cap": 25.0,
              "stance_cost": None, "bare_config": str(Path(work) / "bare"), "harness_config": None,
              "bucket": "", "predicted_ratio": None, "history_dir": str(Path(work) / "history"),
              "change_note": "", "claude": "claude", "harness_repo": str(repo),
              "out": str(Path(work) / "out"), "raw": None, "tmp": None, "skip_preflight": True,
              "dry_run": False}
    values.update(over)
    Path(values["bare_config"]).mkdir(parents=True, exist_ok=True)
    Path(values["tasks"]).write_text(json.dumps({"tasks": [TASK]}), encoding="utf-8")
    return argparse.Namespace(**values)


class TagScheduleTests(unittest.TestCase):
    def test_a_dry_run_prints_the_schedule_for_every_tag_and_syncs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            args = replay_args(tmp, repo, tag=["v1", "candidate"], dry_run=True)
            refuse = mock.Mock(side_effect=AssertionError("a dry run syncs nothing"))
            with mock.patch.object(BENCH, "ROOT", repo), mock.patch.object(BENCH, "sync_tag", refuse):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = BENCH.cmd_replay(args)
            self.assertEqual(code, 0)
            self.assertIn("  tag v1", out.getvalue())
            self.assertIn("  tag candidate", out.getvalue())
            self.assertEqual(out.getvalue().count("demo rep 1"), 4)  # two arms, two tags

    def test_a_ref_that_does_not_resolve_stops_the_run_before_any_tag_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            args = replay_args(tmp, repo, tag=["v1", "v9"])
            with mock.patch.object(BENCH, "ROOT", repo), mock.patch.object(BENCH, "replay") as ran:
                with self.assertRaises(SystemExit):
                    BENCH.cmd_replay(args)
            ran.assert_not_called()

    def test_each_tag_writes_its_own_history_row_labelled_from_its_own_checkout(self):
        """The whole point of the flag: two tags, one invocation, two comparable rows."""
        def fake_replay(tasks, opts, launch=None, out=None):
            rows = [dict(opts["stamp"], task="demo", arm=arm, tag=opts["tag"], rep=1, error=False,
                         passed=True, cost_usd=1.0, cost_normalised_usd=1.0, cache_miss_ratio=0.5,
                         change_note="")
                    for arm in BENCH.ARMS]
            Path(out).write_text("", encoding="utf-8")
            return rows, False
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            args = replay_args(tmp, repo, tag=["v1", "candidate"])
            with mock.patch.object(BENCH, "ROOT", repo), \
                    mock.patch.object(BENCH, "replay", fake_replay), \
                    mock.patch.object(BENCH, "_text", lambda *a, **k: "1.2.3"), \
                    mock.patch.object(BENCH, "installed_harness", lambda home: repo):
                (repo / "policy").mkdir()
                (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")
                out = io.StringIO()
                with redirect_stdout(out):
                    code = BENCH.cmd_replay(args)
            self.assertEqual(code, 0)
            rows = [json.loads(line) for line in
                    (Path(tmp) / "history" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["tag"] for r in rows], ["v1", "candidate"])
            self.assertEqual([r["harness_version"] for r in rows], ["1.0.0", "2.0.0"])
            self.assertNotEqual(rows[0]["harness_sha"], rows[1]["harness_sha"])
            # The pinned arm ran on a profile of its own; the candidate inherited the install.
            self.assertNotEqual(rows[0]["series"], rows[1]["series"])
            for tag in ("v1", "candidate"):
                self.assertTrue((Path(tmp) / "out" / tag / BENCH.RESULTS).exists(), tag)

    def test_a_pinned_tag_leaves_no_temporary_directory_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            args = replay_args(tmp, repo, **{"tmp": str(Path(tmp) / "scratch")})
            Path(args.tmp).mkdir()
            with mock.patch.object(BENCH, "ROOT", repo), \
                    mock.patch.object(BENCH, "_text", lambda *a, **k: "1.2.3"), \
                    mock.patch.object(BENCH, "replay", lambda *a, **k: ([], False)):
                (repo / "policy").mkdir()
                (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")
                with redirect_stdout(io.StringIO()):
                    BENCH.cmd_replay(args)
            self.assertEqual(sorted(Path(args.tmp).iterdir()), [])


def signed_in_profile(root):
    """A profile the owner signed into and keeps: CLI state of its own, no harness in it."""
    root = Path(root)
    (root / "statsig").mkdir(parents=True)
    (root / ".claude.json").write_text('{"signed": "in"}', encoding="utf-8")
    (root / ".credentials.json").write_text('{"token": "before"}', encoding="utf-8")
    (root / "settings.json").write_text('{"theme": "dark"}', encoding="utf-8")
    (root / "statsig" / "cache").write_text("state", encoding="utf-8")
    return root


def contents(root):
    """Names, kinds and bytes under `root`: equal before and after means nothing was left behind."""
    root = Path(root)
    return sorted((rel, kind, (root / rel).read_bytes() if kind == "file" else b"")
                  for rel, kind in BENCH.profile_entries(root).items())


class NamedProfileTests(unittest.TestCase):
    def patched(self, repo, replay, home=None):
        stack = [mock.patch.object(BENCH, "ROOT", repo), mock.patch.object(BENCH, "replay", replay),
                 mock.patch.object(BENCH, "_text", lambda *a, **k: "1.2.3"),
                 mock.patch.object(BENCH, "installed_harness", lambda home: repo)]
        if home:
            stack.append(mock.patch.dict(os.environ, {"HOME": str(home)}))
            stack.append(mock.patch.object(BENCH.Path, "home", classmethod(lambda cls: Path(home))))
        return stack

    def run_replay(self, args, stack):
        for patcher in stack:
            patcher.start()
        try:
            with redirect_stdout(io.StringIO()):
                return BENCH.cmd_replay(args)
        finally:
            for patcher in reversed(stack):
                patcher.stop()

    def test_two_tags_share_one_profile_and_leave_it_exactly_as_it_was(self):
        """Each tag finds the profile clean, sees only its own layer, and hands it back unchanged."""
        seen = []

        def fake_replay(tasks, opts, launch=None, out=None):
            config = Path(opts["harness_config"])
            seen.append((opts["tag"], (config / "CLAUDE.md").read_text(encoding="utf-8"),
                         sorted(p.name for p in (config / "rules").iterdir())))
            (config / "projects").mkdir(exist_ok=True)  # what the CLI itself writes during a run
            (config / "projects" / "run.jsonl").write_text("{}", encoding="utf-8")
            Path(out).write_text("", encoding="utf-8")
            return [], False

        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            before = contents(profile)
            args = replay_args(tmp, repo, tag=["v1", "v2"], harness_config=str(profile))
            (repo / "policy").mkdir()
            (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")
            self.assertEqual(self.run_replay(args, self.patched(repo, fake_replay)), 0)
            # The sync's layer is gone; what the run's own session wrote is not the sync's and stays.
            self.assertEqual(contents(profile), sorted(before + [("projects", "dir", b""),
                                                                 ("projects/run.jsonl", "file", b"{}")]))
        self.assertEqual(seen, [("v1", "synced 1.0.0", ["stub-1.0.0.md"]),
                                ("v2", "synced 2.0.0", ["stub-2.0.0.md"])])

    def test_the_profile_is_put_back_when_a_tag_raises_in_the_middle(self):
        def failing(tasks, opts, launch=None, out=None):
            raise RuntimeError("a run in the middle of the schedule")

        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            before = contents(profile)
            args = replay_args(tmp, repo, harness_config=str(profile))
            (repo / "policy").mkdir()
            (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                self.run_replay(args, self.patched(repo, failing))
            self.assertEqual(contents(profile), before)

    def refused_before_launch(self, tmp, repo, tags, profile, home=None, installed=None, **over):
        """Runs the replay with a launcher that must never be called; returns the refusal."""
        launched = mock.Mock(side_effect=AssertionError("launched after a refusal"))
        args = replay_args(tmp, repo, tag=tags, harness_config=str(profile) if profile else None, **over)
        stack = self.patched(repo, launched, home)
        if installed is not None:
            stack[3] = mock.patch.object(BENCH, "installed_harness", installed)
        cli = mock.Mock(side_effect=AssertionError("asked the CLI after a refusal"))
        stack[2] = mock.patch.object(BENCH, "_text", cli)
        with self.assertRaises(SystemExit) as caught:
            self.run_replay(args, stack)
        launched.assert_not_called()
        cli.assert_not_called()
        return str(caught.exception)

    def test_the_live_profile_is_refused_before_any_tag_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = harness_repo(tmp / "repo")
            home = tmp / "sentinel-home"
            (home / ".claude").mkdir(parents=True)
            message = self.refused_before_launch(tmp, repo, ["candidate", "v1"], home / ".claude", home)
            self.assertIn("live profile", message)
            self.assertEqual(sorted((home / ".claude").iterdir()), [])

    def test_a_profile_already_holding_a_harness_is_refused_before_any_tag_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = harness_repo(tmp / "repo")
            profile = signed_in_profile(tmp / "bench-harness")
            (profile / "rules").mkdir()
            (profile / "rules" / "one.md").symlink_to(repo / "VERSION")
            before = contents(profile)
            message = self.refused_before_launch(tmp, repo, ["v1", "v2"], profile)
            self.assertIn("rules/one.md", message)
            self.assertEqual(contents(profile), before)

    def test_candidate_never_shares_a_named_profile_with_a_pinned_tag(self):
        """Candidate after a pinned tag would load whatever the profile holds and label it with the
        installed version: a clean profile runs no harness, a synced one runs the wrong one."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = harness_repo(tmp / "repo")
            profile = signed_in_profile(tmp / "bench-harness")
            before = contents(profile)
            message = self.refused_before_launch(tmp, repo, ["v1", "candidate"], profile)
            self.assertIn("candidate", message)
            self.assertEqual(contents(profile), before)

    def test_a_pinned_tag_writes_its_rows_apart_from_the_candidates(self):
        """v1 here shares nothing with the install but the default results directory would be the
        same for any tag whose VERSION matches, so a pinned tag always gets a folder of its own."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            args = replay_args(tmp, repo, out=None)
            (repo / "policy").mkdir()
            (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")
            outs = []

            def fake_replay(tasks, opts, launch=None, out=None):
                outs.append(Path(out))
                return [], False
            self.run_replay(args, self.patched(repo, fake_replay))
            self.assertEqual(outs, [repo / "benchmarks" / "1.0.0" / "v1" / BENCH.RESULTS])


class UndoSyncTests(unittest.TestCase):
    """The profile is not rolled back; the sync is taken out of it. Credentials are never touched."""

    def prices(self, repo):
        (repo / "policy").mkdir()
        (repo / "policy" / "prices.json").write_text(json.dumps({"models": {}}), encoding="utf-8")

    def test_a_credential_the_run_refreshed_is_left_as_the_run_left_it(self):
        """settings.json, which the sync merged, comes back byte for byte; the credential file the
        CLI rewrote mid-run keeps its new bytes, since rolling a refreshed token back signs the
        profile out; everything the sync and the run added is gone."""
        def fake_replay(tasks, opts, launch=None, out=None):
            config = Path(opts["harness_config"])
            self.assertIn("hooks/harness", (config / "settings.json").read_text(encoding="utf-8"))
            (config / ".credentials.json").write_text('{"token": "refreshed"}', encoding="utf-8")
            (config / ".claude.json").unlink()
            (config / ".claude.json").write_text('{"signed": "in again"}', encoding="utf-8")  # created anew
            (config / "todos").mkdir()  # another session's writes during the run
            (config / "todos" / "agent.json").write_text("[]", encoding="utf-8")
            Path(out).write_text("", encoding="utf-8")
            return [], False

        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            self.prices(repo)
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            before = contents(profile)
            args = replay_args(tmp, repo, harness_config=str(profile))
            tests = NamedProfileTests()
            self.assertEqual(tests.run_replay(args, tests.patched(repo, fake_replay)), 0)
            after = contents(profile)
            self.assertEqual((profile / ".credentials.json").read_text(encoding="utf-8"), '{"token": "refreshed"}')
            self.assertEqual((profile / "settings.json").read_text(encoding="utf-8"), '{"theme": "dark"}')
            expected = [(rel, kind, b'{"token": "refreshed"}' if rel == ".credentials.json"
                         else b'{"signed": "in again"}' if rel == ".claude.json" else data)
                        for rel, kind, data in before]
            self.assertEqual(after, sorted(expected + [("todos", "dir", b""), ("todos/agent.json", "file", b"[]")]))

    def test_a_copy_aside_that_fails_halfway_leaves_the_profile_untouched_and_launches_nothing(self):
        launched = mock.Mock(side_effect=AssertionError("launched after a failed copy"))

        def broken_copy(src, dst, *a, **k):
            Path(dst).write_bytes(b"trunc")  # what a full disk leaves
            raise OSError(28, "No space left on device")

        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            self.prices(repo)
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            before = contents(profile)
            args = replay_args(tmp, repo, harness_config=str(profile), **{"tmp": str(Path(tmp) / "scratch")})
            Path(args.tmp).mkdir()
            tests = NamedProfileTests()
            stack = tests.patched(repo, launched) + [mock.patch.object(BENCH.shutil, "copy2", broken_copy)]
            with self.assertRaises(OSError):
                tests.run_replay(args, stack)
            launched.assert_not_called()
            self.assertEqual(contents(profile), before)
            self.assertEqual(sorted(Path(args.tmp).iterdir()), [])  # no copy was ever marked saved

    def test_a_copy_that_does_not_match_the_original_is_not_a_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = signed_in_profile(Path(tmp) / "p")
            listing = BENCH.profile_listing(profile)
            (profile / "settings.json").write_text('{"theme": "light"}', encoding="utf-8")  # moved under us
            with self.assertRaises(RuntimeError):
                BENCH.copy_aside(profile, Path(tmp) / "saved", listing)
            self.assertFalse((Path(tmp) / "saved").exists())

    def test_a_failed_undo_keeps_the_copy_and_names_its_path_even_on_interrupt(self):
        for failure in (RuntimeError("disk"), KeyboardInterrupt()):
            with tempfile.TemporaryDirectory() as tmp:
                repo = harness_repo(Path(tmp) / "repo")
                profile = signed_in_profile(Path(tmp) / "bench-harness")
                err = io.StringIO()
                with mock.patch.object(BENCH, "undo_sync", mock.Mock(side_effect=failure)), \
                        contextlib.redirect_stderr(err), self.assertRaises(type(failure)):
                    with BENCH.synced_tag(repo, "v1", config_dir=str(profile)):
                        pass
                kept = re.search(r"kept at (\S+)", err.getvalue())
                self.assertIsNotNone(kept, err.getvalue())
                self.assertEqual((Path(kept.group(1)) / "settings.json").read_text(encoding="utf-8"),
                                 '{"theme": "dark"}')
                shutil.rmtree(kept.group(1).rsplit("/saved-profile", 1)[0], ignore_errors=True)

    def test_every_restore_write_is_atomic_and_skipped_when_bytes_already_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = signed_in_profile(Path(tmp) / "p")
            before = BENCH.profile_listing(profile)
            copied = BENCH.copy_aside(profile, Path(tmp) / "saved", before)
            self.assertEqual(copied, ["settings.json"])
            self.assertFalse((Path(tmp) / "saved").is_dir() and any(
                p.name.endswith(".partial") for p in Path(tmp).iterdir()))
            untouched = (profile / "settings.json").stat().st_ino
            state = Path(tmp) / "state"  # a sync that merged settings.json and linked nothing
            state.mkdir()
            (state / "manifest.json").write_text(json.dumps({"links": []}), encoding="utf-8")
            (state / "ownership.json").write_text(json.dumps({"files": {
                str(profile / "settings.json"): {"kind": "json", "created": False}}}), encoding="utf-8")
            BENCH.undo_sync(profile, before, Path(tmp) / "saved", copied, state)
            self.assertEqual((profile / "settings.json").stat().st_ino, untouched)  # not rewritten
            (profile / "settings.json").write_text("changed", encoding="utf-8")
            with mock.patch.object(BENCH, "atomic_write", wraps=BENCH.atomic_write) as atomic:
                BENCH.undo_sync(profile, before, Path(tmp) / "saved", copied, state)
            atomic.assert_called_once()
            self.assertEqual((profile / "settings.json").read_text(encoding="utf-8"), '{"theme": "dark"}')
            self.assertEqual([p.name for p in profile.iterdir() if p.name.startswith(".settings")], [])

    def test_only_a_link_into_a_harness_or_at_a_managed_name_is_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "p")
            (profile / "debug").mkdir()
            (profile / "debug" / "x.log").write_text("", encoding="utf-8")
            (profile / "debug" / "latest").symlink_to(profile / "debug" / "x.log")
            self.assertEqual(BENCH.harness_residue(profile), [])
            self.assertIsNone(BENCH.check_sync_target(profile))
            (profile / "misc").symlink_to(repo / "VERSION")
            self.assertEqual(BENCH.harness_residue(profile), ["misc"])
            (profile / "misc").unlink()
            (profile / "rules").mkdir()
            (profile / "rules" / "own.md").symlink_to(profile / "debug" / "x.log")
            self.assertEqual(BENCH.harness_residue(profile), ["rules/own.md"])

    def test_candidate_beside_a_pinned_tag_needs_a_resolvable_install_before_anything_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            self.prices(repo)
            tests = NamedProfileTests()
            message = tests.refused_before_launch(tmp, repo, ["v1", "candidate"], None,
                                                  installed=lambda home: None, harness_repo=None)
            self.assertIn("--harness-repo", message)

    def test_a_symlinked_managed_name_is_refused_before_any_tag_launches(self):
        """`commands` linked to the owner's dotfiles would have the sync write through it, outside
        the profile and outside anything the undo can see."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo = harness_repo(tmp / "repo")
            profile = signed_in_profile(tmp / "bench-harness")
            (tmp / "dotfiles" / "commands").mkdir(parents=True)
            (profile / "commands").symlink_to(tmp / "dotfiles" / "commands")
            before = contents(profile)
            tests = NamedProfileTests()
            message = tests.refused_before_launch(tmp, repo, ["v1"], profile)
            self.assertIn("commands", message)
            self.assertEqual(contents(profile), before)
            self.assertEqual(sorted((tmp / "dotfiles" / "commands").iterdir()), [])
            self.assertEqual(BENCH.escapes_profile(profile), ["commands"])
            (profile / "commands").unlink()
            self.assertEqual(BENCH.escapes_profile(profile), [])

    def test_a_fifo_and_an_unreadable_file_do_not_stop_the_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            os.mkfifo(str(profile / "ipc.sock"))
            (profile / "locked.json").write_text("{}", encoding="utf-8")
            (profile / "locked.json").chmod(0)
            try:
                before = BENCH.profile_listing(profile)
                self.assertEqual(before["ipc.sock"], ("other", None))
                self.assertEqual(before["locked.json"][0], "file")  # listed by stat, never opened
                with BENCH.synced_tag(repo, "v1", config_dir=str(profile)) as synced:
                    self.assertTrue((profile / "CLAUDE.md").is_file())
                self.assertFalse((profile / "CLAUDE.md").exists())
                self.assertTrue(stat.S_ISFIFO(os.lstat(str(profile / "ipc.sock")).st_mode))
                self.assertEqual((profile / "settings.json").read_text(encoding="utf-8"), '{"theme": "dark"}')
            finally:
                (profile / "locked.json").chmod(0o600)

    def test_only_what_the_sync_recorded_is_removed_and_a_new_credential_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            (profile / ".credentials.json").unlink()
            with BENCH.synced_tag(repo, "v1", config_dir=str(profile)):
                (profile / ".credentials.json").write_text('{"token": "first"}', encoding="utf-8")
                (profile / "todos" / "mine.json").parent.mkdir()
                (profile / "todos" / "mine.json").write_text("the owner's own", encoding="utf-8")
                (profile / "history.jsonl").write_text("{}", encoding="utf-8")
            self.assertEqual((profile / ".credentials.json").read_text(encoding="utf-8"), '{"token": "first"}')
            self.assertEqual((profile / "todos" / "mine.json").read_text(encoding="utf-8"), "the owner's own")
            self.assertTrue((profile / "history.jsonl").is_file())
            self.assertFalse((profile / "rules").exists())
            self.assertFalse((profile / "CLAUDE.md").exists())
            self.assertFalse((profile / "env.json").exists())

    def test_a_sync_that_records_nothing_stops_the_run_after_its_tag_with_the_leftovers_named(self):
        """The records are read from where HEAD's harness writes them; a tag that recorded
        elsewhere leaves the undo blind, and the profile itself is the check."""
        seen = []

        def fake_replay(tasks, opts, launch=None, out=None):
            seen.append(opts["tag"])
            Path(out).write_text("", encoding="utf-8")
            return [], False

        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo", records=False)
            self.prices(repo)
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            args = replay_args(tmp, repo, tag=["v1", "v2"], harness_config=str(profile))
            tests = NamedProfileTests()
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
                tests.run_replay(args, tests.patched(repo, fake_replay))
            self.assertIn("rules/stub-1.0.0.md", str(caught.exception))
            kept = re.search(r"kept at (\S+)", err.getvalue())
            self.assertIsNotNone(kept, err.getvalue())
            self.assertTrue((Path(kept.group(1)) / "settings.json").is_file())
            self.assertEqual(seen, ["v1"])  # v2 never launched
            self.assertEqual((profile / "settings.json").read_text(encoding="utf-8"), '{"theme": "dark"}')
            shutil.rmtree(kept.group(1).rsplit("/saved-profile", 1)[0], ignore_errors=True)

    def test_only_directories_the_records_lead_through_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = harness_repo(Path(tmp) / "repo")
            profile = signed_in_profile(Path(tmp) / "bench-harness")
            with BENCH.synced_tag(repo, "v1", config_dir=str(profile)):
                (profile / "empty-during-run").mkdir()  # appeared during the run, not the sync's
            self.assertTrue((profile / "empty-during-run").is_dir())
            self.assertFalse((profile / "rules").exists())  # the sync's, and empty once undone

    def test_the_real_sync_at_head_is_taken_back_out_of_a_seeded_profile(self):
        """The one test here that runs `bin/harness sync` itself rather than the stub, with HOME
        and CLAUDE_CONFIG_DIR both under the test's own directory."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            home, profile = tmp / "home", signed_in_profile(tmp / "profile")
            home.mkdir()
            before = BENCH.profile_listing(profile)
            copied = BENCH.copy_aside(profile, tmp / "saved", before)
            env = BENCH.scrubbed_env({"HOME": str(home), "CLAUDE_CONFIG_DIR": str(profile)})
            done = subprocess.run([sys.executable, "bin/harness", "sync"], cwd=str(REPO), env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                                  timeout=BENCH.SYNC_TIMEOUT)
            if done.returncode:
                self.skipTest("bin/harness sync at HEAD cannot run here (exit %d; it needs git and this "
                              "checkout's projections): %s" % (done.returncode, done.stdout.strip()[-400:]))
            during = BENCH.profile_listing(profile)
            self.assertTrue(any(kind == "link" for kind, _ in during.values()))
            self.assertIn("hooks", (profile / "settings.json").read_text(encoding="utf-8"))
            BENCH.undo_sync(profile, before, tmp / "saved", copied, home / BENCH.SYNC_STATE)
            self.assertEqual(BENCH.profile_listing(profile), before)
            self.assertEqual((profile / ".credentials.json").read_text(encoding="utf-8"), '{"token": "before"}')


if __name__ == "__main__":
    unittest.main()
