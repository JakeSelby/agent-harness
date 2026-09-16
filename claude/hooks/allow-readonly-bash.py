#!/usr/bin/env python3
"""PreToolUse hook: approve read-only Bash commands that Claude Code's built-in
read-only set misses, so plan mode and Manual mode stop prompting for them.

Why a hook and not allow rules: `git -C <dir> status`, `gh repo view`, `npm view`
and friends cannot be expressed as a prefix rule without a wildcard before the
subcommand, which Claude Code warns about and which would also match writes.

Behaviour:
  - Approves only when EVERY segment of a compound command is read-only under
    the grammar below. Anything else returns no decision and falls through to
    the normal permission flow. This hook never denies.
  - Output redirections to a file (`>`, `>>`) are never approved here.
  - Subshells, `bash -c`, `eval`, `xargs` with flags, `sudo`, `find -exec` and
    `find -delete` are never approved here.

Test: echo '{"tool_name":"Bash","tool_input":{"command":"git -C /x status"}}' | python3 allow-readonly-bash.py
"""
import json
import re
import shlex
import sys

# Commands that are read-only regardless of arguments. Claude Code still checks
# redirect targets on its own; we refuse file redirects below anyway.
PLAIN = {
    "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "find", "fd",
    "tree", "stat", "file", "du", "df", "pwd", "echo", "printf", "true", "false",
    "test", "[", "which", "type", "whoami", "id", "uname", "sw_vers", "date", "env",
    "printenv", "basename", "dirname", "realpath", "readlink", "sort", "uniq", "cut",
    "tr", "awk", "jq", "yq", "column", "nl", "od", "xxd", "strings", "md5", "md5sum",
    "shasum", "sha256sum", "diff", "cmp", "comm", "tac", "rev", "seq", "expr",
    "cd", "hostname", "arch", "nproc", "sysctl", "lsof", "ps", "top", "uptime",
}

# Commands read-only only when the arguments match the given regex
# (matched against the argument string after the program name).
PREFIXED = [
    ("sed", r"^-n(\s|$)"),
    ("gh", r"^(auth status|repo view|repo list|pr view|pr list|pr diff|pr checks|pr status|"
           r"issue view|issue list|run list|run view|release list|release view|label list|"
           r"search \S+|api (-X GET |--method GET )?\S+$|--version)"),
    ("npm", r"^(view|info|show|ls|list|outdated|why|explain|--version|-v)(\s|$)"),
    ("pnpm", r"^(ls|list|why|outdated|--version|-v)(\s|$)"),
    ("yarn", r"^(info|why|--version|-v)(\s|$)"),
    ("cargo", r"^(metadata|tree|--version|-V)(\s|$)"),
    ("uv", r"^(pip list|pip show|tree|--version|-V)(\s|$)"),
    ("python3", r"^--version$"),
    ("python", r"^--version$"),
    ("node", r"^--version$"),
    ("claude", r"^--version$"),
    ("rustc", r"^--version$"),
    ("go", r"^(version|env)(\s|$)"),
    ("export", r"^[A-Za-z_][A-Za-z0-9_]*=[^;`]*$"),
    ("brew", r"^(list|info|--version|--prefix)(\s|$)"),
    ("aws", r"^sts get-caller-identity(\s|$)"),
]

# git subcommands that are read-only with any arguments.
GIT_ANY = {
    "status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "check-ignore",
    "blame", "describe", "shortlog", "cat-file", "rev-list", "name-rev", "merge-base",
    "count-objects", "for-each-ref", "show-ref", "var", "diff-tree", "diff-index",
    "diff-files", "grep", "whatchanged", "version", "--version", "help",
}

GIT_ARGS_WRITE = re.compile(r"^--output")

FIND_FORBIDDEN = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"}
OPERATORS = {";", "&&", "||", "|", "|&", "&"}
NEVER = {"sudo", "eval", "exec", "bash", "sh", "zsh", "xargs", "source", "."}


