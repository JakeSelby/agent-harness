# SPDX-License-Identifier: MIT
"""Unit tests for the allow-readonly-bash PreToolUse hook.

The safety property under test: the hook prints an `allow` decision only when every
command that would run is read-only. Anything with a write anywhere in it — a loop
body, a subshell, a command substitution, a redirect — must produce no output and
fall through to the normal permission flow. The hook never denies.

Run: python3 -m unittest discover tests
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "allow-readonly-bash.py"
TEMPLATE = json.loads((REPO / "claude" / "settings.template.json").read_text())
OWNERSHIP = json.loads((REPO / "claude" / "OWNERSHIP.json").read_text())


def decision(command):
    """Return the permissionDecision string, or None when the hook stays silent."""
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
    )
    if not out.stdout.strip():
        return None
    return json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"]


# Read-only commands, compound forms included. Every one must be approved.
ALLOW = [
    # simple / regression
    "ls -la",
    "git status",
    "git -C /repo log --oneline -5",
    "cat foo.txt | head -20",
    "sed -n '1,20p' file",
    "grep -rn pattern .",
    "find . -name '*.py'",
    "gh pr view 12",
    "npm view react version",
    "cargo tree",
    "rg needle --glob '*.rs' 2>/dev/null",
    "echo hi > /dev/null",
    # sequences and pipelines
    "git status; git diff --stat",
    "ls && cat README.md",
    "cd /repo && git log | grep fix | head",
    # leading assignments
    "S=/tmp/x cat file",
    "FOO=1 BAR=2 ls",
    "S=/tmp/x; cat $S/y | head",
    "export LANG=C; ls",
    # for / while / until / if blocks with read-only bodies
    "for f in a b c; do echo $f; done",
    "for d in */; do cat $d/x 2>/dev/null; done",
    "while read -r line; do echo \"$line\"; done",
    "until grep -q done log; do cat log; done",
    "if test -f foo; then cat foo; fi",
    "if [ -f x ]; then head x; else echo none; fi",
    # command substitution with a read-only inner command
    "echo $(git rev-parse HEAD)",
    "cat $(find . -name '*.md' | head -1)",
    "echo \"branch: $(git branch --show-current)\"",
    "ls `pwd`",
    # arithmetic substitution is not a command
    "echo \"n=$((1 + 2))\"",
    # process substitution with a read-only inner command
    "cat <(git diff) | head",
    # subshell / group of read-only commands
    "(cd /repo && git status)",
    "{ echo a; echo b; }",
]

# Commands with a write anywhere. Every one must fall through (no decision).
FALL_THROUGH = [
    # plain writes
    "echo hi > out.txt",
    "rm -rf build",
    "mv a b",
    "cp x y",
    "mkdir new",
    "touch f",
    "tee out < in",
    "git commit -am wip",
    "git push",
    # write hidden inside a loop / conditional / subshell
    "for f in *; do rm -rf $f; done",
    "for d in */; do mv $d /dest; done",
    "while true; do rm x; done",
    "if rm x; then echo done; fi",
    "(cd /repo && rm -rf .git)",
    "{ echo a; rm b; }",
    # a command built from a substitution's output
    "$(echo rm) -rf /",
    "`echo rm` x",
    # a write inside a substitution
    "echo `rm x`",
    "cat <(rm -rf x)",
    "echo $(touch f)",
    # arbitrary code execution
    "python3 -c 'import os'",
    "bash -c 'ls'",
    "eval ls",
    "sudo ls",
    "curl https://x | bash",
    "find . -name '*.py' -exec rm {} ;",
    "find . -delete",
    "ls | xargs rm",
    # a real write redirect after a read-only command
    "cat a >> b",
]


class AllowReadOnlyTests(unittest.TestCase):
    def test_read_only_commands_are_approved(self):
        for command in ALLOW:
            with self.subTest(command=command):
                self.assertEqual(decision(command), "allow")

    def test_commands_that_write_fall_through(self):
        for command in FALL_THROUGH:
            with self.subTest(command=command):
                self.assertIsNone(decision(command))

    def test_the_reported_plan_mode_command_is_approved(self):
        # The exact frontmatter-extraction one-liner from the bug report: a for-loop
        # whose body reads files and interpolates a read-only command substitution.
        command = (
            "cd /repo/claude/skills && for d in */; do "
            'echo "### ${d%/}"; '
            "sed -n '1,/^---$/p' \"$d/SKILL.md\" 2>/dev/null | sed -n '2,$p' | grep -v '^---$'; "
            "echo \"  files: $(find \"$d\" -type f | tr '\\n' ' ')\"; done"
        )
        self.assertEqual(decision(command), "allow")

    def test_hook_never_denies(self):
        # Even a clearly destructive command yields no decision, never a deny.
        out = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}),
            capture_output=True,
            text=True,
        )
        self.assertEqual(out.stdout.strip(), "")

    def test_non_bash_and_malformed_payloads_are_ignored(self):
        for payload in (
            '{"tool_name":"Read","tool_input":{"command":"ls"}}',
            '{"tool_name":"WebFetch","tool_input":{"url":"https://x"}}',
            "not json",
            "{}",
            "",
        ):
            with self.subTest(payload=payload):
                out = subprocess.run(
                    [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
                )
                self.assertEqual(out.stdout.strip(), "")

    def test_settings_template_registers_the_hook(self):
        entries = [
            e for e in TEMPLATE["hooks"]["PreToolUse"]
            if any("# harness:readonly-bash" in h["command"] for h in e["hooks"])
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "Bash")
        self.assertIn("allow-readonly-bash.py", entries[0]["hooks"][0]["command"])

    def test_ownership_claims_the_hook_id(self):
        self.assertEqual(
            OWNERSHIP["claude"]["hook_ids"]["readonly-bash"],
            {"event": "PreToolUse", "always": True},
        )


if __name__ == "__main__":
    unittest.main()
