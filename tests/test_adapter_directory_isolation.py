"""Each runtime's loader reads its own adapter directory and never another runtime's.

This is the claim per-target evidence invalidation rests on: if no `claude-code` loader can read
a file under `adapters/codex`, a change there cannot alter what a `claude-code` target observes.
See lib/harness_core/compatibility.py and docs/compatibility.md.
"""
import ast
import subprocess
import unittest
from test_harness import REPO
from harness_core import compatibility

RUNTIMES = sorted(compatibility.runtime_scopes(compatibility.catalog(REPO)))
SCANNED = ("bin", "lib", "primitives", "policy", "templates", "adapters")


def source_files():
    """Every tracked file under the shared runtime-source paths, adapters included."""
    listed = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "--", *SCANNED],
                                     text=True).splitlines()
    for name in listed:
        path = REPO / name
        if path.is_file():
            yield path


def parsed(path):
    """The syntax tree of a Python source file, or None when the file is not Python."""
    if path.suffix != ".py" and path.name != "harness":
        return None
    try:
        return ast.parse(path.read_text(errors="replace"))
    except (SyntaxError, ValueError):
        return None


def docstring_ids(tree):
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None) if isinstance(node, holders) else None
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            found.add(id(body[0].value))
    return found


def literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def cross_reads(tree, runtimes):
    """Lines that name a runtime's adapter directory instead of resolving it from a variable.

    Prose is not code: a docstring or a comment may name a directory. Only executable path
    building counts, whether it is written as one literal or joined segment by segment.
    """
    found, skip = [], docstring_ids(tree)
    for node in ast.walk(tree):
        value = literal(node)
        if value is not None and id(node) not in skip:
            if any("adapters/" + runtime in value for runtime in runtimes):
                found.append((node.lineno, value))
            continue
        segments = []
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            segments = [literal(node.left.right) if isinstance(node.left, ast.BinOp) else None,
                        literal(node.right)]
        if isinstance(node, ast.Call):
            for index in range(len(node.args) - 1):
                if literal(node.args[index]) == "adapters":
                    segments = ["adapters", literal(node.args[index + 1])]
        if segments[:1] == ["adapters"] and segments[1] in runtimes:
            found.append((node.lineno, "adapters/" + segments[1]))
    return found


class AdapterIsolationTests(unittest.TestCase):
    def test_the_catalog_maps_more_than_one_runtime(self):
        # A single-runtime catalog would make every assertion below vacuously true.
        self.assertGreater(len(RUNTIMES), 1)

    def test_no_adapter_file_mentions_another_runtimes_directory(self):
        for runtime in RUNTIMES:
            others = [name for name in RUNTIMES if name != runtime]
            for path in sorted((REPO / "adapters" / runtime).rglob("*")):
                if not path.is_file():
                    continue
                text = path.read_text(errors="replace")
                for other in others:
                    with self.subTest(path=path.name, runtime=runtime, other=other):
                        self.assertNotIn(other, text)

    def test_no_runtime_source_file_hardcodes_an_adapter_directory(self):
        offenders = []
        for path in source_files():
            tree = parsed(path)
            if tree is None:
                continue
            offenders += [(str(path.relative_to(REPO)), line, value)
                          for line, value in cross_reads(tree, RUNTIMES)]
        self.assertEqual(offenders, [])

    def test_a_json_or_text_source_file_names_no_other_runtimes_adapter(self):
        # The Python scan reads syntax; a data file is checked as the text it is. Prose is
        # excluded here as it is there: shared instruction text may name any directory.
        for path in source_files():
            if path.suffix in ("", ".py", ".md"):
                continue
            text = path.read_text(errors="replace")
            for runtime in RUNTIMES:
                with self.subTest(path=str(path.relative_to(REPO)), runtime=runtime):
                    self.assertNotIn("adapters/" + runtime, text)

    def test_the_detector_catches_a_hardcoded_cross_read(self):
        planted = [
            'path = root / "adapters" / "codex" / "capabilities.json"',
            'path = open("adapters/codex/hook.py")',
            'path = os.path.join(root, "adapters", "codex", "hook.py")',
        ]
        for code in planted:
            with self.subTest(code=code):
                self.assertTrue(cross_reads(ast.parse(code), RUNTIMES))

    def test_the_detector_passes_a_runtime_resolved_read(self):
        clean = ['path = root / "adapters" / runtime / "capabilities.json"',
                 '"""A docstring may name adapters/codex/capabilities.json."""']
        for code in clean:
            with self.subTest(code=code):
                self.assertEqual(cross_reads(ast.parse(code), RUNTIMES), [])


if __name__ == "__main__":
    unittest.main()
