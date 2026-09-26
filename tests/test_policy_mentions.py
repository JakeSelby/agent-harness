# SPDX-License-Identifier: MIT
"""The policy-file guard judges what a command writes, not what its text mentions.

A line made only of commands that run no code from their input, such as `gh`, `git` and `echo`,
may mention a policy path in a quoted argument or a here-document body as data. A redirect,
`tee`, `sed -i`, a `cp` or `mv` operand and an unresolved operand named `governance.json` or
`config.json` are still level-1 writes, and so is a policy path anywhere in a line that runs
code the walk cannot see into: a shell, an interpreter, a leading assignment or a substitution.

Run: python3 -m unittest discover tests
"""
import unittest

from test_governance_binding import Home, grader

MENTIONS = [
    "gh issue create --title x --body-file - <<'EOF'\n"
    "The guard reads .agent-harness/governance.json and ~/.config/agent-harness/config.json.\n"
    "EOF",
    "cat > notes.md <<EOF\nedit .agent-harness/governance.json by hand\nEOF",
    'echo "edit .agent-harness/governance.json by hand" > notes.md',
    'git commit -m "document .agent-harness/governance.json"',
    "gh pr comment 1 --body '~/.config/agent-harness/config.json selects the provider'",
    'cd sub && git commit -m "see .agent-harness/governance.json" | cat',
]

WRITES = [
    "echo {} > .agent-harness/governance.json",
    "cat > .agent-harness/governance.json <<'EOF'\n{}\nEOF",
    "tee ~/.config/agent-harness/config.json < x",
    "sed -i '' s/2/3/ .agent-harness/governance.json",
    "perl -i -pe s/2/3/ .agent-harness/governance.json",
    "cp /tmp/p.json ~/.config/agent-harness/config.json",
    "mv .agent-harness/governance.json /tmp/old.json",
    'mv /tmp/c.json "$D"/config.json',
    'cd "$T" && tee governance.json < x',
    "python3 -c 'open(\".agent-harness/governance.json\",\"w\")'",
    "node -e 'fs.writeFileSync(\"~/.config/agent-harness/config.json\", \"{}\")'",
    # An option that takes a separate value must not hide the code that follows it.
    "python3 -W ignore -c 'open(\".agent-harness/governance.json\",\"w\")'",
    "python3 -X dev -c 'open(\".agent-harness/governance.json\",\"w\")'",
    "node -r mod -e 'fs.writeFileSync(\".agent-harness/governance.json\", \"{}\")'",
    "python3 -m json.tool /tmp/p.json .agent-harness/governance.json",
    "python3 script.py -c .agent-harness/governance.json",
    # A leading assignment is part of the command it prefixes.
    "P=.agent-harness/governance.json python3 -c 'import os; open(os.environ[\"P\"],\"w\")'",
    # Code a shell or an interpreter reads from a pipe or a here-document.
    "printf 'echo hi > .agent-harness/governance.json\\n' | sh",
    "python3 - <<'EOF'\nopen('.agent-harness/governance.json', 'w').write('{}')\nEOF",
    "python3 - <<'EOF'\nprint('see ~/.config/agent-harness/governance.json')\nEOF",
    "bash <<'EOF'\necho {} > .agent-harness/governance.json\nEOF",
    "gh issue create --body \"$(python3 -c 'open(\\\".agent-harness/governance.json\\\",\\\"w\\\")')\"",
    'echo "x > .agent-harness/governance.json',
]


class PolicyMentions(Home):
    """A policy path the command only mentions is not a policy-file write."""

    def setUp(self):
        super().setUp()
        self.configure("local")

    def test_regression_a_mention_in_data_is_not_gated(self):
        for command in MENTIONS:
            _answer, reason = self.bash(command)
            self.assertNotIn("policy file", reason, command)
            self.assertNotIn("harness configuration", reason, command)
            self.assertNotIn("level 1", reason, command)

    def test_a_real_write_is_still_gated(self):
        for command in WRITES:
            answer, reason = self.bash(command)
            self.assertEqual(answer, "ask", command)
            self.assertIn("level 1", reason, command)


class DataOnly(unittest.TestCase):
    """Which lines may mention a policy path as data."""

    def test_a_line_of_data_commands_is_data_only(self):
        for command in ('gh issue create --body "x"', "git status && echo x > out | cat",
                        "cat > notes.md <<'EOF'\nx\nEOF"):
            self.assertTrue(grader.data_only(command), command)

    def test_a_line_that_may_run_unseen_code_is_not(self):
        for command in ("P=x gh issue list", "printf x | sh", "python3 - <<'EOF'\nx\nEOF",
                        "eval echo x", "xargs rm < list", "find . -exec rm {} +",
                        "source env.sh", ". env.sh", "env gh issue list", "/tmp/git status",
                        'echo "$(date)"', "cat <(ls)", "(sh x)", 'echo "unclosed'):
            self.assertFalse(grader.data_only(command), command)


if __name__ == "__main__":
    unittest.main()
