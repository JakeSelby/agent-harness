#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PreToolUse hook: grade every Bash command 0-3 and gate the grades the autonomy stance forbids.

Why a hook and not a rule: "never force-push without asking" is a sentence the model can read
and still skip, and the native permission prompt cannot tell `git push` from `git push --force`
or `terraform plan` from `terraform apply`. A hook sees the command before it runs, in every
permission mode, and can put the consequence in front of the user in one line.

Behaviour:
  - Grades the maximum over the simple commands the read-only grammar decomposes the command
    into: 0 read-only (`allow-readonly-bash.command_ok` proves it), 1 local write, 2
    remote-mutating, 3 irreversible. An unknown command grades 1, never 3: a false low grade is
    the missed prompt native gives today, and the corpus grows from each miss.
  - The text is normalised before anything else — backslash continuations joined, quoted heredoc
    bodies and comments dropped — so a `#` comment or a here-document cannot hide the verb or
    break the parse with an unbalanced quote or backtick. When the text still does not parse, the
    raw text is scanned for grade-3 verb families rather than graded 1: an unparseable command
    that says `--force` or `rm -rf` is irreversible whatever the rest of it is.
  - `bash -c`, `sh -c`, `eval`, `xargs`, `find -exec` and command-substitution bodies grade 3 when
    their inner text carries a grade-3 verb, else 1; the read-only hook refuses them all anyway.
  - The autonomy stance sets the threshold: `execute` gates grade 3, `confirm-writes` grade 2 and
    up, `ask` grade 1 and up. Below the threshold the hook prints nothing.
  - At or above it, prompting modes get `ask` and the non-prompting modes get `deny` with the
    confirm marker in the reason, because per the Claude Code hooks reference, in
    `bypassPermissions` and in `auto` mode 'The "ask" decision is ignored', while 'A hook that
    returns `permissionDecision: "deny"` blocks the tool even in `bypassPermissions` mode or
    with `--dangerously-skip-permissions`'. A command prefixed `HARNESS_CONFIRMED=1` is the
    confirmation channel: the marker is stripped and the command passes silently at any grade.
    The marker is leading and confirms the whole command line, compounds included, because that
    is the text the user was shown and said yes to; a marker in the middle confirms nothing.
  - Never raises and never blocks on a bug: a missing sibling grammar, a malformed config and any
    other error are all a silent exit 0, so a fault here can only cost a prompt that native would
    not have shown either.

