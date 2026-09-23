"""Held-back check for the `hook-ids` task: every hook module names itself in a `HOOK_ID` constant."""
import ast
from pathlib import Path

# The module count at the task's `parent_sha` in `benchmarks/tasks.json`, not at HEAD: every arm
# runs against that snapshot, so a hook module added since is not one the agent is asked to edit.
# `tests/test_doc_figures_derive_from_code.py` derives this number from the glob at that sha.
EXPECTED_MODULES = 18


def _modules(root):
    return sorted((Path(root) / "policy" / "hooks").glob("*.py"))


def check(root):
    """Errors, empty when every module still compiles and carries exactly one correct constant."""
    modules = _modules(root)
    errors = [] if len(modules) == EXPECTED_MODULES else ["expected %d hook modules, found %d"
                                                          % (EXPECTED_MODULES, len(modules))]
    for path in modules:
        source = path.read_text(encoding="utf-8")
        try:
            compile(source, path.name, "exec")  # catches a constant placed before a __future__ import
            tree = ast.parse(source)
        except SyntaxError as exc:
            errors.append("%s: no longer compiles (%s)" % (path.name, exc.msg))
            continue
        values = [node.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "HOOK_ID" for t in node.targets)]
        if len(values) != 1 or not isinstance(values[0], ast.Constant) or values[0].value != path.stem:
            errors.append("%s: needs exactly one top-level HOOK_ID = %r" % (path.name, path.stem))
    return errors


def solve(root):
    for path in _modules(root):
        lines = path.read_text(encoding="utf-8").splitlines(True)
        tree = ast.parse("".join(lines))
        after = 0
        for node in tree.body:
            docstring = node is tree.body[0] and isinstance(node, ast.Expr) and isinstance(
                getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str)
            if docstring or isinstance(node, (ast.Import, ast.ImportFrom)):
                after = node.end_lineno
            else:
                break
        lines.insert(after, 'HOOK_ID = "%s"\n' % path.stem)
        path.write_text("".join(lines), encoding="utf-8")
