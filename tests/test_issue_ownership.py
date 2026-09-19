"""Regression coverage for delivery issue ownership."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'issue_ownership', Path(__file__).resolve().parents[1] / '.github/scripts/check_issue_ownership.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def pr(number, issues, state='OPEN', merged=False, repository='owner/repo'):
    return {'number': number, 'state': state, 'merged': merged,
            'closingIssuesReferences': {'totalCount': len(issues), 'nodes': [
                {'number': issue, 'repository': {'nameWithOwner': repository}} for issue in issues]}}


class IssueOwnershipTests(unittest.TestCase):
    def test_unique_issue(self):
        self.assertEqual(checker.validate([pr(1, [10]), pr(2, [11])], 1, 'owner/repo'), 10)

    def test_missing_multiple_and_foreign(self):
        for current in (pr(1, []), pr(1, [10, 11]), pr(1, [10], repository='other/repo')):
            with self.subTest(current=current), self.assertRaises(ValueError):
                checker.validate([current], 1, 'owner/repo')

    def test_open_and_merged_competitors_fail(self):
        for other in (pr(2, [10]), pr(2, [10], 'MERGED', True)):
            with self.subTest(other=other), self.assertRaises(ValueError):
                checker.validate([pr(1, [10]), other], 1, 'owner/repo')

    def test_closed_unmerged_replacement_allowed(self):
        self.assertEqual(checker.validate([pr(1, [10]), pr(2, [10], 'CLOSED')], 1, 'owner/repo'), 10)

    def test_same_number_in_other_repo_does_not_collide(self):
        self.assertEqual(checker.validate([
            pr(1, [10]), pr(2, [10], repository='other/repo')], 1, 'owner/repo'), 10)

    def test_unknown_and_truncated_data_fail(self):
        with self.assertRaises(ValueError):
            checker.validate([], 1, 'owner/repo')
        truncated = pr(2, [])
        truncated['closingIssuesReferences']['totalCount'] = 1
        with self.assertRaises(ValueError):
            checker.validate([pr(1, [10]), truncated], 1, 'owner/repo')
