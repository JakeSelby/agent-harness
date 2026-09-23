"""Regression coverage for delivery issue ownership."""

import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

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


class BmadMappingTests(unittest.TestCase):
    def write_map(self, directory, numbers):
        path = Path(directory) / 'issue-map.json'
        path.write_text(json.dumps({'items': [
            {'github_number': number, 'bmad_id': 'AH-S{:03d}'.format(number)} for number in numbers]}))
        return path

    def test_mapped_issue_passes_and_reports_its_id(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(checker.require_mapping(10, self.write_map(temp, [9, 10])), 'AH-S010')

    def test_unmapped_issue_fails_and_names_the_reserve_command(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, r'#11 has no BMad ID.*reserve --issue 11'):
                checker.require_mapping(11, self.write_map(temp, [10]))

    def test_missing_or_malformed_map_fails_and_names_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'issue-map.json'
            for content in (None, '[]', '{}', '{"items": [{"github_number": 10}]}', 'not json'):
                if content is not None:
                    path.write_text(content)
                with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'issue-map.json is missing or malformed'):
                    checker.require_mapping(10, path)

    def run_main(self, numbers):
        page = {'data': {'repository': {'pullRequests': {'nodes': [pr(1, [10])]}}}}
        result = mock.Mock(stdout=json.dumps([page]))
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            checker, 'ISSUE_MAP', self.write_map(temp, numbers)
        ), mock.patch.object(checker.subprocess, 'run', return_value=result), mock.patch.object(
            checker, 'require_story_depth', return_value='depth: ok'
        ), mock.patch.dict(
            os.environ, {'GITHUB_REPOSITORY': 'owner/repo', 'PR_NUMBER': '1'}
        ), redirect_stdout(io.StringIO()) as out:
            checker.main()
        return out.getvalue()

    def test_main_refuses_a_pull_request_whose_delivery_issue_is_unmapped(self):
        self.assertIn('#10 (AH-S010)', self.run_main([10]))
        with self.assertRaisesRegex(ValueError, '#10 has no BMad ID'):
            self.run_main([11])

    def test_this_repository_has_an_issue_map_where_the_check_looks(self):
        self.assertTrue(checker.ISSUE_MAP.is_file())