def git_ok(args):
    """args: list of tokens after `git`. Strips -C <dir>, --no-pager, -P."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            i += 2
            continue
        if a in ("--no-pager", "-P"):
            i += 1
            continue
        if a.startswith("-"):
            return False  # -c key=val and unknown globals are not approved
        break
    rest = args[i:]
    if not rest:
        return False
    sub, sargs = rest[0], rest[1:]
    if any(GIT_ARGS_WRITE.match(s) for s in sargs):
        return False
    if sub in GIT_ANY:
        return True
    if sub == "branch":
        ro = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--list", "-l", "--show-current",
              "--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--verbose"}
        listing = any(s in ("--list", "-l") for s in sargs)
        for s in sargs:
            if s.startswith("--format=") or s.startswith("--sort="):
                continue
            if s in ro:
                continue
            if not s.startswith("-") and listing:
                continue
            return False
        return True
    if sub == "remote":
        return not sargs or sargs[0] in ("-v", "--verbose", "show", "get-url")
    if sub == "tag":
        return not sargs or sargs[0] in ("-l", "--list", "-n", "--contains", "--points-at")
    if sub == "stash":
        return bool(sargs) and sargs[0] in ("list", "show")
    if sub == "worktree":
        return bool(sargs) and sargs[0] == "list"
    if sub == "submodule":
        return bool(sargs) and sargs[0] == "status"
    if sub == "reflog":
        return not sargs or sargs[0] not in ("expire", "delete")
    if sub == "config":
        getters = {"--get", "--get-all", "--get-regexp", "--list", "-l"}
        writers = {"--unset", "--unset-all", "--add", "--replace-all", "--edit", "-e",
                   "--remove-section", "--rename-section"}
        if any(s in writers for s in sargs) or not any(s in getters for s in sargs):
            return False
        positional = [s for s in sargs if not s.startswith("-")]
        return len(positional) <= 1
    if sub == "symbolic-ref":
        return len([s for s in sargs if not s.startswith("-")]) <= 1
    return False


def segment_ok(tokens):
    # Refuse file redirections; allow fd-only forms and /dev/null.
    cleaned = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in (">", ">>", "<", "<<", "<<<", "2>", "&>", ">&", "<&"):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if t in (">", ">>", "2>", "&>") and target != "/dev/null":
                return False
            i += 2
            continue
        if re.match(r"^\d*>&\d+$", t) or t in ("2>&1", "1>&2"):
            i += 1
            continue
        if re.match(r"^\d*>>?$", t):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if target != "/dev/null":
                return False
            i += 2
            continue
        cleaned.append(t)
        i += 1
    tokens = cleaned
    if not tokens:
        return False
    # Strip leading safe env assignments (LANG=C, NO_COLOR=1, PATH=...).
    while tokens and re.match(r"^(LANG|LC_[A-Z]+|NO_COLOR|TERM|PATH|PAGER|GIT_PAGER|TZ|COLUMNS)=", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return False
    for t in tokens:
        if "$(" in t or "`" in t or "<(" in t or ">(" in t:
            return False
    prog = tokens[0].rsplit("/", 1)[-1] if tokens[0].startswith("/") else tokens[0]
    args = tokens[1:]
    if prog in NEVER:
        return False
    if prog in ("timeout", "time", "nice", "nohup", "stdbuf", "command", "noglob"):
        return segment_ok(args[1:] if prog == "timeout" and args else args)
    if prog == "find":
        return not any(a in FIND_FORBIDDEN for a in args)
    if prog in PLAIN:
        return True
    if prog == "git":
        return git_ok(args)
    for name, pattern in PREFIXED:
        if prog == name:
            return re.match(pattern, " ".join(args)) is not None
    if args == ["--version"]:
        return True
    return False


def command_ok(cmd):
    if len(cmd) > 10000:
        return False
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return False
    segments, cur = [], []
    for t in tokens:
        if t in OPERATORS:
            segments.append(cur)
            cur = []
        elif t in ("(", ")", "{", "}"):
            return False
        else:
            cur.append(t)
    segments.append(cur)
    if len(segments) > 1 and any(not s for s in segments):
        return False  # dangling or leading operator: Claude Code treats it as unparseable
    return bool(segments) and all(segment_ok(s) for s in segments)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("tool_name") != "Bash":
        return
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if command_ok(cmd):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "read-only command (allow-readonly-bash hook)",
            }
        }))


if __name__ == "__main__":
    main()