Test: echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | python3 grade-bash.py
"""
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

CONFIG = Path.home() / ".config" / "agent-harness" / "config.json"
HOOK = "grade-bash hook"
MARKER = "HARNESS_CONFIRMED=1"
DEFAULT_STANCE = "execute"
THRESHOLDS = {"execute": 3, "confirm-writes": 2, "ask": 1}
DENY_MODES = {"auto", "bypassPermissions"}
DENY_TAIL = (" No prompt exists in this mode: ask the user in chat, and on a yes re-run the same "
             "command prefixed with " + MARKER + ".")
LABELS = {1: "local write", 2: "remote-mutating", 3: "irreversible"}
PLACEHOLDER = "__GRADESUB__"
MAX_DEPTH = 4

try:  # a missing or broken sibling grammar leaves the hook silent, never crashing the tool call
    _spec = importlib.util.spec_from_file_location(
        "grade_bash_readonly", Path(__file__).resolve().with_name("allow-readonly-bash.py"))
    ro = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(ro)
except Exception:
    ro = None

# One consequence clause per verb family, plus a generic fallback per grade. The clause is the
# whole preview: the reason line is verb, target, clause.
CLAUSES = {
    "git-history": "rewrites remote history",
    "git-discard": "discards local work with no undo",
    "merge": "merges into the shared branch",
    "delete": "deletes data that cannot be restored",
    "archive": "locks the repository read-only for everyone",
    "database": "drops data that cannot be restored",
    "migration": "changes a database schema in place",
    "infra": "changes live infrastructure",
    "deploy": "ships to a live environment",
    "cluster": "changes a live cluster",
    "publish": "publishes a release that cannot be withdrawn",
    "system": "changes this machine outside the project",
    "opaque": "runs text this hook cannot inspect",
    "remote": "changes shared state",
    "remote-delete": "deletes a remote resource",
}
GENERIC = {1: "writes to the working tree", 2: "changes shared state", 3: "cannot be undone"}

MARKER_RE = re.compile(r"^\s*(env\s+)?" + MARKER + r"\s*;?\s*")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
DASH_C_RE = re.compile(r"^-[A-Za-z]*c$")
# Wrappers that run the command in their remaining arguments, with the option letters that take
# a value of their own, so `nice -n 10 git push --force` is graded as the push.
WRAPPERS = {
    "timeout": ("-k", "--kill-after", "-s", "--signal"),
    "time": (),
    "nice": ("-n", "--adjustment"),
    "nohup": (),
    "stdbuf": ("-i", "-o", "-e", "--input", "--output", "--error"),
    "command": (),
    "exec": (),
    "noglob": (),
    "env": ("-u", "--unset", "--chdir", "-C"),
    "npx": ("--package", "-p"),
    "uvx": ("--from", "-p"),
}
# Runners that execute the rest of the line in a managed environment, like `npx`.
RUNNERS = {("bundle", "exec"), ("poetry", "run"), ("uv", "run"), ("pipx", "run"),
           ("pnpm", "dlx"), ("pnpm", "exec"), ("yarn", "dlx"), ("yarn", "exec"),
           ("npm", "exec"), ("rye", "run"), ("hatch", "run")}
SUDO = {"sudo": ("-u", "-g", "-U", "--user", "--group", "-p", "--prompt"),
        "doas": ("-u", "-C"),
        "su": ("-c", "-s", "--shell", "--command")}
SHELLS = {"bash", "sh", "zsh", "ksh", "dash"}
GIT_VALUE_GLOBALS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                     "--config-env")
XARGS_VALUE_FLAGS = ("-I", "-i", "-n", "-P", "-L", "-s", "-d", "-a", "-E", "-e", "--replace",
                     "--max-args", "--max-procs", "--max-lines", "--delimiter", "--arg-file")
TEMP_ROOTS = ["/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/"]
DOCKER_EXEC_VALUE_FLAGS = ("-e", "--env", "-u", "--user", "-w", "--workdir",
                           "--index", "--env-file")
SSH_VALUE_FLAGS = ("-p", "-i", "-l", "-o", "-F", "-L", "-R", "-D", "-b", "-c", "-E", "-J", "-W")
SCAN_CAP = 16384
SQL_RE = re.compile(
    r"\b(DROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW|ROLE|USER)|TRUNCATE(?:\s+TABLE)?|"
    r"DELETE\s+FROM)\s+(?:IF\s+EXISTS\s+)?([`\"\w.]+)", re.I)
ALTER_DROP_RE = re.compile(r"\bALTER\s+TABLE\s+([`\"\w.]+)[\s\S]{0,200}?\bDROP\b", re.I)
MONGO_RE = re.compile(r"\bdb(?:\.\w+)*\.(dropDatabase|drop|deleteMany|remove)\s*\(")
SQL_CLIENTS = {"psql", "mysql", "mariadb", "sqlite3", "mongosh", "mongo", "clickhouse-client"}
CLOUD = {"aws", "gcloud", "az", "doctl", "flyctl"}
CLOUD_G3 = {"delete", "terminate", "destroy", "purge", "remove"}
CLOUD_G2 = {"create", "put", "update", "start", "stop", "attach", "detach", "tag", "modify",
            "associate", "deploy", "set", "cp", "mv", "sync", "upload"}
HTTP_LONG_BODY = ("--data", "--form", "--upload-file", "--post-data", "--post-file",
                  "--body-data", "--body-file", "--json")
HTTP_BODY_LETTERS = "dFT"
HTTP_G2_METHODS = {"POST", "PUT", "PATCH"}
HTTP_G3_METHOD = "DELETE"
GH_G2_NOUNS = {"pr", "issue", "release", "repo"}
GH_G2_VERBS = {"create", "edit", "comment", "close", "reopen", "ready", "review", "merge"}
PUBLISH = {"npm": "publish", "pnpm": "publish", "yarn": "publish", "cargo": "publish",
           "twine": "upload", "gem": "push", "poetry": "publish"}

# Last resort when the text does not parse: a grade-3 verb family anywhere in it is a grade 3.
# Substring needles, not regexes: the text can be large, and every check here must stay linear.
# A chunk is one separator-free run, so the needles of an entry must co-occur in one command.
SCAN = [
    (("force-with-lease",), "git push --force-with-lease", "git-history"),
    (("push", "--force"), "git push --force", "git-history"),
    (("push", "--mirror"), "git push --mirror", "git-history"),
    (("push", "--delete"), "git push --delete", "git-history"),
    (("push", " -f"), "git push -f", "git-history"),
    (("reset", "--hard"), "git reset --hard", "git-discard"),
    (("clean", " -f"), "git clean -f", "git-discard"),
    (("clean", "--force"), "git clean -f", "git-discard"),
    (("filter-branch",), "git filter-branch", "git-history"),
    (("filter-repo",), "git filter-repo", "git-history"),
    (("rm ", "-rf"), "rm -rf", "delete"),
    (("rm ", "-fr"), "rm -rf", "delete"),
    (("rm ", "-r "), "rm -r", "delete"),
    (("rm ", "-f "), "rm -f", "delete"),
    (("drop table",), "DROP TABLE", "database"),
    (("drop database",), "DROP DATABASE", "database"),
    (("drop schema",), "DROP SCHEMA", "database"),
    (("truncate ",), "TRUNCATE", "database"),
    (("delete from",), "DELETE FROM", "database"),
    (("dropdatabase",), "db.dropDatabase()", "database"),
    (("flushall",), "redis-cli FLUSHALL", "database"),
    (("terraform", "destroy"), "terraform destroy", "infra"),
    (("terraform", "apply"), "terraform apply", "infra"),
    (("pulumi", "destroy"), "pulumi destroy", "infra"),
    (("kubectl", "delete"), "kubectl delete", "cluster"),
    (("sudo ",), "sudo", "system"),
    (("doas ",), "doas", "system"),
    (("mkfs",), "mkfs", "system"),
    (("shutdown",), "shutdown", "system"),
    (("reboot",), "reboot", "system"),
    (("dd if=",), "dd", "system"),
]
SCAN_SPLIT = re.compile(r"[\n;&|]+")


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def stance():
    """The autonomy variant, from the environment, then the config, then the default. Anything
    malformed in the config falls back rather than turning grading off."""
    value = os.environ.get("HARNESS_STANCE_AUTONOMY")
    if value:
        return value
    config = _load(CONFIG)
    if not isinstance(config, dict):
        return DEFAULT_STANCE
    stances = config.get("stances")
    if not isinstance(stances, dict):
        return DEFAULT_STANCE
    value = stances.get("autonomy")
    return value if isinstance(value, str) and value else DEFAULT_STANCE


def emit(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))


def strip_marker(cmd):
    """(command without a leading confirm marker, marker seen)."""
    stripped = MARKER_RE.sub("", cmd, count=1)
    return stripped, stripped != cmd


def _split_heredocs(text):
    """Text without the body of every here-document. A body is data: the shell expands a
    variable in an unquoted one but never runs its lines, and a quoted body is not even
    expanded. Bodies go before continuations are joined, so a body line ending in a backslash
    cannot swallow the delimiter."""
    lines = text.split("\n")
    out, bodies = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        match = HEREDOC_RE.search(line)
        i += 1
        if not match:
            continue
        delimiter, body = match.group(2), []
        while i < len(lines) and lines[i].strip() != delimiter:
            body.append(lines[i])
            i += 1
        if i < len(lines):
            out.append(lines[i])
            i += 1
        bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _strip_comments(text):
    """Text without its `#` comments, with quote state carried across newlines, so a `#` inside
    a multi-line quoted string stays and a comment outside one takes the rest of its line."""
    out = []
    sq = dq = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if sq:
            sq = c != "'"
        elif dq:
            if c == "\\":
                out.append(text[i:i + 2])
                i += 2
                continue
            dq = c != '"'
        elif c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        elif c == "'":
            sq = True
        elif c == '"':
            dq = True
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n;|&()"):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def normalize(cmd):
    """(shell text, here-document bodies). Bodies come out first, then continuations are
    joined, then comments are dropped, so nothing can hide a verb behind a `#`, inside a body,
    or behind a line continuation. A body is data to the shell; only a client that interprets
    it — a SQL client — is graded on its contents."""
    text = cmd.replace("\r\n", "\n").replace("\r", "\n")
    text, bodies = _split_heredocs(text)
    text = re.sub(r"\\\n", " ", text)
    return _strip_comments(text), bodies


def _scan(text):
    """The fallback for text this hook cannot decompose: a grade-3 verb family in any one of
    its separator-free chunks, or grade 1. Linear in the length of the text, and the text it
    reads is capped, because a hook that runs past its timeout fails open."""
    if len(text) > SCAN_CAP:
        return 3, "command too long to grade", "", "opaque"
    for chunk in SCAN_SPLIT.split(text.lower()):
        for needles, verb, family in SCAN:
            if all(needle in chunk for needle in needles):
                return 3, verb, "", family
    return 1, "", "", "opaque"


def _extract_subs(cmd):
    """(text with every substitution replaced by a placeholder, the inner texts). The text is
    None when a substitution never closes."""
    out, inners = [], []
    i, n = 0, len(cmd)
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
                return None, inners
            inners.append(cmd[i + 1:j])
            out.append(PLACEHOLDER)
            i = j + 1
            continue
        if cmd.startswith("$(", i):
            end = ro._match_paren(cmd, i + 1)
            if end is None:
                return None, inners
            inner = cmd[i + 2:end]
            if not inner.startswith("("):  # `$(( ))` is arithmetic, not a command
                inners.append(inner)
            out.append(PLACEHOLDER)
            i = end + 1
            continue
        if c in "<>" and not dq and cmd.startswith("(", i + 1):
            end = ro._match_paren(cmd, i + 1)
            if end is None:
                return None, inners
            inners.append(cmd[i + 2:end])
            out.append(PLACEHOLDER)
            i = end + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), inners


def segments(text):
    """The simple commands in `text`, by the read-only grammar's own decomposition: newlines as
    separators, reserved words structural only in command position. None when it does not
    tokenize."""
    text = " ; ".join(text.split("\n"))
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.commenters = ""
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return None
    out, cur, skipping = [], [], False
    for token in tokens:
        if token in ro.ALWAYS_DELIM:
            if cur:
                out.append(cur)
            cur, skipping = [], False
            continue
        if skipping:
            continue
        if not cur:
            if token in ro.WORD_DROP or token in ro.WORD_COND or token == "!":
                continue
            if token in ro.WORD_HEADER:  # `for x in *` names data, not commands
                skipping = True
                continue
        cur.append(token)
    if cur:
        out.append(cur)
    return out


def _redirects(tokens):
    """(tokens without redirections, the targets they write)."""
    clean, targets = [], []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ro.PUNCTUATION_RUN.match(token):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if ro.WRITE_REDIRECTS.match(token):
                targets.append(target)
            i += 2
            continue
        clean.append(token)
        i += 1
    return clean, targets


def operands(args):
    out, done = [], False
    for a in args:
        if a == "--" and not done:
            done = True
        elif done or not a.startswith("-"):
            out.append(a)
    return out


def has(args, *names):
    return any(a == n or a.startswith(n + "=") for a in args for n in names)


def short(args, letters):
    """True when a short-option cluster carries any of `letters`, so `-fu` reads like `-f`."""
    for a in args:
        if a.startswith("-") and not a.startswith("--") and any(c in letters for c in a[1:]):
            return True
    return False


def strip_options(args, value_flags):
    """Arguments past a wrapper's own options, with the value of each option that takes one."""
    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("-") or a == "-":
            break
        if a in value_flags:
            i += 2
            continue
        i += 1
    return args[i:]


