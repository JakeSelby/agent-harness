#!/usr/bin/env python3
"""PreToolUse hook: approve read-only Bash commands that Claude Code's built-in
read-only set misses, so plan mode and Manual mode stop prompting for them.

Why a hook and not allow rules: `git -C <dir> status`, `gh repo view`, `npm view`
and friends cannot be expressed as a prefix rule without a wildcard before the
subcommand, which Claude Code warns about and which would also match writes.

Behaviour:
  - Approves only when EVERY line and EVERY segment of a compound command is
    read-only under the grammar below. Anything else returns no decision and
    falls through to the normal permission flow. This hook never denies.
  - Output redirections to a file (`>`, `>>`, `>|`, `&>`, `>&`, `<>`) are never
    approved here; `/dev/null` and fd duplication (`2>&1`) are.
  - Subshells, `bash -c`, `eval`, `xargs` with flags, `sudo`, `find -exec` and
    `find -delete` are never approved here, nor are the write or exec flags of
    otherwise read-only tools (`sort -o`, `fd -x`, `rg --pre`, `sed w`, awk's
    `system()`), programs run by path outside the system bin directories, or
    environment prefixes other than locale, terminal and `PAGER=cat`.

Test: echo '{"tool_name":"Bash","tool_input":{"command":"git -C /x status"}}' | python3 allow-readonly-bash.py
"""
import json
import re
import shlex
import sys

# Commands that are read-only regardless of arguments. Claude Code still checks
# redirect targets on its own; we refuse file redirects below anyway.
PLAIN = {
    "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "find",
    "stat", "du", "df", "pwd", "echo", "printf", "true", "false",
    "test", "[", "which", "type", "whoami", "id", "uname", "sw_vers",
    "printenv", "basename", "dirname", "realpath", "readlink", "uniq", "cut",
    "tr", "jq", "column", "nl", "od", "strings", "md5", "md5sum",
    "shasum", "sha256sum", "diff", "cmp", "comm", "tac", "rev", "seq", "expr",
    "cd", "arch", "nproc", "lsof", "ps", "top", "uptime",
}

# Read-only unless one of these flags appears: a long option matched by prefix, or a
# letter anywhere in a short-option cluster, so `-Hx` is caught the same as `-x`.
FLAGGED = {
    "sort": (("--output", "--compress-program"), "o"),
    "tree": ((), "o"),
    "yq": (("--inplace", "--split-exp"), "is"),
    "fd": (("--exec", "--exec-batch"), "xX"),
    "rg": (("--pre",), ""),
    "file": (("--compile",), "C"),
    "date": (("--set",), "s"),
    "sysctl": (("--write",), "w"),
    "hostname": (("--file",), "F"),
    "xxd": ((), ""),
}
# Operands beyond this count name an output file (`xxd in out`) or set state (`hostname x`).
POSITIONAL_MAX = {"xxd": 1, "hostname": 0}

# Commands read-only only when the arguments match the given regex
# (matched against the argument string after the program name).
PREFIXED = [
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
    ("brew", r"^(list|info|--version|--prefix)(\s|$)"),
    ("aws", r"^sts get-caller-identity(\s|$)"),
]

# Environment assignments that cannot change what an approved program does. PATH,
# GIT_*, LD_*, NODE_OPTIONS and the like are not here: they redirect an approved
# program to code of the caller's choosing.
SAFE_ENV = re.compile(
    r"^(LANG|LC_[A-Z]+|NO_COLOR|CLICOLOR|TERM|TZ|COLUMNS|LINES)=[^;`$()|&<>]*$"
    r"|^(PAGER|GIT_PAGER)=(cat)?$"
)

# A program named by absolute path is approved only from these directories; a
# repository can ship a `bin/cat` of its own.
SAFE_BIN_DIRS = {"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/sbin", "/usr/sbin"}

# git subcommands that are read-only with any arguments.
GIT_ANY = {
    "status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "check-ignore",
    "blame", "describe", "shortlog", "cat-file", "rev-list", "name-rev", "merge-base",
    "count-objects", "for-each-ref", "show-ref", "var", "diff-tree", "diff-index",
    "diff-files", "grep", "whatchanged", "version", "--version", "help",
}

GIT_ARGS_WRITE = re.compile(r"^(--output|--open-files-in-pager|-O)")

