"""Published README copy follows the no-em-dash rule, including the parts generated into it."""
import json
import re
import unittest

from test_harness import REPO
from harness_core import catalog, compatibility

EM_DASH = "—"


class ReadmeCopyTests(unittest.TestCase):
    def test_the_readme_carries_no_em_dash(self):
        for number, line in enumerate((REPO / "README.md").read_text().splitlines(), 1):
            with self.subTest(line=number):
                self.assertNotIn(EM_DASH, line)

    def test_the_generated_compatibility_block_carries_no_em_dash(self):
        for text in catalog.compatibility_capability_table(REPO, compatibility.catalog(REPO)):
            self.assertNotIn(EM_DASH, text)

    def test_the_readme_lists_exactly_the_planned_work_in_product_json(self):
        readme = (REPO / "README.md").read_text()
        section = readme.split("### On the way", 1)[1].split("\n## ", 1)[0]
        listed = []
        for bullet in re.findall(r"^- .*$", section, flags=re.M):
            entry = re.match(r"^- \*\*(.+?):\*\* (.+)$", bullet)
            self.assertIsNotNone(entry, "unexpected On the way bullet: " + bullet)
            listed.append(entry.groups())
        planned = json.loads((REPO / "product.json").read_text())["on_the_way"]
        self.assertEqual(listed, [(entry["title"], entry["line"]) for entry in planned])


if __name__ == "__main__":
    unittest.main()
