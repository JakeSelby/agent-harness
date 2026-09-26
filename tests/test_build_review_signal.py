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
            self.assertIn("not on a thread reply's empty review", step, msg=path)

    def test_a_skipped_or_missing_first_review_is_requested_before_the_wait(self):
        """Drafts and release titles skip automatic review; waiting alone never gets a pass."""
        for path in (SOURCE, PROJECTION):
            step = step_six(path)
            request = step.index("If it reads skipped or no review starts, request one with the "
                                 "bot's command, such as `@coderabbitai review`.")
            self.assertLess(request, step.index("Wait up to fifteen minutes"), msg=path)

    def test_the_request_is_the_bots_own_command_not_only_coderabbits(self):
        """A repository selected by `greptile.json` has no use for a CodeRabbit mention."""
        for path in (SOURCE, PROJECTION):
            self.assertIn("with the bot's command, such as `@coderabbitai review`", step_six(path),
                          msg=path)

    def test_the_threads_to_resolve_come_from_review_threads(self):
        """`resolveReviewThread` needs a thread ID, which the `reviewThreads` listing supplies."""
        for path in (SOURCE, PROJECTION):
            step = step_six(path)
            listing = step.index("Each unresolved bot thread in GraphQL `reviewThreads`")
            self.assertLess(listing, step.index("`resolveReviewThread`"), msg=path)

    def test_the_wait_covers_a_slow_pass(self):
        """A requested re-review took about 8.5 minutes, too close to a ten-minute wait."""
        for path in (SOURCE, PROJECTION):
            step = step_six(path)
            self.assertIn("Wait up to fifteen minutes", step, msg=path)
            self.assertNotIn("ten minutes", step, msg=path)


if __name__ == "__main__":
    unittest.main()
