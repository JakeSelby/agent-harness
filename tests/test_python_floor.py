"""Python 3.9 is the floor: no tracked source may use newer syntax, and CI runs the suite under it.

The parse runs under whatever Python runs the suite, so the required `test` check fails on
3.9-incompatible syntax even though the `test-py39` job that runs the suite under 3.9 itself
is not a required check.
"""

import ast
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = (3, 9)


def python_sources():
    """Every tracked `.py` file, plus every tracked file whose shebang names Python."""
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.split("\0")
    found = []
    for name in filter(None, listed):
        path = ROOT / name
        if name.endswith(".py"):
            found.append(path)
            continue
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            first = handle.readline(200)
        if first.startswith(b"#!") and b"python" in first:
            found.append(path)
    return found


def floor_error(source, filename="<source>"):
    """The SyntaxError a 3.9 parser would raise on `source`, or None."""
    try:
        ast.parse(source, filename, feature_version=FLOOR)
    except SyntaxError as error:
        return error
    return None


class SyntaxFloorTests(unittest.TestCase):
    def test_the_floor_parse_rejects_newer_syntax(self):
        self.assertIsNotNone(floor_error("match x:\n    case 1:\n        pass\n"))
        self.assertIsNone(floor_error("if (n := 1):\n    pass\n"))

    def test_the_source_list_includes_extensionless_entry_points(self):
        names = {path.relative_to(ROOT).as_posix() for path in python_sources()}
        self.assertIn("bin/harness", names)
        self.assertIn("tests/test_python_floor.py", names)

    def test_every_tracked_python_source_parses_at_the_floor(self):
        failures = []
        for path in python_sources():
            error = floor_error(path.read_text(encoding="utf-8"), str(path))
            if error is not None:
                failures.append("{}:{}: {}".format(
                    path.relative_to(ROOT).as_posix(), error.lineno, error.msg))
        self.assertEqual(failures, [])


class FloorJobTests(unittest.TestCase):
    def job(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^  test-py39:\n(.*?)(?=^  [A-Za-z_-]+:\n|\Z)", text)
        self.assertIsNotNone(match, "ci.yml has no test-py39 job")
        return text, match.group(1)

    def test_the_job_runs_the_suite_under_the_floor_interpreter(self):
        _, job = self.job()
        self.assertIn("    name: test-py39\n", job)
        self.assertRegex(job, r'(?m)^          python-version: "3\.9"$')
        self.assertRegex(job, r"(?m)^        run: python -m unittest discover -s tests -v$")

    def test_the_interpreter_action_is_pinned_by_full_sha(self):
        _, job = self.job()
        self.assertRegex(job, r"(?m)^      - uses: actions/setup-python@[0-9a-f]{40} # v\d")

    def test_the_workflow_reaches_pull_requests_and_the_merge_queue(self):
        text, _ = self.job()
        trigger = re.search(r"(?ms)^on:\n(.*?)^\S", text).group(1)
        self.assertRegex(trigger, r"(?m)^  pull_request:")
        self.assertRegex(trigger, r"(?m)^  merge_group:")


if __name__ == "__main__":
    unittest.main()