# awk: shell escapes, file output, script files and extension loading.
AWK_FORBIDDEN = re.compile(r"system\s*\(|getline|[|>]|@load|@include|^-[filE]|^--(file|include|load|exec)")

FIND_FORBIDDEN = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"}
OPERATORS = {";", "&&", "||", "|", "|&", "&"}
NEVER = {"sudo", "eval", "exec", "bash", "sh", "zsh", "xargs", "source", "."}

# Redirection tokens that are safe on their own: fd duplication and input redirects
# (the operand of an input redirect is read, never written).
READ_REDIRECTS = {"<", "<<", "<<<", "<&"}
WRITE_REDIRECTS = re.compile(r"^\d*(>|>>|&>|>&)$")
PUNCTUATION_RUN = re.compile(r"^\d*[<>&|]+$")


def flags_hit(args, longs, shorts):
    for a in args:
        if a == "--":
            break
        if a.startswith("--"):
            if any(a.startswith(l) for l in longs):
                return True
        elif a.startswith("-") and len(a) > 1:
            if any(ch in shorts for ch in a[1:]):
                return True
    return False


def positionals(args):
    out, opts_done = [], False
    for a in args:
        if a == "--":
            opts_done = True
        elif opts_done or not a.startswith("-"):
            out.append(a)
    return out


def _skip_delimited(s, i, delim):
    """Index just past the next unescaped `delim` from s[i], honouring bracket
    expressions; None when the section never closes."""
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and s[j] == "^":
                j += 1
            if j < n and s[j] == "]":
                j += 1
            while j < n and s[j] != "]":
                j += 1
            if j >= n:
                return None
            i = j + 1
            continue
        if c == delim:
            return i + 1
        i += 1
    return None


def sed_script_ok(s):
    """True when a sed script only prints, edits the pattern space, branches or
    quits — never `w`, `W`, `e` or the `w`/`e` flags of `s`."""
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c in " \t\n;":
            i += 1
            continue
        if c == "#":
            while i < n and s[i] != "\n":
                i += 1
            continue
        # Addresses: N, $, /re/, \cREc, optional ~step, I/M flags, a comma and a second one.
        while i < n:
            c = s[i]
            if c.isdigit() or c in "$+~":
                while i < n and (s[i].isdigit() or s[i] in "$~+"):
                    i += 1
            elif c == "/":
                i = _skip_delimited(s, i + 1, "/")
            elif c == "\\" and i + 1 < n:
                i = _skip_delimited(s, i + 2, s[i + 1])
            else:
                break
            if i is None:
                return False
            while i < n and s[i] in "IM":
                i += 1
            while i < n and s[i] in " \t":
                i += 1
            if i < n and s[i] == ",":
                i += 1
                while i < n and s[i] in " \t":
                    i += 1
                continue
            break
        while i < n and s[i] in " \t!":
            i += 1
        if i >= n:
            return True
        cmd = s[i]
        i += 1
        if cmd in "wWe":
            return False
        if cmd in "{}pPnNdDhHgGxz=F":
            continue
        if cmd in ":btT" or cmd in "rR" or cmd in "aic":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if cmd in "qQlLv":
            while i < n and s[i].isdigit():
                i += 1
            continue
        if cmd in "sy":
            if i >= n:
                return False
            delim = s[i]
            i = _skip_delimited(s, i + 1, delim)
            if i is None:
                return False
            i = _skip_delimited(s, i, delim)
            if i is None:
                return False
            if cmd == "s":
                while i < n and s[i] in "gpImM0123456789":
                    i += 1
                if i < n and s[i] not in " \t\n;}":
                    return False  # `e`, `w file`, or a flag this parser does not know
            continue
        return False
    return True


