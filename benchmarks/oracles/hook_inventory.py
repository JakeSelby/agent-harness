"""Held-back check for the `hook-inventory` task: one entry per hook module, read from the tree."""
import ast
import json
from pathlib import Path

OUTPUT = "hook-inventory.json"


def expected(root):
    out = {}
    for path in sorted((Path(root) / "policy" / "hooks").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = (ast.get_docstring(tree) or "").strip().splitlines()
        out[path.name] = {"summary": " ".join(doc[0].split()) if doc else "",
                          "top_level_functions": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                                     for node in tree.body)}
    return out


def check(root):
    """Errors, empty when the inventory is exactly right."""
    path = Path(root) / OUTPUT
    if not path.is_file():
        return ["%s is missing" % OUTPUT]
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return ["%s is not JSON" % OUTPUT]
    want = expected(root)
    if not isinstance(got, dict) or sorted(got) != sorted(want):
        return ["the keys are not exactly the %d hook file names" % len(want)]
    errors = []
    for name, entry in sorted(want.items()):
        mine = got[name] if isinstance(got[name], dict) else {}
        if " ".join(str(mine.get("summary", "")).split()) != entry["summary"]:
            errors.append("%s: summary is not the docstring's first line" % name)
        if mine.get("top_level_functions") != entry["top_level_functions"]:
            errors.append("%s: top_level_functions should be %d" % (name, entry["top_level_functions"]))
    return errors


def solve(root):
    (Path(root) / OUTPUT).write_text(json.dumps(expected(root), indent=2) + "\n", encoding="utf-8")