def _joined(args, limit=2):
    return " ".join(operands(args)[:limit])


def _rm_flagged(tokens):
    """True when `tokens` is an `rm` carrying a recursive or force flag."""
    return bool(tokens) and tokens[0].rpartition("/")[2] == "rm" and (
        short(tokens[1:], "rRf") or has(tokens[1:], "--recursive", "--force"))


def _inner(text, cwd, depth):
    """A body this hook cannot model as a command: grade 3 when it carries a grade-3 verb."""
    grade, verb, target, family = grade_text(text, cwd, depth + 1)
    if grade == 3:
        return 3, verb, target, family
    return 1, None, None, None


def _inner_tokens(tokens, cwd, depth):
    if not tokens:
        return 1, None, None, None
    if depth >= MAX_DEPTH:
        return _scan(" ".join(tokens))
    grade, verb, target, family = grade_tokens(tokens, cwd, depth + 1)
    if grade == 3:
        return 3, verb, target, family
    return 1, None, None, None


def _git(args, cwd):
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_VALUE_GLOBALS and i + 1 < len(args):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    rest = args[i:]
    if not rest:
        return 1, "git", "", None
    sub, sargs = rest[0], rest[1:]
    ops = operands(sargs)
    dry_run = has(sargs, "--dry-run") or short(sargs, "n")
    if sub == "push":
        if dry_run:
            return 1, "git push --dry-run", " ".join(ops), None
        if has(sargs, "--force-with-lease"):
            return 3, "git push --force-with-lease", " ".join(ops), "git-history"
        if has(sargs, "--force") or has(sargs, "--mirror") or short(sargs, "f"):
            verb = "git push --force" if has(sargs, "--force") else (
                "git push --mirror" if has(sargs, "--mirror") else "git push -f")
            return 3, verb, " ".join(ops), "git-history"
        if has(sargs, "--delete") or short(sargs, "d") or any(o.startswith(":") for o in ops):
            return 3, "git push --delete", " ".join(ops), "git-history"
        if any(o.startswith("+") for o in ops):
            return 3, "git push", " ".join(ops), "git-history"
        return 2, "git push", " ".join(ops), "remote"
    if sub == "reset" and has(sargs, "--hard"):
        return 3, "git reset --hard", _joined(sargs, 1), "git-discard"
    if sub == "clean" and (has(sargs, "--force") or short(sargs, "f")) and not dry_run:
        return 3, "git clean -f", _joined(sargs, 1), "git-discard"
    if sub == "checkout":
        if "--" in sargs:
            return 3, "git checkout --", _joined(sargs, 1), "git-discard"
        if has(sargs, "--force") or short(sargs, "f"):
            return 3, "git checkout -f", _joined(sargs, 1), "git-discard"
        if ops[:1] in (["."], ["./"]):
            return 3, "git checkout", ops[0], "git-discard"
    if sub == "switch" and (has(sargs, "--discard-changes", "--force") or short(sargs, "f")):
        return 3, "git switch --discard-changes", _joined(sargs, 1), "git-discard"
    if sub == "restore" and not (has(sargs, "--staged") or short(sargs, "S")):
        return 3, "git restore", _joined(sargs, 1), "git-discard"
    if sub == "branch" and (has(sargs, "-D", "--delete") or short(sargs, "D")):
        return 3, "git branch -D", _joined(sargs, 1), "git-discard"
    if sub == "stash" and ops and ops[0] in ("drop", "clear"):
        return 3, "git stash " + ops[0], " ".join(ops[1:2]), "git-discard"
    if sub == "reflog" and ops and ops[0] in ("expire", "delete"):
        return 3, "git reflog " + ops[0], " ".join(ops[1:2]), "git-history"
    if sub in ("filter-branch", "filter-repo"):
        return 3, "git " + sub, _joined(sargs, 1), "git-history"
    return 1, "git " + sub, _joined(sargs, 1), None


