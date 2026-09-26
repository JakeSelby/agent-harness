# SPDX-License-Identifier: MIT
"""The policy-file guard exempts one inert shape of mention, and gates every other.

Issue and pull request text passed to gh's built-in create, comment, edit and review
subcommands, in a quoted `--body` or `--title` value or a quoted here-document fed to
`--body-file -`, may mention a policy path as data. Any other line that names one is a level-1
write, since almost any command may run code that writes a path it only names: a shell, an
interpreter, a git alias, a leading assignment, a substitution or an unquoted here-document.

Run: python3 -m unittest discover tests
"""
import unittest

from test_governance_binding import Home, grader

GH_BODY = ("gh issue create --title x --body-file - <<'EOF'\n"
           "The guard reads .agent-harness/governance.json and ~/.config/agent-harness/config.json.\n"
           "EOF")

MENTIONS = [
    GH_BODY,
    "gh pr comment 1 --body '~/.config/agent-harness/config.json selects the provider'",
    'gh pr create -t "edit .agent-harness/governance.json" -F - <<"EOF"\nsee above\nEOF',
    "gh issue edit 3 --body='.agent-harness/governance.json is read'",
]

GATED = [
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
    # A git alias runs a shell; a `<<sh` inside a quoted argument is not a here-document.
    "git -c alias.x='!printf x > .agent-harness/governance.json' x",
    "printf '<<sh\\necho hi > .agent-harness/governance.json\\nsh\\n' | sh",
    # An unquoted here-document expands a substitution in its body.
    "gh issue create --body-file - <<EOF\n$(echo {} > .agent-harness/governance.json)\nEOF",
    GH_BODY + "\nsh -c 'echo {} > .agent-harness/governance.json'",
    GH_BODY.replace("<<'EOF'\n", "<<'EOF'; sh\n", 1),
    # Commands other than gh's text subcommands stay gated when they mention a policy path.
    'git commit -m "document .agent-harness/governance.json"',
    'echo "edit .agent-harness/governance.json by hand" > notes.md',
]


class PolicyMentions(Home):
    """Only gh issue and pull request text may mention a policy path ungated."""

    def setUp(self):
        super().setUp()
        self.configure("local")

    def test_regression_gh_text_mentioning_a_policy_path_is_not_gated(self):
        for command in MENTIONS:
            _answer, reason = self.bash(command)
            self.assertNotIn("policy file", reason, command)
            self.assertNotIn("harness configuration", reason, command)
            self.assertNotIn("level 1", reason, command)

    def test_every_other_line_naming_a_policy_path_is_gated(self):
        for command in GATED:
            answer, reason = self.bash(command)
            self.assertEqual(answer, "ask", command)
            self.assertIn("level 1", reason, command)


class GhTextOnly(unittest.TestCase):
    """The one exempt shape, and near misses of it."""

    def test_the_exempt_shapes(self):
        for command in MENTIONS:
            self.assertTrue(grader.gh_text_only(command), command)

    def test_near_misses_are_not_exempt(self):
        path = ".agent-harness/governance.json"
        for command in ("gh issue list --search '%s'" % path,
                        "gh api repos/x --field body='%s'" % path,
                        "gh issue create --body %s" % path,
                        "gh issue create --label '%s'" % path,
                        "gh issue create --body='x'%s" % path,
                        "gh issue create --body-file - <<EOF\n%s\nEOF" % path,
                        "gh issue create <<'EOF'\n%s\nEOF" % path,
                        "gh issue create --body-file - <<'EOF'\n%s\n" % path,
                        "gh issue create --body-file - <<'EOF'x\n%s\nEOF" % path,
                        "gh issue create --body '%s' 2>&1" % path,
                        "gh issue create --body '%s' \\\n  --title x" % path,
                        "'gh' issue create --body '%s'" % path,
                        "GH_HOST=x gh issue create --body '%s'" % path):
            self.assertFalse(grader.gh_text_only(command), command)


if __name__ == "__main__":
    unittest.main()
