"""A change under a path the case-to-path map assigns invalidates only the cases that name it."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_harness import REPO
from harness_core import compatibility


WORKERS = ["adapters/claude-code/worker.py", "adapters/codex/worker.py"]
REQUIRED = ["installation", "role-confinement"]
MAP = {"version": 1, "cases": {"installation": [], "role-confinement": list(WORKERS)}}
SCOPE = {"version": 1,
         "runtime_paths": {"claude-code": "adapters/claude-code", "codex": "adapters/codex"},
         "shared_files": ["capabilities.json", "worker.py"], "runtime_files": ["hook.py"]}
CLIENTS = [{"runtime": "claude-code"}, {"runtime": "codex"}]


def declaring(case_paths=MAP, required=REQUIRED):
    """A catalog fragment that declares `case_paths` inside the invalidation block."""
    block = dict(SCOPE, case_paths=case_paths) if case_paths is not None else dict(SCOPE)
    return {"clients": CLIENTS, "required_cases": list(required), "evidence_invalidation": block}


class CaseMapDeclarationTests(unittest.TestCase):
    def test_the_repository_map_names_every_required_case_and_only_paths_that_exist(self):
        data = compatibility.catalog(REPO)
        declared = compatibility.case_path_map(data)
        self.assertEqual(sorted(declared["cases"]), sorted(data["required_cases"]))
        for case, paths in declared["cases"].items():
            for path in paths:
                with self.subTest(case=case, path=path):
                    self.assertTrue((REPO / path).exists(), path)
        self.assertEqual(compatibility.case_map_identity(data)["version"], declared["version"])

    def test_no_map_means_no_identity_and_every_record_keeps_the_whole_target(self):
        data = declaring(None)
        self.assertEqual(compatibility.case_path_map(data), {})
        self.assertIsNone(compatibility.case_map_identity(data))
        self.assertIsNone(compatibility.stale_cases(data, {"case_map": None}, ["lib/core.py"]))

    def test_a_map_that_is_not_literal_complete_and_versioned_is_refused(self):
        cases = MAP["cases"]
        refused = [
            (dict(MAP, version=0), "positive integer version"),
            (dict(MAP, version="1"), "positive integer version"),
            (dict(MAP, version=True), "positive integer version"),
            ({"cases": cases}, "positive integer version"),
            (dict(MAP, cases={"installation": []}), "every required case"),
            (dict(MAP, cases=dict(cases, extra=[])), "every required case"),
            (dict(MAP, cases=list(cases)), "every required case"),
        ]
        for path in ("adapters/*/worker.py", "adapters/codex/../lib", "/lib", "lib/", "lib//x",
                     "docs/compatibility.md", "", None, "adapters/codex/w?rker.py"):
            refused.append((dict(MAP, cases=dict(cases, installation=[path])), "installation"))
        refused.append((dict(MAP, cases=dict(cases, installation=["lib", "lib"])), "installation"))
        refused.append((dict(MAP, cases=dict(cases, installation="lib")), "installation"))
        for declared, message in refused:
            with self.subTest(declared=declared):
                with self.assertRaisesRegex(ValueError, message):
                    compatibility.case_path_map(declaring(declared))

    def test_the_identity_moves_with_the_map_even_when_the_version_does_not(self):
        before = compatibility.case_map_identity(declaring())
        edited = compatibility.case_map_identity(
            declaring(dict(MAP, cases=dict(MAP["cases"], installation=["lib"]))))
        reordered = compatibility.case_map_identity(
            declaring(dict(MAP, cases=dict(MAP["cases"], **{"role-confinement": WORKERS[::-1]}))))
        self.assertEqual(before["version"], edited["version"])
        self.assertNotEqual(before["sha256"], edited["sha256"])
        self.assertEqual(before, reordered)

    def test_a_directory_entry_covers_the_files_under_it_and_nothing_beside_it(self):
        data = declaring(dict(MAP, cases=dict(MAP["cases"], installation=["policy/hooks"])))
        record = {"case_map": compatibility.case_map_identity(data)}
        self.assertEqual(compatibility.stale_cases(data, record, ["policy/hooks/stop-gate.py"]),
                         {"installation": ["policy/hooks/stop-gate.py"]})
        self.assertIsNone(compatibility.stale_cases(data, record, ["policy/hooks-extra.py"]))


class CaseScopedInvalidationTests(unittest.TestCase):
    """The per-case diff, run against a real repository rather than a mocked git."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name) / "work"
        for runtime in ("claude-code", "codex"):
            (self.work / "adapters" / runtime).mkdir(parents=True)
        (self.work / "lib").mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.write("VERSION", "1.0.0\n")
        self.write("lib/core.py", "shared = 1\n")
        for runtime in ("claude-code", "codex"):
            for name in ("hook.py", "worker.py"):
                self.write("adapters/" + runtime + "/" + name, "print('one')\n")
        self.commit("qualification source")
        self.data = dict(declaring(), harness_version="1.0.0")
        self.source = self.git("rev-parse", "HEAD")

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

    def record(self, cases, source=None, **changes):
        record = {"kind": "native", "client": "claude-code-cli", "harness_version": "1.0.0",
                  "runtime_version": "1.2", "client_version": "1.2", "platform": "fixture-os",
                  "source_commit": source or self.source,
                  "observations": ["Synthetic validation fixture"], "cases": cases,
                  "invalidation_scope": compatibility.evidence_scope(self.data, self.entry()),
                  "case_map": compatibility.case_map_identity(self.data)}
        record.update(changes)
        return record

    def entry(self, *records):
        entry = {"id": "claude-code-cli", "runtime": "claude-code", "runtime_version": "1.2",
                 "client_version": "1.2", "platform": "fixture-os", "evidence": []}
        for number, record in enumerate(records):
            path = self.work / ("record-%d.json" % number)
            path.write_text(json.dumps({key: value for key, value in record.items()
                                        if value is not None}))
            entry["evidence"].append({"path": path.name,
                                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return entry

    def errors(self, *records):
        return compatibility.evidence_errors(self.work, self.data, self.entry(*records))

    def passing(self, **changes):
        return self.record({case: "passed" for case in REQUIRED}, **changes)

    def test_a_worker_change_leaves_the_cases_that_do_not_name_it_standing(self):
        self.write("adapters/codex/worker.py", "print('two')\n")
        self.commit("worker fix")
        self.assertEqual(self.errors(self.passing()),
                         ["role-confinement is stale in linked evidence: source changed under "
                          "adapters/codex/worker.py"])

    def test_a_rerun_of_only_the_stale_case_completes_the_claim(self):
        self.write("adapters/claude-code/worker.py", "print('two')\n")
        fixed = self.commit("worker fix")
        rerun = self.record({"role-confinement": "passed"}, source=fixed)
        self.assertEqual(self.errors(self.passing(), rerun), [])

    def test_a_stale_failure_neither_passes_nor_blocks_a_rerun(self):
        failed = self.record({"installation": "passed", "role-confinement": "failed"})
        self.write("adapters/claude-code/worker.py", "print('two')\n")
        fixed = self.commit("worker fix")
        self.assertEqual(self.errors(failed), ["role-confinement is stale in linked evidence: "
                                               "source changed under adapters/claude-code/worker.py"])
        rerun = self.record({"role-confinement": "passed"}, source=fixed)
        self.assertEqual(self.errors(failed, rerun), [])

    def test_a_change_under_a_path_no_case_maps_invalidates_the_whole_record(self):
        self.write("lib/core.py", "shared = 2\n")
        self.commit("shared fix")
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors(self.passing()))

    def test_one_unmapped_file_beside_a_mapped_one_still_invalidates_everything(self):
        self.write("adapters/codex/worker.py", "print('two')\n")
        self.write("lib/core.py", "shared = 2\n")
        self.commit("worker and shared fix")
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors(self.passing()))

    def test_a_record_without_a_map_version_is_whole_target_scoped(self):
        self.write("adapters/codex/worker.py", "print('two')\n")
        self.commit("worker fix")
        self.assertIn("runtime source changed or evidence commit is unavailable",
                      self.errors(self.passing(case_map=None)))

    def test_a_record_under_another_map_is_whole_target_scoped(self):
        self.write("adapters/codex/worker.py", "print('two')\n")
        self.commit("worker fix")
        identity = compatibility.case_map_identity(self.data)
        for stated in (dict(identity, version=2), dict(identity, sha256="0" * 64), "1", 1):
            with self.subTest(stated=stated):
                self.assertIn("runtime source changed or evidence commit is unavailable",
                              self.errors(self.passing(case_map=stated)))

    def test_per_target_scoping_still_applies_before_the_map_is_read(self):
        # The other runtime's private hook is outside this target's path set, so no case of the
        # Claude Code record is touched, mapped or not.
        self.write("adapters/codex/hook.py", "print('two')\n")
        self.commit("codex hook fix")
        self.assertEqual(self.errors(self.passing()), [])

    def test_an_unchanged_source_qualifies_every_case(self):
        self.assertEqual(self.errors(self.passing()), [])


if __name__ == "__main__":
    unittest.main()