def _gh(args):
    ops = operands(args)
    noun = ops[0] if ops else ""
    verb = ops[1] if len(ops) > 1 else ""
    if (noun, verb) in (("repo", "delete"), ("release", "delete"), ("gist", "delete")):
        return 3, "gh %s %s" % (noun, verb), " ".join(ops[2:3]), "delete"
    if (noun, verb) in (("repo", "archive"), ("repo", "rename")):
        return 3, "gh %s %s" % (noun, verb), " ".join(ops[2:3]), "archive"
    if (noun, verb) == ("pr", "merge"):
        return 2, "gh pr merge", " ".join(ops[2:3]), "merge"
    if noun == "api":
        method = ""
        for i, a in enumerate(args):
            if a in ("-X", "--method") and i + 1 < len(args):
                method = args[i + 1].upper()
            elif a.startswith("--method="):
                method = a.split("=", 1)[1].upper()
        path = " ".join([o for o in ops[1:] if o != method][:1])
        if method == HTTP_G3_METHOD:
            return 3, "gh api DELETE", path, "remote-delete"
        if method not in ("", "GET", "HEAD") or has(args, "-f", "-F", "--input", "--field",
                                                    "--raw-field"):
            return 2, "gh api " + (method or "POST"), path, "remote"
        return 1, "gh api", path, None
    if noun in GH_G2_NOUNS and verb in GH_G2_VERBS:
        return 2, "gh %s %s" % (noun, verb), " ".join(ops[2:3]), "remote"
    return 1, "gh " + noun, verb, None


