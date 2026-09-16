#!/usr/bin/env python3
"""PreToolUse hook: approve read-only Bash commands that Claude Code's built-in
read-only set misses, so plan mode and Manual mode stop prompting for them.

Why a hook and not allow rules: `git -C <dir> status`, `gh repo view`, `npm view`
and friends cannot be expressed as a prefix rule without a wildcard before the
subcommand, which Claude Code warns about and which would also match writes.

Behaviour:
  - Approves only when EVERY command that would run is read-only under the grammar
    below. Compound commands are decomposed first: pipelines and `;`/`&&`/`||`
    sequences, `for`/`while`/`until`/`if` blocks, subshell `( ... )` and group
    `{ ...; }`, and command substitutions `$(...)` / backticks / `<(...)` are each
    verified, recursively, and the whole thing is approved only if every part is.
    Anything the grammar cannot prove read-only returns no decision and falls
    through to the normal permission flow. This hook never denies.
  - Output redirections to a file (`>`, `>>`) are never approved here; `/dev/null`
    and fd-only forms are.
  - Subshells that run a write, `bash -c`, `eval`, `xargs`, `sudo`, `find -exec`
    and `find -delete`, and a command built from a substitution's output are never
    approved here.

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
    "read", "fold", "paste", "join", "look", "hexdump", "base64", "cksum",
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
    ("export", r"^([A-Za-z_][A-Za-z0-9_]*(=\S*)?\s*)+$"),
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
NEVER = {"sudo", "eval", "exec", "bash", "sh", "zsh", "xargs", "source", "."}

# Metacharacters that separate commands wherever they appear.
ALWAYS_DELIM = {";", "&&", "||", "|", "|&", "&", "(", ")", ";;"}
# Reserved words are structural only in command position (see command_ok). As an
# argument, e.g. `grep -q done`, the same word is ordinary data.
#   WORD_DROP    separate commands but carry none to check.
#   WORD_COND    introduce a condition command whose remainder must be checked.
#   WORD_HEADER  introduce a loop/case header whose words are data, not commands.
WORD_DROP = {"do", "done", "then", "fi", "else", "esac", "{", "}"}
WORD_COND = {"while", "until", "if", "elif"}
WORD_HEADER = {"for", "select", "case"}

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PLACEHOLDER = "__ROSUB__"  # stands in for a verified substitution; never a real command


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
    """True when a single simple command (already free of substitutions and of the
    structural keywords) is read-only."""
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
    # Strip leading assignments (LANG=C, S=/path, NAME=value cmd ...). A segment
    # that is nothing but assignments runs no command, so it is read-only.
    while tokens and ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return True
    for t in tokens:
        if "$(" in t or "`" in t or "<(" in t or ">(" in t:
            return False  # an unextracted substitution: fail closed
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


def _match_paren(s, start):
    """s[start] == '('. Return the index of the matching ')', or None. Quote-aware."""
    depth = 0
    i = start
    n = len(s)
    sq = dq = False
    while i < n:
        c = s[i]
        if sq:
            if c == "'":
                sq = False
        elif dq:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                dq = False
        else:
            if c == "'":
                sq = True
            elif c == '"':
                dq = True
            elif c == "\\":
                i += 2
                continue
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def _strip_subs(cmd, depth):
    """Replace every command/process/arithmetic substitution in `cmd` with a
    placeholder, verifying each command substitution is itself read-only. Returns
    the rewritten string, or None if any substitution is not read-only or the text
    does not parse."""
    out = []
    i = 0
    n = len(cmd)
    sq = dq = False
    while i < n:
        c = cmd[i]
        if sq:
            out.append(c)
            if c == "'":
                sq = False
            i += 1
            continue
        if c == "'" and not dq:
            sq = True
            out.append(c)
            i += 1
            continue
        if c == '"':
            dq = not dq
            out.append(c)
            i += 1
            continue
        if c == "\\":
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if cmd[j] == "\\" else 1
            if j >= n:
                return None
            inner = cmd[i + 1:j].replace("\\`", "`").replace("\\$", "$")
            if not command_ok(inner, depth + 1):
                return None
            out.append(_PLACEHOLDER)
            i = j + 1
            continue
        if cmd.startswith("$(", i):
            end = _match_paren(cmd, i + 1)
            if end is None:
                return None
            inner = cmd[i + 2:end]
            if not inner.startswith("("):  # a plain '(' opener is arithmetic $(( )), no command
                if not command_ok(inner, depth + 1):
                    return None
            out.append(_PLACEHOLDER)
            i = end + 1
            continue
        if c in "<>" and not dq and cmd.startswith("(", i + 1):
            end = _match_paren(cmd, i + 1)
            if end is None:
                return None
            inner = cmd[i + 2:end]
            if not command_ok(inner, depth + 1):
                return None
            out.append(_PLACEHOLDER)
            i = end + 1
            continue
        out.append(c)
        i += 1
    if sq or dq:
        return None
    return "".join(out)


def _header_ok(tokens):
    """A `for NAME [in WORDS]` / `select NAME ...` header runs no command; its words
    are data. Accept the well-formed shapes; reject C-style `for (( ))` and `case`."""
    kw = tokens[0]
    if kw in ("for", "select"):
        if len(tokens) < 2 or not NAME_RE.match(tokens[1]):
            return False
        return len(tokens) == 2 or tokens[2] == "in"
    return False  # `case` headers are not decomposed here; fail closed


def command_ok(cmd, depth=0):
    if depth > 6 or len(cmd) > 10000:
        return False
    cmd = _strip_subs(cmd, depth)
    if cmd is None:
        return False
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return False
    segments = []
    cur = []
    for t in tokens:
        if t in ALWAYS_DELIM:
            if cur:
                segments.append(cur)
                cur = []
            continue
        if not cur:  # command position: reserved words are structural here only
            if t in WORD_DROP:
                continue
            if t in WORD_COND or t in WORD_HEADER:
                cur = [t]
                continue
        cur.append(t)
    if cur:
        segments.append(cur)
    if not segments:
        return False
    for seg in segments:
        head = seg[0]
        if head in WORD_HEADER:
            if not _header_ok(seg):
                return False
        elif head in WORD_COND:
            rest = seg[1:]
            if rest and rest[0] == "!":
                rest = rest[1:]
            if not rest or not segment_ok(rest):
                return False
        else:
            rest = seg[1:] if head == "!" else seg
            if not rest or not segment_ok(rest):
                return False
    return True


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
