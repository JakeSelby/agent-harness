"""A change under one runtime's adapter directory invalidates only that runtime's evidence."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_harness import REPO
from harness_core import compatibility


SCOPE = {"version": 1,
         "runtime_paths": {"claude-code": "adapters/claude-code", "codex": "adapters/codex"},
         "shared_files": ["capabilities.json"], "runtime_files": ["hook.py"]}
CLIENTS = [{"runtime": "claude-code"}, {"runtime": "codex"}, {"runtime": "cursor"}]


def declaring(scope=SCOPE):
    """A catalog fragment that declares `scope` for the runtimes its clients run."""
    return {"clients": CLIENTS, "evidence_invalidation": scope}


class ScopeDeclarationTests(unittest.TestCase):
    def test_the_repository_catalog_maps_every_runtime_that_has_an_adapter(self):
        data = compatibility.catalog(REPO)
        scopes = compatibility.runtime_scopes(data)
        adapters = sorted(path.name for path in (REPO / "adapters").iterdir() if path.is_dir())
        self.assertEqual(sorted(scopes), adapters)
        for runtime, path in scopes.items():
            self.assertTrue((REPO / path).is_dir(), path)
            self.assertEqual(path, "adapters/" + runtime)

    def test_an_undeclared_or_unmapped_runtime_keeps_the_whole_source_rule(self):
        for data in ({}, declaring()):
            with self.subTest(data=data):
                scope = compatibility.evidence_scope(data, {"runtime": "cursor"})
                self.assertEqual((scope["excluded"], scope["shared"]), ([], []))
                self.assertEqual(compatibility.scope_pathspec(scope),
                                 list(compatibility.SOURCE_PATHS))

    def test_a_mapped_runtime_is_scoped_to_shared_source_and_its_own_adapter(self):
        scope = compatibility.evidence_scope(declaring(), {"runtime": "claude-code"})
        self.assertEqual(scope["excluded"], ["adapters/codex"])
        self.assertEqual(scope["shared"], ["adapters/codex/capabilities.json"])
        self.assertEqual(compatibility.scope_pathspec(scope)[-1],
                         ":(exclude,literal)adapters/codex")
        self.assertIn("adapters", compatibility.scope_pathspec(scope))

    def test_a_record_whose_scope_lists_are_not_strings_is_a_refusal_not_a_traceback(self):
        scope = compatibility.evidence_scope(declaring(), {"runtime": "claude-code"})
        for broken in ({"version": 1}, {"version": 1, "paths": "adapters", "excluded": [],
                                        "shared": []},
                       dict(scope, excluded=[None]), dict(scope, shared=[{"path": "adapters"}]),
                       dict(scope, version=2), "not an object"):
            with self.subTest(broken=broken):
                self.assertFalse(compatibility.same_scope(broken, scope))
        self.assertTrue(compatibility.same_scope(dict(scope), scope))

    def test_a_runtime_with_no_adapter_directory_narrows_nothing_for_anyone(self):
        # `adapters/cursor` does not exist, so declaring it excludes no file from any diff; the
        # isolation test is what holds the declared directories to files that are really there.
        scope = compatibility.evidence_scope(
            declaring(dict(SCOPE, runtime_paths=dict(SCOPE["runtime_paths"],
                                                     cursor="adapters/cursor"))),
            {"runtime": "cursor"})
        self.assertEqual(sorted(scope["excluded"]), ["adapters/claude-code", "adapters/codex"])

    def test_a_scope_that_does_not_name_a_runtimes_own_directory_is_refused(self):
        paths = SCOPE["runtime_paths"]
        cases = [
            (dict(SCOPE, version=2), "unsupported evidence"),
            (dict(SCOPE, runtime_paths={"codex": "adapters/codex"}), "two or more runtime"),
            (dict(SCOPE, runtime_paths=["adapters/codex"]), "two or more runtime"),
            (dict(SCOPE, runtime_paths={"claude-code": "adapters/codex",
                                        "codex": "adapters/codex"}), "own adapter directory"),
            (dict(SCOPE, runtime_paths={"claude-code": "lib", "codex": "adapters/codex"}),
             "own adapter directory"),
            (dict(SCOPE, runtime_paths=dict(paths, **{"grok": "adapters/grok"})),
             "no client runs"),
            (dict(SCOPE, runtime_paths=dict(paths, **{"../codex": "adapters/../codex"})),
             "no client runs"),
            (dict(SCOPE, shared_files=[]), "requires the shared file names"),
            (dict(SCOPE, shared_files=["adapters/codex/capabilities.json"]), "plain file names"),
            (dict(SCOPE, shared_files=["../capabilities.json"]), "plain file names"),
            (dict(SCOPE, runtime_files=".."), "plain file names"),
            (dict(SCOPE, runtime_files=["capabilities.json"]), "shared or per-runtime"),
        ]
        for declared, message in cases:
            with self.subTest(declared=declared):
                with self.assertRaisesRegex(ValueError, message):
                    compatibility.runtime_scopes(declaring(declared))


class ScopedInvalidationTests(unittest.TestCase):
    """The invalidation diff, run against a real repository rather than a mocked git."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name) / "work"
        (self.work / "adapters" / "claude-code").mkdir(parents=True)
        (self.work / "adapters" / "codex").mkdir(parents=True)
        (self.work / "lib").mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.write("VERSION", "1.0.0\n")
        self.write("lib/core.py", "shared = 1\n")
        for runtime in ("claude-code", "codex"):
            self.write("adapters/" + runtime + "/hook.py", "print('one')\n")
            self.write("adapters/" + runtime + "/capabilities.json", "{}\n")
        self.commit("qualification source")
        self.data = dict(declaring(), harness_version="1.0.0", required_cases=["installation"])
        self.record = {"kind": "native", "harness_version": "1.0.0", "runtime_version": "1.2",
                       "client_version": "1.2", "platform": "fixture-os",
                       "source_commit": self.git("rev-parse", "HEAD"),
                       "observations": ["Synthetic validation fixture"],
                       "cases": {"installation": "passed"}}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.work), "-c", "user.name=t",
                                        "-c", "user.email=t", *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def write(self, name, text):
        (self.work / name).write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", message)
        return self.git("rev-parse", "HEAD")

    def client(self, runtime, scoped=True):
        """A client whose single evidence record claims the scope the catalog grants it."""
        identifier = runtime + "-cli"
        entry = {"id": identifier, "runtime": runtime, "runtime_version": "1.2",
                 "client_version": "1.2", "platform": "fixture-os", "evidence": []}
        record = dict(self.record, client=identifier)
        if scoped:
            record["invalidation_scope"] = compatibility.evidence_scope(self.data, entry)
        path = self.work / (identifier + ".json")
        path.write_text(json.dumps(record))
        entry["evidence"] = [{"path": path.name,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        return entry

    def errors(self, runtime, scoped=True):
        return compatibility.evidence_errors(self.work, self.data, self.client(runtime, scoped))

    def test_a_codex_adapter_change_leaves_claude_code_evidence_standing(self):
        self.write("adapters/codex/hook.py", "print('two')\n")
        self.commit("codex adapter fix")
        self.assertEqual(self.errors("claude-code"), [])
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors("codex"))

    def test_a_claude_code_adapter_change_leaves_codex_evidence_standing(self):
        self.write("adapters/claude-code/hook.py", "print('two')\n")
        self.commit("claude-code adapter fix")
        self.assertEqual(self.errors("codex"), [])
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors("claude-code"))

    def test_a_shared_source_change_still_invalidates_every_target(self):
        self.write("lib/core.py", "shared = 2\n")
        self.commit("shared fix")
        for runtime in ("claude-code", "codex"):
            with self.subTest(runtime=runtime):
                self.assertIn("runtime source changed or evidence commit is unavailable",
                              self.errors(runtime))

    def test_a_shared_file_in_another_runtimes_directory_invalidates_every_target(self):
        # `capabilities.json` is read for every runtime whatever the session runs, so it is
        # carved back into the shared set even inside an excluded directory.
        self.write("adapters/codex/capabilities.json", '{"stances": {}}\n')
        self.commit("codex capabilities change")
        for runtime in ("claude-code", "codex"):
            with self.subTest(runtime=runtime):
                self.assertIn("runtime source changed or evidence commit is unavailable",
                              self.errors(runtime))

    def test_an_adapter_file_no_runtime_owns_invalidates_every_target(self):
        self.write("adapters/README.md", "shared adapter note\n")
        self.commit("shared adapter file")
        for runtime in ("claude-code", "codex"):
            with self.subTest(runtime=runtime):
                self.assertIn("runtime source changed or evidence commit is unavailable",
                              self.errors(runtime))

    def test_a_record_claiming_no_scope_keeps_the_whole_source_rule(self):
        self.write("adapters/codex/hook.py", "print('two')\n")
        self.commit("codex adapter fix")
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors("claude-code", scoped=False))

    def test_a_record_claiming_a_scope_the_catalog_withholds_is_refused(self):
        entry = self.client("claude-code")
        path = self.work / entry["evidence"][0]["path"]
        record = json.loads(path.read_text())
        record["invalidation_scope"]["excluded"] = ["adapters/codex", "lib"]
        path.write_text(json.dumps(record))
        entry["evidence"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(compatibility.evidence_errors(self.work, self.data, entry),
                         ["evidence claims an invalidation scope the catalog does not grant",
                          "missing acceptance cases: installation"])

    def test_evidence_still_qualifies_when_nothing_changed(self):
        for runtime in ("claude-code", "codex"):
            with self.subTest(runtime=runtime):
                self.assertEqual(self.errors(runtime), [])


if __name__ == "__main__":
    unittest.main()