def _http(prog, args):
    method, body = "", False
    for i, a in enumerate(args):
        if a in ("-X", "--request", "--method") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith(("--request=", "--method=")):
            method = a.split("=", 1)[1].upper()
        elif a.startswith("--"):
            if any(a.startswith(f) for f in HTTP_LONG_BODY):
                body = True
        elif a.startswith("-") and len(a) > 1:
            cluster = a[1:]
            if cluster.endswith("X") and i + 1 < len(args):
                method = args[i + 1].upper()
            elif "X" in cluster:
                method = cluster.split("X", 1)[1].upper()
            if any(c in HTTP_BODY_LETTERS for c in cluster):
                body = True
    ops = operands(args)
    if prog in ("http", "https", "httpie") and ops:
        verb = ops[0].upper()
        if verb == HTTP_G3_METHOD:
            return 3, "%s DELETE" % prog, " ".join(ops[1:2]), "remote-delete"
        if verb in HTTP_G2_METHODS:
            return 2, "%s %s" % (prog, verb), " ".join(ops[1:2]), "remote"
    url = " ".join([o for o in ops if o != method][:1])
    if method == HTTP_G3_METHOD:
        return 3, "%s DELETE" % prog, url, "remote-delete"
    if method in HTTP_G2_METHODS or body:
        return 2, "%s %s" % (prog, method or "with a request body"), url, "remote"
    return 1, prog, url, None


def _cloud(prog, args):
    ops = operands(args)
    for i, op in enumerate(ops):
        head = op.split("-")[0].lower()
        if op.lower() in CLOUD_G3 or head in CLOUD_G3:
            return 3, "%s %s" % (prog, " ".join(ops[:i + 1])), " ".join(ops[i + 1:i + 2]), "infra"
    if prog == "aws" and ops[:1] == ["s3"]:
        if len(ops) > 1 and ops[1] in ("rm", "rb"):
            return 3, "aws s3 " + ops[1], " ".join(ops[2:3]), "delete"
        if len(ops) > 1 and ops[1] == "sync" and has(args, "--delete"):
            return 3, "aws s3 sync --delete", " ".join(ops[2:4]), "delete"
    for i, op in enumerate(ops):
        head = op.split("-")[0].lower()
        if op.lower() in CLOUD_G2 or head in CLOUD_G2:
            return 2, "%s %s" % (prog, " ".join(ops[:i + 1])), " ".join(ops[i + 1:i + 2]), "remote"
    return 1, prog, " ".join(ops[:2]), None


