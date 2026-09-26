# SPDX-License-Identifier: MIT
"""The policy-file guard judges what a command writes, not what its text mentions.

A policy path inside a quoted argument or a here-document body is data, so a command that only
mentions one goes to the decision provider like any other. A redirect, `tee`, `sed -i`, a `cp`
or `mv` operand, an unresolved operand named `governance.json` or `config.json`, any
argument of an interpreter and a here-document a shell runs as its script are still level-1 writes.

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


class InterpreterArguments(unittest.TestCase):
    """A policy path in any argument of an interpreter is written, wherever it stands."""

    POLICY = "open('.agent-harness/governance.json','w')"

    def test_every_argument_of_an_interpreter_is_judged(self):
        for prog, args in (("python3.12", ["-W", "ignore", "-c", self.POLICY]),
                           ("perl", ["-I", "lib", "-ne", self.POLICY]),
                           ("ruby", ["-e" + self.POLICY]),
                           ("node", ["--require", "mod", "--eval=" + self.POLICY]),
                           ("php", ["-r", self.POLICY])):
            self.assertIn(".agent-harness/governance.json",
                          grader._written(prog, args, [], "/repo"), prog)

    def test_another_program_is_not_judged_by_its_arguments(self):
        self.assertEqual(grader._written("gh", ["-e", self.POLICY], [], "/repo"), [])
        self.assertEqual(grader._written("python3", ["-c", "print(1)"], [], "/repo"), [])


if __name__ == "__main__":
    unittest.main()
