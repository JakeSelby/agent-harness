# SPDX-License-Identifier: MIT
"""`usage --rules` is discoverable: from `harness --help`, and from the top of the usage doc.

A flag documented only in the parser is a flag nobody finds, so the banner and the doc are
checked against the parser's own choices rather than against a copy of them.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
USAGE_DOC = REPO / "docs" / "usage.md"


def help_text():
    out = subprocess.run([sys.executable, str(REPO / "bin" / "harness"), "--help"],
                         capture_output=True, text=True)
    return out.stdout + out.stderr


class HelpBannerTests(unittest.TestCase):
    def test_the_banner_names_the_rules_report(self):
        self.assertIn("usage   --rules", help_text())

    def test_the_banner_names_every_rules_grouping(self):
        self.assertIn("--by rule|repo|stance", help_text())

    def test_the_banner_lists_the_token_groupings_too(self):
        # The rules line is an addition to the token line, not a replacement for it.
        self.assertIn("--by day|repo|model|role|stance|decision", help_text())


class UsageDocTests(unittest.TestCase):
    def setUp(self):
        self.text = USAGE_DOC.read_text()

    def test_the_rules_report_has_a_top_level_section_before_the_record_format(self):
        self.assertIn("\n## Which rules fired\n", self.text)
        self.assertLess(self.text.index("## Which rules fired"),
                        self.text.index("## What is recorded"))

    def test_the_section_documents_both_promotion_thresholds(self):
        section = self.text.split("## Which rules fired", 1)[1].split("\n## ", 1)[0]
        self.assertIn("RULE_PROMOTE_SHARE", section)
        self.assertIn("RULE_MIN_SESSIONS", section)
        self.assertIn("0.30", section)
        self.assertIn("20", section)

    def test_the_documented_thresholds_are_the_ones_the_report_uses(self):
        source = (REPO / "bin" / "harness").read_text()
        self.assertIn("RULE_PROMOTE_SHARE = 0.30", source)
        self.assertIn("RULE_MIN_SESSIONS = 20", source)

    def test_the_standalone_path_is_documented_and_linked(self):
        self.assertIn("(standalone-measurement.md)", self.text)
        standalone = (REPO / "docs" / "standalone-measurement.md").read_text()
        self.assertIn("453", standalone)
        self.assertLess(len(standalone.splitlines()), 40)


if __name__ == "__main__":
    unittest.main()
