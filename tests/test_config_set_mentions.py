# SPDX-License-Identifier: MIT
"""The `harness config set governance` check exempts the policy-file guard's one inert shape.

Issue and pull request text passed to gh's built-in create, comment, edit and review
subcommands, in a quoted `--body` or `--title` value or a quoted here-document fed to
`--body-file -`, may mention the command as data. A real invocation stays gated wherever it
sits: alone, after a separator or a pipe, in a subshell, or run by `eval`, a shell or an
interpreter.

Run: python3 -m unittest discover tests
"""
import unittest

from test_governance_binding import Home, grader

SET = "harness config set governance.provider none"

MENTIONS = [
    "gh issue create --title x --body '%s turns the guard off'" % SET,
    "gh issue create --title x --body-file - <<'EOF'\nRunning `%s` is gated.\nEOF" % SET,
    'gh pr comment 1 --body "citizen config set governance.provider local"',
    "gh pr create -t 'x' -b '%s'" % SET,
    "gh issue edit 3 --body='%s is gated'" % SET,
    'gh pr review 4 --comment --body "%s"' % SET,
]

GATED = [
    SET,
    "citizen config set governance.provider none",
    "true; " + SET,
    "true && " + SET,
    "false || " + SET,
    "echo y | " + SET,
    "(%s)" % SET,
    "eval '%s'" % SET,
    "sh -c '%s'" % SET,
    "bash -c '%s'" % SET,
    "python3 -c 'import os; os.system(\"%s\")'" % SET,
    # A gh text command does not shield a real invocation on the same line or after it.
    "gh issue create --title x --body y; " + SET,
    "gh issue create --title x --body y && " + SET,
    "gh issue create --title x --body y | " + SET,
    "gh issue create --title x --body-file - <<'EOF'\nx\nEOF\n" + SET,
    "gh issue create --body \"$(%s)\"" % SET,
    # Other commands that mention it are still gated.
    'git commit -m "%s"' % SET,
    "gh api repos/x --field body='%s'" % SET,
]


class ConfigSetMentions(Home):
    """Only gh issue and pull request text may mention `harness config set governance` ungated."""

    def setUp(self):
        super().setUp()
        self.configure("local")

    def test_regression_gh_text_mentioning_config_set_is_not_gated(self):
        for command in MENTIONS:
            _answer, reason = self.bash(command)
            self.assertNotIn("harness config set", reason, command)
            self.assertNotIn("level 1", reason, command)

    def test_a_real_invocation_is_gated(self):
        for command in GATED:
            answer, reason = self.bash(command)
            self.assertEqual(answer, "ask", command)
            self.assertIn("level 1", reason, command)


class GhConfigSetTextOnly(unittest.TestCase):
    """The exempt shape for the config-set check, and near misses of it."""

    def names(self, command):
        return grader.gh_text_only(command, grader._names_config_set)

    def test_the_exempt_shapes(self):
        for command in MENTIONS:
            self.assertTrue(self.names(command), command)

    def test_near_misses_are_not_exempt(self):
        for command in ("gh issue create --title x " + SET,
                        "gh issue create --label '%s'" % SET,
                        "gh issue create --title harness config set governance",
                        "gh issue list --search '%s'" % SET,
                        "gh issue create --body '%s' 2>&1" % SET,
                        "gh issue create --body-file - <<EOF\n%s\nEOF" % SET,
                        "GH_HOST=x gh issue create --body '%s'" % SET):
            self.assertFalse(self.names(command), command)

    def test_the_policy_path_default_is_unchanged(self):
        self.assertTrue(grader.gh_text_only("gh issue create --body '%s'" % SET))
        self.assertFalse(grader.gh_text_only(
            "gh issue create --title .agent-harness/governance.json"))


if __name__ == "__main__":
    unittest.main()