def sed_ok(args):
    """`sed -n` with inline scripts that never write or execute: no -i, no -f, no w/e."""
    scripts, files, i, saw_n = [], [], 0, False
    while i < len(args):
        a = args[i]
        if a == "--":
            files.extend(args[i + 1:])
            break
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if name in ("--quiet", "--silent"):
                saw_n = True
            elif name == "--expression":
                if eq:
                    scripts.append(value)
                elif i + 1 < len(args):
                    scripts.append(args[i + 1])
                    i += 1
                else:
                    return False
            elif name in ("--regexp-extended", "--separate", "--unbuffered", "--null-data",
                          "--posix", "--debug", "--sandbox", "--line-length"):
                if name == "--line-length" and not eq:
                    i += 1
            else:
                return False
        elif a.startswith("-") and len(a) > 1:
            letters = a[1:]
            for k, ch in enumerate(letters):
                if ch == "n":
                    saw_n = True
                elif ch in "Ersuz":
                    pass
                elif ch == "e":
                    rest = letters[k + 1:]
                    if rest:
                        scripts.append(rest)
                    elif i + 1 < len(args):
                        scripts.append(args[i + 1])
                        i += 1
                    else:
                        return False
                    break
                elif ch == "l":
                    if not letters[k + 1:]:
                        i += 1
                    break
                else:
                    return False  # -i, -f, and anything unknown
        else:
            (files if scripts else scripts).append(a)
        i += 1
    return saw_n and bool(scripts) and all(sed_script_ok(s) for s in scripts)


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


def strip_redirects(tokens):
    """Tokens with safe redirections removed; None when any redirection writes a file."""
    cleaned = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if not PUNCTUATION_RUN.match(t):
            cleaned.append(t)
            i += 1
            continue
        target = tokens[i + 1] if i + 1 < len(tokens) else ""
        if t in READ_REDIRECTS:
            i += 2
        elif re.match(r"^\d*>&$", t) and re.match(r"^\d+$", target):
            i += 2  # 2>&1
        elif WRITE_REDIRECTS.match(t) and target == "/dev/null":
            i += 2
        else:
            return None  # a file is written, or an operator this hook does not model
    return cleaned


def segment_ok(tokens):
    tokens = strip_redirects(tokens)
    if not tokens:
        return False
    # Strip leading env assignments that cannot redirect an approved program.
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        if not SAFE_ENV.match(tokens[0]):
            return False
        tokens = tokens[1:]
    if not tokens:
        return False
    for t in tokens:
        if "$(" in t or "`" in t or "<(" in t or ">(" in t:
            return False
    head = tokens[0]
    if "/" in head:
        base, _, prog = head.rpartition("/")
        if base not in SAFE_BIN_DIRS:
            return False  # a relative path, or a binary outside the system directories
    else:
        prog = head
    args = tokens[1:]
    if prog in NEVER:
        return False
    if prog in ("timeout", "time", "nice", "nohup", "stdbuf", "command", "noglob"):
        return segment_ok(args[1:] if prog == "timeout" and args else args)
    if prog == "env":
        while args and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", args[0]):
            if not SAFE_ENV.match(args[0]):
                return False
            args = args[1:]
        if not args:
            return True
        return not args[0].startswith("-") and segment_ok(args)
    if prog == "export":
        return len(args) == 1 and SAFE_ENV.match(args[0]) is not None
    if prog == "find":
        return not any(a in FIND_FORBIDDEN for a in args)
    if prog in PLAIN:
        return True
    if prog in FLAGGED:
        longs, shorts = FLAGGED[prog]
        if flags_hit(args, longs, shorts):
            return False
        if prog in POSITIONAL_MAX and len(positionals(args)) > POSITIONAL_MAX[prog]:
            return False
        if prog == "sysctl" and any("=" in a for a in args):
            return False
        return True
    if prog == "awk":
        return not any(AWK_FORBIDDEN.search(a) for a in args)
    if prog == "sed":
        return sed_ok(args)
    if prog == "git":
        return git_ok(args)
    if prog == "go":
        return bool(args) and (args[0] == "version" or (args[0] == "env" and not flags_hit(args[1:], (), "wu")))
    for name, pattern in PREFIXED:
        if prog == name:
            return re.match(pattern, " ".join(args)) is not None
    if args == ["--version"] and "/" not in head:
        return True
    return False


def line_ok(cmd):
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


def command_ok(cmd):
    if len(cmd) > 10000:
        return False
    # A newline is a command separator to bash but whitespace to shlex, so every
    # line is judged on its own; a continuation or a quoted newline falls through.
    lines = [ln for ln in cmd.replace("\r", "\n").split("\n") if ln.strip()]
    if not lines:
        return False
    if any(ln.rstrip().endswith("\\") for ln in lines):
        return False
    return all(line_ok(ln) for ln in lines)


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
