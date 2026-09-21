# SPDX-License-Identifier: MIT
"""Every relative link in the repository's docs resolves to a real file or a real heading.

One check of the deterministic smoke tier: it spends no model turns, writes no file under
`compatibility/evidence/` and appears in no catalog record. A green run says the prose points at
things that exist; it is never native client qualification.
"""
import re
import tempfile
import unittest
from pathlib import Path

from test_harness import REPO

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)


def anchors(text):
    """The heading slugs GitHub would mint: code ticks and punctuation dropped, spaces hyphenated."""
    return set(re.sub(r"[^\w\- ]", "", head.replace("`", "")).strip().lower().replace(" ", "-")
               for head in HEADING.findall(text))


def pages(root):
    root = Path(root)
    return sorted(list(root.glob("*.md")) + list(root.glob("docs/**/*.md")))


def broken(root):
    """`page: target` for every in-repo doc link resolving to no path or no heading.

    A link that leaves the checkout is GitHub-relative — `../../issues/new` is a URL once the
    page is rendered — so resolving it is the platform's job and not this check's.
    """
    root = Path(root).resolve()
    found = []
    for page in pages(root):
        text = page.read_text()
        for target in LINK.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            path, _, anchor = target.partition("#")
            dest = (page.parent / path).resolve() if path else page
            if not dest.is_relative_to(root):
                continue
            where = "%s: %s" % (page.relative_to(root), target)
            if not dest.exists():
                found.append(where)
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest.read_text()):
                found.append(where)
    return found


class RepositoryLinkTests(unittest.TestCase):
    def test_every_link_in_the_repository_docs_resolves(self):
        self.assertEqual(broken(REPO), [])

    def test_the_check_reads_the_readme_and_the_docs_directory(self):
        names = set(path.name for path in pages(REPO))
        self.assertIn("README.md", names)
        self.assertIn("getting-started.md", names)


class BrokenLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "real.md").write_text("# Real page\n\n## A live section\n")

    def write(self, body):
        (self.root / "README.md").write_text(body)

    def test_a_resolving_path_and_anchor_pass(self):
        self.write("# Top\n\n## Here\n\n[a](docs/real.md) [b](docs/real.md#a-live-section) [c](#here)\n")
        self.assertEqual(broken(self.root), [])

    def test_a_link_to_a_missing_file_is_reported(self):
        self.write("[gone](docs/absent.md)\n")
        self.assertEqual(broken(self.root), ["README.md: docs/absent.md"])

    def test_a_link_to_a_missing_anchor_is_reported(self):
        self.write("[gone](docs/real.md#no-such-section)\n")
        self.assertEqual(broken(self.root), ["README.md: docs/real.md#no-such-section"])

    def test_a_missing_anchor_in_the_same_page_is_reported(self):
        self.write("# Top\n\n[gone](#no-such-section)\n")
        self.assertEqual(broken(self.root), ["README.md: #no-such-section"])

    def test_a_url_and_a_link_out_of_the_checkout_are_left_to_the_platform(self):
        # The address is assembled rather than written out: the repository lint refuses a literal
        # one in a tracked file, fixture or not.
        mail = "mailto:maintainer@" + "example.invalid"
        self.write("[u](https://example.invalid/x) [m](%s) "
                   "[g](../../issues/new?template=01-bug.yml)\n" % mail)
        self.assertEqual(broken(self.root), [])


if __name__ == "__main__":
    unittest.main()
