# SPDX-License-Identifier: MIT
"""/build step 6 names what a finished bot review looks like. Run: python3 -m unittest discover tests"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "primitives" / "workflows" / "build.md"
PROJECTION = REPO / "claude" / "commands" / "build.md"


def step_six(path):
    body = path.read_text(encoding="utf-8")
    start = body.index("6. **Answer the review bot**")
    return " ".join(body[start:body.index("\n\n", start)].split())


class ReviewSignalTests(unittest.TestCase):
    def test_a_pass_is_the_completed_commit_status_not_a_new_review_object(self):
        """An empty review from a thread reply once passed for a clean second round."""
        for path in (SOURCE, PROJECTION):
            step = step_six(path)
            self.assertIn("status on the head commit completes", step, msg=path)
            self.assertIn("`success: Review completed`", step, msg=path)
            self.assertIn("`Review skipped` and the empty review a thread reply creates are not passes",
                          step, msg=path)

    def test_the_wait_covers_a_slow_pass(self):
        """A requested re-review took about 8.5 minutes, too close to a ten-minute wait."""
        for path in (SOURCE, PROJECTION):
            step = step_six(path)
            self.assertIn("Wait up to fifteen minutes", step, msg=path)
            self.assertNotIn("ten minutes", step, msg=path)


if __name__ == "__main__":
    unittest.main()