def _sql(text):
    match = SQL_RE.search(text)
    if match:
        verb = re.sub(r"\s+", " ", match.group(1)).upper()
        return 3, verb, match.group(2).strip("`\""), "database"
    match = ALTER_DROP_RE.search(text)
    if match:
        return 3, "ALTER TABLE DROP", match.group(1).strip("`\""), "database"
    match = MONGO_RE.search(text)
    if match:
        return 3, "db.%s()" % match.group(1), "", "database"
    return None


def _expand(op):
    """The operand with `~`, `$HOME` and `$TMPDIR` expanded and `.`/`..` segments resolved, so
    `/tmp/../etc` is judged as `/etc` and `$HOME` as the home directory."""
    text = op.replace("${HOME}", "$HOME").replace("${TMPDIR}", "$TMPDIR")
    text = text.replace("$HOME", os.path.expanduser("~"))
    text = text.replace("$TMPDIR", (os.environ.get("TMPDIR") or "/tmp").rstrip("/"))
    if text.startswith("~"):
        text = os.path.expanduser(text)
    return os.path.normpath(text) if text else text


def _rm_risky(op, cwd):
    """True when deleting `op` recursively reaches outside the working tree, or takes the whole
    working tree, the repository metadata or a wildcard with it."""
    if "*" in op:
        return True
    path = _expand(op)
    if not path or path == "/":
        return True
    if path == ".git" or path.endswith("/.git"):
        return True
    if path.startswith("/"):
        temp_roots = list(TEMP_ROOTS)
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            temp_roots.append(tmpdir.rstrip("/") + "/")
        if any(path.startswith(root) for root in temp_roots):
            return False  # the system temp directories are outside cwd by design
        root = os.path.normpath(cwd) if cwd else ""
        return not (root and (path == root or path.startswith(root + "/")))
    return path == "." or path == ".." or path.startswith("../")


def _rm(args, cwd):
    if not (short(args, "rRf") or has(args, "--recursive", "--force")):
        return 1, "rm", _joined(args, 1), None
    verb = "rm -rf" if short(args, "rR") or has(args, "--recursive") else "rm -f"
    for op in operands(args):
        if _rm_risky(op, cwd):
            return 3, verb, op, "delete"
    return 1, verb, _joined(args, 1), None


G3_SUBCOMMANDS = {
    "terraform": ({"apply", "destroy"}, "infra"),
    "tofu": ({"apply", "destroy"}, "infra"),
    "pulumi": ({"up", "destroy"}, "infra"),
    "cdk": ({"deploy", "destroy"}, "infra"),
    "sam": ({"deploy"}, "deploy"),
    "serverless": ({"deploy", "remove"}, "deploy"),
    "sls": ({"deploy", "remove"}, "deploy"),
    "fly": ({"deploy"}, "deploy"),
    "railway": ({"up"}, "deploy"),
    "alembic": ({"upgrade", "downgrade"}, "migration"),
    "flyway": ({"migrate", "clean"}, "migration"),
    "goose": ({"up", "down"}, "migration"),
    "helm": ({"uninstall", "delete"}, "cluster"),
}
G2_SUBCOMMANDS = {
    "kubectl": ({"apply", "create", "patch", "scale", "rollout", "label", "annotate"}, "cluster"),
    "helm": ({"install", "upgrade"}, "cluster"),
    "docker": ({"push"}, "publish"),
}
RAILS_G3 = re.compile(r"^db:(migrate|drop|reset|schema:load|rollback)$")


