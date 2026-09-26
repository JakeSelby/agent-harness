"""Python 3.9 is the floor: no tracked source may use newer syntax, and CI runs the suite under it.

Only a 3.9 interpreter makes the parse exact: a newer one honours `feature_version` in part, and
3.12's f-string grammar ignores it. The required `test` job therefore runs this module under a real
3.9 before the suite, so it fails on 3.9-incompatible syntax even though `test-py39`, which runs the
whole suite under 3.9, is not a required check.
"""

import ast
import re
import subprocess
import sys
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

    def test_the_floor_interpreter_rejects_what_newer_parsers_let_through(self):
        # From 3.12 the parser accepts reused quotes inside an f-string whatever
        # `feature_version` says, so the parse is exact only on 3.9, which the required `test`
        # job provides.
        reused_quotes = 'd = {}\nx = f"{d["k"]}"\n'
        if sys.version_info[:2] == FLOOR:
            self.assertIsNotNone(floor_error(reused_quotes))
        elif sys.version_info >= (3, 12):
            self.assertIsNone(floor_error(reused_quotes))

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
    def job(self, name="test-py39"):
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        match = re.search(r"(?ms)^  " + re.escape(name) + r":\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)", text)
        self.assertIsNotNone(match, "ci.yml has no {} job".format(name))
        return text, match.group(1)

    def test_the_required_job_parses_under_a_real_floor_interpreter(self):
        _, job = self.job("test")
        setup = re.search(r"(?ms)^      - uses: actions/setup-python@[0-9a-f]{40} # v\d.*?(?=^      - )", job)
        self.assertIsNotNone(setup, "the test job installs no floor interpreter")
        self.assertRegex(setup.group(0), r'(?m)^          python-version: "3\.9"$')
        self.assertRegex(setup.group(0), r"(?m)^          update-environment: false$")
        self.assertIn("FLOOR_PYTHON: ${{ steps.floor.outputs.python-path }}", job)
        self.assertIn('run: \'"$FLOOR_PYTHON" -m unittest tests.test_python_floor -v\'', job)
        self.assertLess(job.index("tests.test_python_floor"), job.index("name: Unit tests"))

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
