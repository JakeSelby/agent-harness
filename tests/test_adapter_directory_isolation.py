"""What shared code may read inside a runtime's adapter directory, and nothing more.

Per-target evidence invalidation rests on a claim about coupling: a change under `adapters/codex`
cannot alter what a `claude-code` target observes. That is only true of the files no shared code
reads for another runtime. The catalog declares which files are shared — `harness tiers` reads
both adapters' `bindings.json`, capability coverage reads both `capabilities.json`, and a role
worker's runtime is chosen by flag — and this test holds the declaration to what the source does.
See lib/harness_core/compatibility.py and docs/compatibility.md.
"""
import ast
import subprocess
import unittest
from test_harness import REPO
from harness_core import compatibility

DECLARATION = compatibility.invalidation_declaration(compatibility.catalog(REPO))
RUNTIMES = sorted(DECLARATION["runtime_paths"])
SCANNED = ("bin", "lib", "primitives", "policy", "templates", "adapters")
# Every site that builds a path into an adapter directory today. The scan is worthless if it
# silently stops finding them, so it must keep finding at least these.
KNOWN_LOADERS = ("lib/harness_core/catalog.py", "lib/harness_core/compatibility.py",
                 "lib/harness_core/lifecycle.py", "lib/harness_core/workers.py",
                 "policy/hooks/posture.py")
VARIABLE = object()


def tracked(*paths):
    listed = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "--", *paths],
                                     text=True).splitlines()
    return [name for name in listed if (REPO / name).is_file()]


def is_python(path):
    return path.suffix == ".py" or path.name == "harness"


def literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return VARIABLE


def segments(node):
    """Flatten a `a / b / c` chain into its segments, with VARIABLE for anything not a literal."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return segments(node.left) + [literal(node.right)]
    return [literal(node)]


def adapter_reads(tree):
    """Every `adapters/<runtime>/<file>` path the code builds, as (line, runtime, file).

    A runtime segment resolved from a variable is reported as VARIABLE: it may be any runtime,
    including another target's, which is exactly what the shared-file declaration is about.
    """
    found = {}
    for node in ast.walk(tree):
        parts = []
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts = segments(node)
        elif isinstance(node, ast.Call):
            parts = [literal(argument) for argument in node.args]
        if "adapters" not in parts:
            continue
        index = parts.index("adapters")
        if len(parts) < index + 3:
            continue
        item = (node.lineno, parts[index + 1], parts[index + 2])
        # The walk sees a nested chain as well as the whole one; the longest wins per line.
        if found.get(node.lineno) is None or len(parts) > found[node.lineno][0]:
            found[node.lineno] = (len(parts), item)
    return [item for _, item in sorted(found.values())]


class DeclarationTests(unittest.TestCase):
    def test_the_catalog_declares_more_than_one_runtime_and_a_shared_file(self):
        # Either would make the assertions below vacuous: nothing to exclude, or nothing carved
        # back into the shared set.
        self.assertGreater(len(RUNTIMES), 1)
        self.assertTrue(DECLARATION["shared_files"])

    def test_every_declared_adapter_file_exists_in_every_runtime_directory(self):
        for runtime in RUNTIMES:
            for name in DECLARATION["shared_files"] + DECLARATION["runtime_files"]:
                with self.subTest(runtime=runtime, name=name):
                    self.assertTrue((REPO / "adapters" / runtime / name).is_file())


class AdapterIsolationTests(unittest.TestCase):
    def setUp(self):
        self.trees, self.unparsed = {}, []
        for name in tracked(*SCANNED):
            path = REPO / name
            if not is_python(path):
                continue
            try:
                self.trees[name] = ast.parse(path.read_text(errors="replace"))
            except (SyntaxError, ValueError) as error:
                self.unparsed.append((name, str(error)))

    def reads(self):
        return [(name, item) for name in sorted(self.trees)
                for item in adapter_reads(self.trees[name])]

    def test_every_scanned_python_file_parses(self):
        # An unparsed file is an unscanned file, and an unscanned loader is an unproven claim.
        self.assertEqual(self.unparsed, [])

    def test_the_scan_still_finds_the_loaders_it_is_meant_to_cover(self):
        found = sorted({name for name, _ in self.reads()})
        self.assertEqual(sorted(set(KNOWN_LOADERS) - set(found)), [])
        self.assertGreaterEqual(len(self.reads()), len(KNOWN_LOADERS))

    def test_shared_code_still_asks_a_loader_for_another_runtimes_files(self):
        """`harness tiers` reads both adapters' `bindings.json` in one command.

        The runtime travels as an argument, so no path in that file names a directory and the
        path scan cannot see it. This is the site the shared-file carve-out exists for, and the
        carve-out is unjustified if it ever stops happening.
        """
        passed = set()
        for node in ast.walk(self.trees["bin/harness"]):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "adapter_tiers":
                passed |= {literal(argument) for argument in node.args} & set(RUNTIMES)
        self.assertEqual(sorted(passed), RUNTIMES)
        self.assertIn("bindings.json", DECLARATION["shared_files"])

    def test_shared_code_reads_only_the_adapter_files_the_catalog_declares(self):
        declared = set(DECLARATION["shared_files"]) | set(DECLARATION["runtime_files"])
        undeclared = sorted({(name, item[2]) for name, item in self.reads()
                             if item[2] is not VARIABLE and item[2] not in declared})
        self.assertEqual(undeclared, [])

    def test_a_file_read_for_any_runtime_is_never_built_from_a_variable_name(self):
        # A variable file name would let a caller reach a file no declaration covers.
        self.assertEqual([(name, item[0]) for name, item in self.reads() if item[2] is VARIABLE], [])

    def test_no_source_file_names_another_runtimes_adapter_directory_outright(self):
        offenders = []
        for name, item in self.reads():
            owner = name.split("/")[1] if name.startswith("adapters/") else None
            if item[1] is not VARIABLE and item[1] != owner:
                offenders.append((name, item[0], item[1]))
        self.assertEqual(offenders, [])

    def test_no_adapter_file_mentions_another_runtime(self):
        for runtime in RUNTIMES:
            others = [name for name in RUNTIMES if name != runtime]
            for name in tracked("adapters/" + runtime):
                text = (REPO / name).read_text(errors="replace")
                for other in others:
                    with self.subTest(path=name, other=other):
                        self.assertNotIn(other, text)

    def test_no_tracked_source_file_is_a_symlink_out_of_its_own_directory(self):
        # A symlink would let a change under one adapter directory reach through another.
        for name in tracked(*SCANNED):
            path = REPO / name
            if not path.is_symlink():
                continue
            with self.subTest(path=name):
                self.assertEqual(path.resolve().parent, path.parent.resolve())

    def test_the_scan_catches_a_hardcoded_cross_read(self):
        planted = ['path = root / "adapters" / "codex" / "capabilities.json"',
                   'path = os.path.join(root, "adapters", "codex", "hook.py")']
        for code in planted:
            with self.subTest(code=code):
                self.assertEqual(adapter_reads(ast.parse(code))[0][1], "codex")

    def test_the_scan_reads_a_runtime_resolved_path_as_any_runtime(self):
        tree = ast.parse('path = root / "adapters" / runtime / "capabilities.json"')
        self.assertEqual(adapter_reads(tree), [(1, VARIABLE, "capabilities.json")])


if __name__ == "__main__":
    unittest.main()
