# SPDX-License-Identifier: MIT
"""Unit tests for the local provider's policy scope: two files, whole-repository pairs, pr_merge.

The properties under test are that a user-level `governance.json` beside `config.json` is read
under the repository file, that the repository file wins for levels and the lower value wins for
caps, that a `repo:<name>` pair reaches every branch of that repository without beating an exact
pair, that `coding.pr_merge` is a class a policy may name, and that every answer names the file
that supplied it. No test reads the real home: each one runs under a temporary one.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from isolation import isolate_home, without_harness_vars

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
from harness_core import decision


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.repo = self.root / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.ledger = self.root / "decisions.jsonl"
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        isolate_home(self.home)
        self.user_path = self.home / ".config" / "agent-harness" / "governance.json"
        self.repo_path = self.repo / ".agent-harness" / "governance.json"

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data) if not isinstance(data, str) else data,
                        encoding="utf-8")
        return path

    def local(self, user=None, repo=None, variant="execute"):
        if user is not None:
            self.write(self.user_path, user)
        if repo is not None:
            self.write(self.repo_path, repo)
        return decision.LocalProvider(root=str(self.repo), variant=variant,
                                      target=str(self.ledger),
                                      user_policy_path=str(self.user_path))

    def decide(self, provider, action_class="coding.git_push", grade=2,
               counterparty="repo:x/main"):
        return provider.decide(decision.Action(action_class, grade), counterparty)


class UserPolicyTests(Base):
    def test_no_file_at_either_level_resolves_to_the_stance_as_before(self):
        for variant, level in (("execute", 3), ("confirm-writes", 2), ("ask", 1)):
            with self.subTest(variant=variant):
                answer = self.decide(self.local(variant=variant))
                self.assertEqual(answer.autonomy_level, level)
                self.assertEqual(answer.injected_cognition["rule_matches"],
                                 ["autonomy stance = " + str(level)])

    def test_a_user_default_applies_and_the_reason_names_the_user_file(self):
        answer = self.decide(self.local(user={"defaults": {"coding.git_push": 2}}))
        self.assertEqual((answer.outcome, answer.autonomy_level), ("ask", 2))
        self.assertIn("user policy " + str(self.user_path), answer.reason)
        self.assertEqual(answer.injected_cognition["rule_matches"],
                         ["defaults.coding.git_push = 2 (user policy "
                          + str(self.user_path) + ")"])

    def test_the_default_location_is_beside_config_json_under_the_harness_home(self):
        self.assertEqual(decision.user_policy_file(), self.user_path)
        self.assertEqual(decision.user_policy_file({"HARNESS_HOME": "/h", "HOME": "/o"}),
                         Path("/h/.config/agent-harness/governance.json"))
        self.write(self.user_path, {"defaults": {"coding.git_commit": 1}})
        provider = decision.LocalProvider(root=str(self.repo), variant="execute")
        self.assertEqual(provider.user_policy_path, self.user_path)
        self.assertEqual(provider.policy_files(), [self.user_path, self.repo_path])
        self.assertEqual(self.decide(provider, "coding.git_commit").autonomy_level, 1)

    def test_a_user_file_that_cannot_be_honoured_is_an_error_naming_it(self):
        for data in ("{not json", {"defaults": {"coding.nope": 2}},
                     {"pairs": {"repo:x": {"coding.git_push": 7}}}):
            with self.subTest(data=data):
                provider = self.local(user=data)
                with self.assertRaises(decision.PolicyError) as caught:
                    self.decide(provider)
                self.assertIn(str(self.user_path), str(caught.exception))


class MergeTests(Base):
    def test_the_repository_default_wins_over_the_user_default(self):
        answer = self.decide(self.local(user={"defaults": {"coding.git_push": 1}},
                                        repo={"defaults": {"coding.git_push": 3}}))
        self.assertEqual(answer.autonomy_level, 3)
        self.assertIn("repository policy " + str(self.repo_path), answer.reason)

    def test_the_repository_pair_entry_wins_and_other_user_entries_survive(self):
        provider = self.local(
            user={"pairs": {"repo:x/main": {"coding.git_push": 1, "coding.git_commit": 1}}},
            repo={"pairs": {"repo:x/main": {"coding.git_push": 3}}})
        self.assertEqual(self.decide(provider).autonomy_level, 3)
        commit = self.decide(provider, "coding.git_commit")
        self.assertEqual(commit.autonomy_level, 1)
        self.assertIn("user policy", commit.reason)

    def test_caps_combine_by_the_lower_value_whichever_file_sets_it(self):
        for user_cap, repo_cap in ((1, 3), (3, 1)):
            with self.subTest(user=user_cap, repo=repo_cap):
                answer = self.decide(self.local(
                    user={"caps": {"coding.git_push": user_cap}},
                    repo={"defaults": {"coding.git_push": 3},
                          "caps": {"coding.git_push": repo_cap}}))
                self.assertEqual(answer.autonomy_level, 1)
                layer, path = (("user policy", self.user_path) if user_cap == 1
                               else ("repository policy", self.repo_path))
                self.assertEqual(answer.injected_cognition["rule_matches"][-1],
                                 "caps.coding.git_push = 1 (" + layer + " " + str(path) + ")")

    def test_the_built_in_deploy_cap_still_applies_over_both_files(self):
        answer = self.decide(self.local(user={"defaults": {"coding.deploy": 3},
                                              "caps": {"coding.deploy": 3}},
                                        repo={"caps": {"coding.deploy": 3}}),
                             "coding.deploy", 3)
        self.assertEqual((answer.outcome, answer.autonomy_level), ("ask", 2))
        self.assertEqual(answer.injected_cognition["rule_matches"][-1],
                         "caps.coding.deploy = 2 (built-in)")

    def test_merge_policies_reports_where_each_entry_came_from(self):
        merged, sources = decision.merge_policies([
            ("user policy", Path("/u"), {"defaults": {"coding.git_push": 1}, "pairs": {},
                                         "caps": {"coding.deploy": 1}}),
            ("repository policy", Path("/r"), {"defaults": {"coding.git_push": 2},
                                               "pairs": {}, "caps": {"coding.deploy": 2}})])
        self.assertEqual(merged["defaults"], {"coding.git_push": 2})
        self.assertEqual(merged["caps"], {"coding.deploy": 1})
        self.assertEqual(sources, {"defaults.coding.git_push": "repository policy /r",
                                   "caps.coding.deploy": "user policy /u"})


class RepositoryPairTests(Base):
    def test_a_whole_repository_pair_reaches_a_task_branch(self):
        answer = self.decide(self.local(repo={"defaults": {"coding.git_push": 1},
                                              "pairs": {"repo:x": {"coding.git_push": 3}}}),
                             counterparty="repo:x/feat-y")
        self.assertEqual(answer.autonomy_level, 3)
        self.assertEqual(answer.injected_cognition["rule_matches"],
                         ["pairs.repo:x.coding.git_push = 3 (repository policy "
                          + str(self.repo_path) + ")"])

    def test_an_exact_pair_beats_the_whole_repository_pair(self):
        answer = self.decide(self.local(repo={"pairs": {"repo:x": {"coding.git_push": 3},
                                                        "repo:x/feat-y": {"coding.git_push": 1}}}),
                             counterparty="repo:x/feat-y")
        self.assertEqual(answer.autonomy_level, 1)

    def test_a_branch_with_slashes_still_names_its_repository(self):
        self.assertEqual(decision.repository_slug("repo:x/feat/a/b"), "repo:x")
        self.assertIsNone(decision.repository_slug("repo:x"))
        answer = self.decide(self.local(user={"pairs": {"repo:x": {"coding.git_push": 1}}}),
                             counterparty="repo:x/feat/a")
        self.assertEqual(answer.autonomy_level, 1)

    def test_another_repository_is_not_matched(self):
        answer = self.decide(self.local(repo={"pairs": {"repo:x": {"coding.git_push": 1}}}),
                             counterparty="repo:xy/main")
        self.assertEqual(answer.autonomy_level, 3)


class PrMergeTests(Base):
    def test_pr_merge_is_a_known_class_a_policy_may_name(self):
        self.assertIn("coding.pr_merge", decision.ACTION_CLASSES)
        self.assertNotIn("coding.pr_merge", decision.BUILTIN_CAPS)
        answer = self.decide(self.local(repo={"defaults": {"coding.pr_merge": 1}}),
                             "coding.pr_merge", 3)
        self.assertEqual((answer.outcome, answer.autonomy_level), ("ask", 1))

    def test_the_null_provider_still_allows_everything(self):
        self.write(self.user_path, {"defaults": {"coding.pr_merge": 1}})
        answer = decision.NullProvider(target=str(self.ledger)).decide(
            decision.Action("coding.pr_merge", 3), "repo:x/main")
        self.assertEqual((answer.outcome, answer.autonomy_level, answer.reason),
                         ("allow", 3, "governance: none"))


class CommandTests(Base):
    def harness(self, *args):
        env = without_harness_vars()
        env.update({"HOME": str(self.home), "HARNESS_HOME": str(self.home)})
        return subprocess.run([sys.executable, str(REPO / "bin" / "harness"), *args],
                              capture_output=True, text=True, cwd=str(self.repo), env=env)

    def configure(self, provider):
        self.write(self.home / ".config" / "agent-harness" / "config.json",
                   {"governance": {"provider": provider}})

    def test_decide_answers_pr_merge_and_names_the_files_it_read(self):
        self.configure("local")
        self.write(self.user_path, {"pairs": {"repo:unknown": {"coding.pr_merge": 2}}})
        done = self.harness("decide", "--action", "coding.pr_merge", "--grade", "3", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertEqual(data["decision"]["autonomy_level"], 2)
        self.assertEqual(data["policy_files"],
                         [{"layer": "user policy", "path": str(self.user_path),
                           "present": True},
                          {"layer": "repository policy", "path": str(self.repo_path),
                           "present": False}])
        text = self.harness("decide", "--action", "coding.pr_merge", "--grade", "3")
        self.assertIn("user policy: " + str(self.user_path) + " (present)", text.stdout)
        self.assertIn("repository policy: " + str(self.repo_path) + " (absent)", text.stdout)

    def test_decide_under_none_reads_no_policy_file(self):
        self.write(self.user_path, "{not json")
        done = self.harness("decide", "--action", "coding.pr_merge", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertEqual(data["decision"]["outcome"], "allow")
        self.assertEqual(data["policy_files"], [])

    def test_a_bad_user_file_fails_decide_with_its_path_and_no_traceback(self):
        self.configure("local")
        self.write(self.user_path, "{not json")
        done = self.harness("decide", "--action", "coding.git_push")
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn(str(self.user_path), done.stderr)

    def test_doctor_names_the_policy_files(self):
        from importlib.machinery import SourceFileLoader
        import importlib.util

        loader = SourceFileLoader("harness_cli_scope", str(REPO / "bin" / "harness"))
        spec = importlib.util.spec_from_loader("harness_cli_scope", loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        lines = cli.governance_lines({"governance": {"provider": "local"}})
        joined = "\n".join(lines)
        self.assertIn("user policy: " + str(self.user_path) + " (absent)", joined)
        self.assertIn("repository policy: ", joined)
        none = "\n".join(cli.governance_lines({}))
        self.assertIn("policy files: none read by provider none", none)


if __name__ == "__main__":
    unittest.main()