def grade_tokens(tokens, cwd, depth):
    """(grade, verb, target, family) for one simple command."""
    tokens, written = _redirects(tokens)
    wrote = ""
    for target in written:
        if re.match(r"^/dev/(sd|disk|nvme|rdisk)", target):
            return 3, "redirect to", target, "system"
        if target and not target.isdigit() and target != "/dev/null":
            wrote = target
    while tokens and ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return 0, None, None, None
    if ro.segment_ok(list(tokens)):
        return (1, "redirect to", wrote, None) if wrote else (0, None, None, None)
    head = tokens[0]
    prog = head.rpartition("/")[2]
    args = tokens[1:]
    ops = operands(args)
    text = " ".join(tokens)

    if PLACEHOLDER in head or head.startswith("$"):
        return _scan(text)  # the program comes from a substitution or a variable
    if (prog, ops[0] if ops else "") in RUNNERS:
        rest = args[args.index(ops[0]) + 1:]
        while rest and (rest[0].startswith("-") or ASSIGN_RE.match(rest[0])):
            rest = rest[1:]
        if rest:
            return grade_tokens(rest, cwd, depth)
    if prog == "cargo" and ops[:1] == ["run"] and "--" in args:
        rest = args[args.index("--") + 1:]
        if rest:
            return grade_tokens(rest, cwd, depth)
    if prog == "ssh":
        rest = strip_options(args, SSH_VALUE_FLAGS)
        if len(rest) > 1:  # the first operand is the host; the rest runs on it
            return _inner(" ".join(rest[1:]), cwd, depth)
    if prog == "kubectl" and ops[:1] == ["exec"] and "--" in args:
        return _inner_tokens(args[args.index("--") + 1:], cwd, depth)
    if prog in ("docker", "docker-compose") and "exec" in args:
        rest = strip_options(args[args.index("exec") + 1:], DOCKER_EXEC_VALUE_FLAGS)
        if len(rest) > 1:  # the first operand is the container or the service
            return _inner_tokens(rest[1:], cwd, depth)
    if prog in ("fly", "flyctl") and ops[:2] == ["ssh", "console"]:
        for i, a in enumerate(args):
            if a in ("-C", "--command") and i + 1 < len(args):
                return _inner(args[i + 1], cwd, depth)
    if prog in SUDO:
        rest = strip_options(args, SUDO[prog])
        return 3, prog, " ".join(rest[:2]) or _joined(args, 1), "system"
    if prog in SHELLS:
        for i, a in enumerate(args):
            if DASH_C_RE.match(a) and i + 1 < len(args):
                return _inner(args[i + 1], cwd, depth)
    if prog in ("eval",):
        return _inner(" ".join(args), cwd, depth)
    if prog in ("xargs", "parallel"):
        rest = strip_options(args, XARGS_VALUE_FLAGS)
        if _rm_flagged(rest):  # the operands arrive on stdin, so any rm -rf here is grade 3
            return 3, "xargs rm -rf", "", "delete"
        return _inner_tokens(rest, cwd, depth)
    if prog in WRAPPERS:
        rest = strip_options(args, WRAPPERS[prog])
        while rest and ASSIGN_RE.match(rest[0]):
            rest = rest[1:]
        if prog == "timeout" and rest:
            rest = rest[1:]  # the duration
        if rest:
            return grade_tokens(rest, cwd, depth)
        return 1, prog, "", None
    if prog == "git":
        return _git(args, cwd)
    if prog == "gh":
        return _gh(args)
    if prog in ("curl", "wget", "http", "https", "httpie"):
        return _http(prog, args)
    if prog in CLOUD:
        return _cloud(prog, args)
    if prog == "rm":
        return _rm(args, cwd)
    if prog == "find":
        if "-delete" in args:
            return 3, "find -delete", _joined(args, 1), "delete"
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                inner = args[args.index(flag) + 1:]
                inner = [t for t in inner if t not in (";", "+", "\\;", "{}")]
                if _rm_flagged(inner):
                    return 3, "find " + flag + " rm -rf", _joined(args, 1), "delete"
                return _inner_tokens(inner, cwd, depth)
    if prog in SQL_CLIENTS:
        hit = _sql(text)
        if hit:
            return hit
        return 1, prog, _joined(args, 1), None
    if prog == "redis-cli":
        for op in ops:
            if op.upper() in ("FLUSHALL", "FLUSHDB"):
                return 3, "redis-cli " + op.upper(), "", "database"
    if SQL_RE.match(text) or ALTER_DROP_RE.match(text):  # a heredoc body, on its own segment
        return _sql(text)
    if prog == "prisma" or (prog in ("npm", "pnpm", "yarn") and ops[:1] == ["prisma"]):
        rest = ops[1:] if prog != "prisma" else ops
        joined = " ".join(rest[:2])
        if joined in ("migrate deploy", "migrate reset", "db push"):
            return 3, "prisma " + joined, "", "migration"
    if prog in PUBLISH and ops[:1] == [PUBLISH[prog]]:
        return 2, "%s %s" % (prog, PUBLISH[prog]), " ".join(ops[1:2]), "publish"
    if prog in ("rails", "rake", "bin/rails") or ops[:1] == ["rails"]:
        for op in ops:
            if RAILS_G3.match(op):
                return 3, "rails " + op, "", "migration"
    if prog in ("manage.py", "./manage.py") or "manage.py" in ops:
        for op in ops:
            if op in ("migrate", "flush", "sqlflush", "reset_db"):
                return 3, "manage.py " + op, "", "migration"
    if prog == "dbmate" and ops:
        return 3, "dbmate " + ops[0], "", "migration"
    if prog in ("docker", "docker-compose"):
        compose = ops[:2] == ["compose", "down"] or (prog == "docker-compose" and ops[:1] == ["down"])
        if compose and (has(args, "--volumes") or short(args, "v")):
            return 3, "docker compose down -v", "", "delete"
        if ops[:2] == ["system", "prune"] or ops[:2] == ["volume", "prune"]:
            return 3, "docker " + " ".join(ops[:2]), "", "delete"
        if ops[:1] in (["rm"], ["rmi"]) and short(args, "f"):
            return 3, "docker %s -f" % ops[0], " ".join(ops[1:2]), "delete"
    if prog == "kubectl":
        if ops[:1] == ["delete"]:
            if any(a.startswith("--dry-run") for a in args):
                return 1, "kubectl delete --dry-run", " ".join(ops[1:2]), None
            return 3, "kubectl delete", " ".join(ops[1:2]), "cluster"
    if prog == "vercel":
        if has(args, "--prod"):
            return 3, "vercel --prod", "", "deploy"
        if ops[:1] == ["deploy"] or not ops:
            return 2, "vercel deploy", "", "remote"
    if prog == "netlify" and ops[:1] == ["deploy"]:
        if has(args, "--prod"):
            return 3, "netlify deploy --prod", "", "deploy"
        return 2, "netlify deploy", "", "remote"
    if prog in G3_SUBCOMMANDS:
        verbs, family = G3_SUBCOMMANDS[prog]
        if ops[:1] and ops[0] in verbs:
            target = " ".join(ops[1:2]) or ("." if family == "infra" else "")
            return 3, "%s %s" % (prog, ops[0]), target, family
    if prog in G2_SUBCOMMANDS:
        verbs, family = G2_SUBCOMMANDS[prog]
        if ops[:1] and ops[0] in verbs:
            return 2, "%s %s" % (prog, ops[0]), " ".join(ops[1:2]), family
    if prog in ("chmod", "chown", "chgrp") and (short(args, "R") or has(args, "--recursive")):
        for op in ops:
            if op.rstrip("/") in ("", "~"):
                return 3, "%s -R" % prog, op, "system"
    if prog.startswith("mkfs") or prog in ("dd", "shutdown", "reboot", "halt", "diskutil"):
        return 3, prog, _joined(args, 1), "system"
    if prog == "crontab" and has(args, "-r"):
        return 3, "crontab -r", "", "system"
    if prog == "launchctl" and ops[:1] and ops[0] in ("unload", "bootout"):
        return 3, "launchctl " + ops[0], " ".join(ops[1:2]), "system"
    if prog == "kill" and has(args, "-9") and has(args, "-1"):
        return 3, "kill -9 -1", "", "system"
    if prog == "history" and has(args, "-c"):
        return 3, "history -c", "", "system"
    if prog == "shred":
        return 3, "shred", _joined(args, 1), "delete"
    return 1, prog, _joined(args, 1), None


