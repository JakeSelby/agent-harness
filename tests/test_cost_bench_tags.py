"""A pinned `--tag` is synced into a config directory of its own, and the profile the owner runs
under is neither read nor written while it happens. No test here launches an agent: the harness
under sync is a stub that records the environment it was given."""
import argparse
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from test_cost_bench import BENCH

STUB = """#!/usr/bin/env python3
import json, os, pathlib, sys

root = pathlib.Path(__file__).resolve().parent.parent
config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR")
                      or (pathlib.Path(os.environ.get("HOME", "/nowhere")) / ".claude"))
config.mkdir(parents=True, exist_ok=True)
(config / "CLAUDE.md").write_text("synced %s" % (root / "VERSION").read_text().strip(), encoding="utf-8")
(config / "env.json").write_text(json.dumps(dict(os.environ), sort_keys=True), encoding="utf-8")
sys.exit(int(os.environ.get("STUB_EXIT") or 0) or (0 if sys.argv[1:] == ["sync"] else 3))
"""

TASK = {"id": "demo", "kind": "synthetic", "parent_sha": "HEAD", "good_sha": None,
        "prompt": ["do", "it"], "tests": {"oracle": "none"}, "max_turns": 5}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t"] + list(args),
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def harness_repo(root, exit_code=0):
    """A checkout shaped like this one: a VERSION, a `bin/harness` that projects into whatever
    CLAUDE_CONFIG_DIR names, and a tag `v1` one version behind the branch."""
    root = Path(root)
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "harness").write_text(STUB.replace('or 0) or (0', 'or %d) or (0' % exit_code),
                                          encoding="utf-8")
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "chore: one")
    git(root, "tag", "v1")
    (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")
    git(root, "commit", "-qam", "chore: two")
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
            for target in (tmp / "home" / ".claude", tmp / "other"):
                with self.assertRaises(SystemExit) as caught:
                    BENCH.refuse_live_config(target, base)
                self.assertIn("live profile", str(caught.exception))
            self.assertIsNone(BENCH.refuse_live_config(tmp / "bench", base))

    def test_the_harness_arms_fence_admits_the_checkout_its_profile_links_into(self):
        """`harness sync` fills a profile with links into the checkout it synced from, so an arm
        fenced to the profile alone reads none of the harness it is supposed to be running."""
        opts = {"harness_source": "/pinned/checkout"}
        self.assertEqual(BENCH.arm_admits("harness", opts), ["/pinned/checkout"])
        self.assertEqual(BENCH.arm_admits("bare", opts), [])
        self.assertEqual(BENCH.arm_admits("harness", {}), [])
        fence = BENCH.fence("/profile", ["/pinned/checkout"])["sandbox"]["filesystem"]
        for key in ("allowRead", "allowWrite"):
            self.assertIn("/pinned/checkout", fence[key])
            self.assertIn("/profile", fence[key])
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


if __name__ == "__main__":
    unittest.main()
