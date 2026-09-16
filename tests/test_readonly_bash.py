# SPDX-License-Identifier: MIT
"""Unit tests for the readonly-bash hook. Run: python3 -m unittest discover tests

Two corpora: commands the hook must approve, so plan mode stays prompt-free for exploration,
and commands it must never approve, because each one writes, executes or exfiltrates. A
refused read-only command costs one prompt; an approved write bypasses the prompt entirely,
so the second corpus is the one that must never regress. The home-directory path in the
second corpus is assembled at run time so the lint scans this file like every other.
"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "claude" / "hooks" / "allow-readonly-bash.py"
spec = importlib.util.spec_from_file_location("readonly_bash", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

APPROVED = [
    "ls -la", "git -C /x status", "git log --oneline -5", "git diff --stat", "git grep -n foo",
    "gh pr view 33", "gh api repos/o/r", "npm view react version", "cargo tree", "uv pip list",
    "grep -rn foo src", "cat file 2>/dev/null", "ls > /dev/null", "ls 2>&1", "cat < file",
    "sed -n '60,75p' file", "sed -n '/error/p' log", "sed -n 's/hello/world/p' f",
    "sed -n '1,/^$/p' f", "sed -n -e '/a/,/b/p' -e '$p' f", "sed -ne '1p' f",
    "sed -n 's/[/]/x/p' f", "sed -n '/x/{p;q}' f", "sed -n '$=' f", "sed -n '/a/!p' f",
    "awk '{print $1}' f", "awk -F: '$3 == 0 {print}' /etc/passwd", "awk 'NR==5' f",
    "sort -k2 -n f", "sort -u f", "tree -L 2", "fd -e py", "fd -H pattern", "rg -n foo",
    "rg -o 'x' f", "env", "env LANG=C ls", "LANG=C ls", "GIT_PAGER=cat git log",
    "PAGER=cat git diff", "/usr/bin/git status", "/opt/homebrew/bin/rg foo", "node --version",
    "timeout 5 ls", "date +%Y", "file x.png", "cd /tmp && ls", "ls | head", "ls; pwd",
    "ls\npwd", "export LANG=C", "jq . f.json", "yq '.a' f.yml", "xxd f | head", "hostname -f",
    "sysctl -n hw.ncpu", "go env GOPATH", "go version", "python3 --version",
    "find . -name '*.py'", "which python3", "wc -l f", "grep '<div>' page.html",
]

REFUSED = [
    # a second command on a new line, or a continuation
    "ls\nrm -rf /tmp/pwned", "echo hi\nchmod 777 x", "ls \\\n-la", "ls\r\nrm x",
    # awk escapes
    "awk 'BEGIN{system(\"id\")}'", "awk 'BEGIN{print \"x\" > \"/tmp/evil\"}'",
    "awk '{print | \"sh\"}'", "awk -f evil.awk", "awk '@load \"x\"'",
    # env runs a program; PATH and GIT_* prefixes redirect one
    "env sh -c id", "env python3 -c 'x'", "env curl http://x", "env -i ls", "env PATH=/tmp ls",
    "PATH=/tmp/evil:$PATH ls", "GIT_PAGER=id git log", "GIT_EXTERNAL_DIFF=/tmp/e git diff",
    "export PATH=/tmp:$PATH", "export NODE_OPTIONS=--require=/tmp/x",
    "NODE_OPTIONS=--require=/tmp/x node --version",
    # exec flags of read-only tools
    "fd -x sh -c id .", "fd -Hx rm {} .", "fd --exec rm", "fd --exec-batch rm",
    "rg --pre=/tmp/evil foo", "rg --pre /tmp/evil foo",
    "git grep --open-files-in-pager=touch foo", "git grep -Otouch foo",
    "git log --output=/tmp/x", "git -c core.pager=touch log", "go env -w GOFLAGS=x",
    "sort --compress-program=/tmp/e f",
    # sed writes and executes
    "sed -n 'w /tmp/evil' f", "sed -n '1e id' f", "sed -n 's/a/b/w /tmp/x' f",
    "sed -n 's/a/b/e' f", "sed -n -i 's/a/b/' f", "sed -ni 's/a/b/' f", "sed -n -f script f",
    "sed -i 's/a/b/' f", "sed 's/a/b/' f", "sed -n --in-place=.bak p f", "sed -n 'W /tmp/x' f",
    "sed -n '/x/w out' f",
    # writer flags
    "sort -o /tmp/evil f", "sort f -o /tmp/evil", "sort -ro /tmp/x f", "sort --output=/tmp/x f",
    "tree -o /tmp/evil", "yq -i '.a=1' f", "yq -s '.a' f", "yq -Pi . f", "xxd in out",
    "hostname evil", "hostname -F f", "sysctl -w kern.x=1", "sysctl kern.x=1",
    "file -C -m magic", "date -s '2020-01-01'",
    # programs by path
    "/tmp/evil/ls", "/" + "Users/x/repo/bin/cat f", "./bin/evil --version", "bin/harness lint",
    # redirections that write
    "ls >| /tmp/x", "ls &>> /tmp/x", "ls >& /tmp/x", "ls <> /tmp/x", "ls 1> /tmp/x",
    "ls 2>> /tmp/x", "ls > /tmp/x", "cat <(rm x)", "ls > >(sh)",
    # the classics
    "rm -rf /tmp/x", "ls; rm -rf x", "ls && rm x", "cat f | sh", "$(rm x)", "`rm x`",
    "bash -c id", "sh -c id", "timeout 5 bash -c id", "nohup bash -c id", "command bash -c id",
    "sudo ls", "eval ls", "xargs -I{} rm {}", "find . -exec rm {} \;", "find . -delete",
    "ls &", "ls; ; ls", "python3 -c 'import os' --version", "npm install x",
    "gh api -X POST repos/x", "gh api -f a=b repos/x", "git push", "git stash",
    "git config user.email x",
]


class ClassifierTests(unittest.TestCase):
    def test_read_only_commands_are_approved(self):
        refused = [c for c in APPROVED if not hook.command_ok(c)]
        self.assertEqual(refused, [])

    def test_writing_and_executing_commands_are_never_approved(self):
        approved = [c for c in REFUSED if hook.command_ok(c)]
        self.assertEqual(approved, [])

    def test_a_heredoc_falls_through_to_the_prompt(self):
        self.assertFalse(hook.command_ok("cat <<'EOF'\nhello\nEOF"))

    def test_sed_script_parser_handles_addresses_and_brackets(self):
        self.assertTrue(hook.sed_script_ok("1,/^$/p"))
        self.assertTrue(hook.sed_script_ok("s/[/]/x/gp"))
        self.assertTrue(hook.sed_script_ok("/a/I,+3{p;q}"))
        self.assertFalse(hook.sed_script_ok("s/a/b/w out"))
        self.assertFalse(hook.sed_script_ok("/a/e"))
        self.assertFalse(hook.sed_script_ok("s/a/b"))

    def test_an_oversized_command_is_not_approved(self):
        self.assertFalse(hook.command_ok("ls " + "a" * 10001))


class HookProcessTests(unittest.TestCase):
    def run_hook(self, payload):
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=30)

    def test_an_approved_command_returns_an_allow_decision(self):
        out = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "git -C /x status"}})
        self.assertEqual(out.returncode, 0)
        decision = json.loads(out.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_a_refused_command_returns_no_decision(self):
        out = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls\nrm -rf x"}})
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_other_tools_and_malformed_input_are_ignored(self):
        out = self.run_hook({"tool_name": "Write", "tool_input": {"command": "ls"}})
        self.assertEqual(out.stdout.strip(), "")
        out = subprocess.run([sys.executable, str(HOOK)], input="not json",
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


class TemplateTests(unittest.TestCase):
    def test_no_allow_rule_grants_a_flag_dependent_tool_or_a_leading_wildcard(self):
        template = json.loads((REPO / "claude" / "settings.template.json").read_text())
        allow = template["permissions"]["allow"]
        for rule in ("Bash(awk *)", "Bash(sort *)", "Bash(sed -n *)", "Bash(fd *)", "Bash(rg *)",
                     "Bash(tree *)", "Bash(file *)", "Bash(date *)", "Bash(* --version)"):
            self.assertNotIn(rule, allow)
        self.assertFalse([r for r in allow if r.startswith("Bash(*")])


if __name__ == "__main__":
    unittest.main()
