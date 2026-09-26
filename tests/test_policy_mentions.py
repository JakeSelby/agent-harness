# SPDX-License-Identifier: MIT
"""The policy-file guard judges what a command writes, not what its text mentions.

A policy path inside a quoted argument or a here-document body is data, so a command that only
mentions one goes to the decision provider like any other. A redirect, `tee`, `sed -i`, a `cp`
or `mv` operand, an unresolved operand named `governance.json` or `config.json`, inline
interpreter code and a here-document a shell runs as its script are still level-1 writes.

Run: python3 -m unittest discover tests
"""
import unittest

from test_governance_binding import Home, grader

MENTIONS = [
    "gh issue create --title x --body-file - <<'EOF'\n"
    "The guard reads .agent-harness/governance.json and ~/.config/agent-harness/config.json.\n"
    "EOF",
    "python3 - <<'EOF'\nprint('see ~/.config/agent-harness/governance.json')\nEOF",
    "cat > notes.md <<EOF\nedit .agent-harness/governance.json by hand\nEOF",
    'echo "edit .agent-harness/governance.json by hand" > notes.md',
    'git commit -m "document .agent-harness/governance.json"',
    "gh pr comment 1 --body '~/.config/agent-harness/config.json selects the provider'",
    "python3 script.py -c .agent-harness/governance.json",
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
    "bash <<'EOF'\necho {} > .agent-harness/governance.json\nEOF",
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


class InlineCode(unittest.TestCase):
    """Which arguments an interpreter runs as code."""

    def test_the_code_option_value_is_inline_code(self):
        self.assertEqual(grader._inline_code("python3", ["-c", "a", "-c", "b"]), ["a"])
        self.assertEqual(grader._inline_code("python3.12", ["-Bc", "a"]), ["a"])
        self.assertEqual(grader._inline_code("perl", ["-ne", "a"]), ["a"])
        self.assertEqual(grader._inline_code("ruby", ["-ea"]), ["a"])
        self.assertEqual(grader._inline_code("node", ["--eval=a", "-p", "b"]), ["a", "b"])
        self.assertEqual(grader._inline_code("php", ["-r", "a"]), ["a"])

    def test_a_script_its_arguments_and_stdin_are_not_inline_code(self):
        self.assertEqual(grader._inline_code("python3", ["script.py", "-c", "a"]), [])
        self.assertEqual(grader._inline_code("python3", ["-"]), [])
        self.assertEqual(grader._inline_code("gh", ["-e", "a"]), [])


if __name__ == "__main__":
    unittest.main()