def grade_text(cmd, cwd="", depth=0):
    """(grade, verb, target, family) for a whole command line: the maximum over its parts."""
    if depth == 0 and ro.command_ok(cmd):
        return 0, None, None, None
    if depth >= MAX_DEPTH:
        return _scan(cmd)
    text, bodies = normalize(cmd)
    stripped, inners = _extract_subs(text)
    best = (0, None, None, None)
    for inner in inners:
        hit = _inner(inner, cwd, depth)
        if hit[0] > best[0]:
            best = hit
    parts = segments(stripped) if stripped is not None else None
    if parts is None:
        return max(best, _scan(text), key=lambda h: h[0])
    if bodies and any(seg and seg[0].rpartition("/")[2] in SQL_CLIENTS for seg in parts):
        for body in bodies:  # the shell does not run a body, but a SQL client interprets it
            hit = _sql(body)
            if hit and hit[0] > best[0]:
                best = hit
    for tokens in parts:
        hit = grade_tokens(tokens, cwd, depth)
        if hit[0] > best[0]:
            best = hit
        if best[0] == 3:
            break
    return best


def reason(grade, verb, target, family, variant):
    clause = CLAUSES.get(family) or GENERIC[grade]
    phrase = " ".join(p for p in (verb, target) if p).strip()
    return "grade %d, %s: %s %s (%s, autonomy=%s)" % (
        grade, LABELS[grade], phrase or "this command", clause, HOOK, variant)


def main():
    if ro is None:
        return  # no grammar, no grading: fall through to the normal permission flow
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return
    command, confirmed = strip_marker(command)
    if confirmed:
        return
    variant = stance()
    threshold = THRESHOLDS.get(variant, THRESHOLDS[DEFAULT_STANCE])
    grade, verb, target, family = grade_text(command, payload.get("cwd") or "")
    if grade < threshold or grade == 0:
        return
    text = reason(grade, verb, target, family, variant)
    if payload.get("permission_mode") in DENY_MODES:
        emit("deny", text + DENY_TAIL)
    else:
        emit("ask", text)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open: a bug here costs a prompt, never a block
