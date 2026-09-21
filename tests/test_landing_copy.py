"""Regression coverage for the check that keeps product.json current with capability changes."""

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'landing_copy', ROOT / '.github/scripts/check_landing_copy.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

REASON = 'Landing copy: internal refactor with no user-visible capability change.'


def runner(files, body):
    """Replay recorded gh output: the files listing first, then the pull request body."""
    replies = [mock.Mock(stdout=''.join(path + '\n' for path in files)), mock.Mock(stdout=body)]

    def run(argv, **kwargs):
        self_check = argv[0] == 'gh'
        if not self_check:
            raise AssertionError('the check may only call gh')
        return replies.pop(0)

    return run


class ValidateTests(unittest.TestCase):
    def test_a_capability_change_without_product_json_or_an_escape_fails(self):
        with self.assertRaises(ValueError) as caught:
            checker.validate(['bin/harness'], 'What and why\n\nCloses #1')
        message = str(caught.exception)
        self.assertIn('bin/harness', message)
        self.assertIn('product.json', message)
        self.assertIn('Landing copy:', message)

    def test_every_capability_root_fires(self):
        for path in ('bin/harness', 'lib/usage.sh', 'adapters/claude/bindings.json',
                     'primitives/rules/secrets.md', 'policy/lifecycle.json'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                checker.validate([path], '')

    def test_a_product_json_change_satisfies_the_rule(self):
        self.assertIn('product.json', checker.validate(['bin/harness', 'product.json'], ''))

    def test_an_escape_line_with_a_real_reason_satisfies_the_rule(self):
        message = checker.validate(['bin/harness'], 'What and why\n\n' + REASON + '\n\nCloses #1')
        self.assertIn('internal refactor', message)

    def test_a_short_or_bare_escape_line_does_not_satisfy_the_rule(self):
        for body in ('Landing copy:', 'Landing copy: n/a', 'Landing copy:   ', 'landing copy: '
                     'this reads like the escape but the prefix is lowercase'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                checker.validate(['bin/harness'], body)

    def test_a_docs_tests_or_ci_only_change_never_fires(self):
        for files in (['docs/usage.md', 'README.md'], ['tests/test_harness.py'],
                      ['.github/workflows/ci.yml', '.github/scripts/check_landing_copy.py']):
            with self.subTest(files=files):
                self.assertIn('does not apply', checker.validate(files, ''))

    def test_a_path_that_merely_contains_a_root_name_does_not_fire(self):
        self.assertIn('does not apply', checker.validate(['docs/primitives-guide.md'], ''))

    def test_an_absent_body_is_treated_as_no_escape(self):
        self.assertIsNone(checker.reason(None))


class MainTests(unittest.TestCase):
    def run_main(self, files, body):
        with mock.patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'PR_NUMBER': '7'}), \
                redirect_stdout(io.StringIO()) as out:
            checker.main(runner(files, body))
        return out.getvalue()

    def test_main_reads_the_changed_files_and_the_body_and_reports_the_verdict(self):
        self.assertIn('waived', self.run_main(['bin/harness'], REASON))
        self.assertIn('product.json', self.run_main(['bin/harness', 'product.json'], ''))

    def test_main_raises_when_neither_way_is_satisfied(self):
        with self.assertRaisesRegex(ValueError, 'Landing copy:'):
            self.run_main(['bin/harness'], 'Closes #1')


class WorkflowTests(unittest.TestCase):
    def test_the_workflow_runs_the_check_on_pull_requests_with_read_only_permissions(self):
        text = (ROOT / '.github/workflows/landing-copy.yml').read_text()
        self.assertIn('types: [opened, edited, reopened, synchronize, ready_for_review]', text)
        self.assertIn('\npermissions:\n  contents: read\n', text)
        self.assertNotIn('write', text)
        self.assertIn('run: python3 .github/scripts/check_landing_copy.py', text)

    def test_the_issue_ownership_check_name_is_untouched(self):
        text = (ROOT / '.github/workflows/issue-ownership.yml').read_text()
        self.assertIn('    name: issue-ownership\n', text)

    def test_the_pull_request_template_names_the_escape(self):
        self.assertIn('Landing copy:', (ROOT / '.github/PULL_REQUEST_TEMPLATE.md').read_text())

    def test_the_repository_rule_is_written_down_where_contributors_read_it(self):
        self.assertIn('landing-copy', (ROOT / 'AGENTS.md').read_text())
