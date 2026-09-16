# SPDX-License-Identifier: MIT
"""Unit tests for templates/repo. Run: python3 -m unittest discover tests

The allow rules are pinned to the committed list so a change to the deny rules cannot
quietly widen or drop what the template lets agents run.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SETTINGS = json.loads((REPO / "templates" / "repo" / "settings.json").read_text(encoding="utf-8"))
DENY_FORM = re.compile(r"^Read\(\./.+\)$")
COMMITTED_ALLOW = ["Bash(pnpm run quality)", "Bash(pnpm test *)", "Bash(pnpm install)"]
SECRET_PATTERNS = ["./.env", "./.env.*", "./**/*.pem", "./**/*.key"]


class RepoSettingsTemplateTests(unittest.TestCase):
    def test_template_is_a_settings_object(self):
        self.assertIsInstance(SETTINGS, dict)
        self.assertIsInstance(SETTINGS["permissions"], dict)

    def test_deny_rules_are_present(self):
        deny = SETTINGS["permissions"]["deny"]
        self.assertIsInstance(deny, list)
        self.assertTrue(deny)

    def test_every_deny_rule_is_a_relative_read_rule(self):
        for rule in SETTINGS["permissions"]["deny"]:
            self.assertRegex(rule, DENY_FORM, msg=rule)

    def test_secret_files_are_denied(self):
        deny = SETTINGS["permissions"]["deny"]
        for pattern in SECRET_PATTERNS:
            self.assertIn("Read(%s)" % pattern, deny)

    def test_generated_directories_are_denied(self):
        deny = SETTINGS["permissions"]["deny"]
        self.assertTrue(any(r.endswith("/**)") for r in deny))

    def test_allow_rules_are_unchanged(self):
        self.assertEqual(SETTINGS["permissions"]["allow"], COMMITTED_ALLOW)


if __name__ == "__main__":
    unittest.main()
