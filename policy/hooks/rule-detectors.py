#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic detectors for the always-loaded rules, run over one session transcript.

This is not a hook: it has no `main()` and no lifecycle event. Nothing outside the tests
runs the registry yet; a follow-up change has the SessionEnd worker (`usage-log.py`) build
the event list below in the pass it already makes over the transcript and call `run()`.
`bin/harness lint` imports `DETECTORS` and `OPT_OUT` today, to check that every rule file
is either measured or has opted out with a reason, and takes `SECRET_PATTERNS` from here.

Event schema
------------
`run(events, stances=None)` consumes a list of dicts, in transcript order. Every event
carries `kind` and `turn` (int, incremented on every `user_prompt`):

- `assistant_text` — `text` (str), `final` (bool: the last assistant text before the
  next user prompt or the end of the transcript), `model` (str).
- `tool_use` — `id` (str), `name` (str), `input` (dict).
- `tool_result` — `tool_use_id` (str), `tool_name` (str, the name of the `tool_use`
  it answers, resolved by the caller), `text` (str).
- `user_prompt` — no extra fields.
- `compact` — no extra fields; one per transcript line with
  `"type":"system","subtype":"compact_boundary"`.

`stances` is a dimension → variant dict, e.g. `{"commits": "conventional-attributed"}`.
The `commits` detectors are skipped when that dimension is absent or `off`.

`run()` returns `{detector_id: [Hit, ...]}` with `Hit = (detector_id, turn, tool_use_id
or None)`, and omits detectors with no hits. A hit never carries a snippet, for any
detector: the transcript is the evidence, and `usage.jsonl` holds no command text (plan
decision 3). A detector that raises is skipped, so one bad pattern cannot cost a session
its record; `run(..., strict=True)` re-raises instead, which is how the corpus is tested.

Cost
----
Every Bash command is parsed once, in `analyse()`, and the parse is shared by all the
shell detectors. A command longer than `MAX_COMMAND` (16 KB) is not parsed at all — the
tokenizer is superlinear in line length and a pasted file is never what these detectors
are looking for. Such a command is scanned for secret shapes as plain text and is
invisible to every other detector. A command of any other shape — absent, a number, a
list — parses to nothing and is passed over; no transcript shape raises out of `run()`.

Known misses
------------
Under-counting is the design: a missed hit is a quieter report, a false hit is a wrong
one. The three known misses, none worth the parser they would cost:

- A heredoc header behind a `#` comment (`cat <<EOF  # note`) is read as a heredoc,
  because the body is lifted out before comments are stripped.
- A `git commit` nested inside a substitution (`$(git commit -m …)`) is invisible: the
  substitution is replaced wholesale before the segments are split.
- Literal text equal to a heredoc marker (`__HARNESS_HEREDOC_0__`) in a `-m` value is
  resolved as if it were that heredoc's body.
"""
import importlib.util
import os
import re
import shlex

# Moved here from `bin/harness`, which imports this module: one source of truth for the
# lint and for the secret-in-write detector. The `aws_secret` literal is split so this
# file does not trip the lint that uses it.
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}", r"(?i)aws_secret" r"_access_key", r"Bearer [A-Za-z0-9._-]{20,}",
    r"(?i)client_secret\s*[:=]", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"xox[bp]-", r"ghp_[A-Za-z0-9]{20,}",
    r"sk-[A-Za-z0-9]{20,}",
]

# The three openers and the closing phrase are read from `claude/output-styles/scannable.md`
# (lines 27 and 126) at build time and frozen here; this module never reads a file at runtime.
BANNED_OPENERS = ("I started by", "After investigating", "Great question")
BANNED_CLOSER = "Let me know if"

# The two shapes `decisions-and-plans` prescribes — a batched "Decisions" block, or a
# recommendation line — and the markers that show another course was named beside them.
# The trigger is a line that *opens* with the word; an inline "I recommend" in running
# prose is not a decision block and does not fire.
DECISION_RE = re.compile(
    r"^[\s*_>#|-]*recommend(?:ation|ed|ing|s)?\b"
    r"|\brecommendation:"
    r"|^[\s*_>#|-]*decisions?\b[\s*_:-]*$",
    re.I | re.M,
)
ALTERNATIVE_RE = re.compile(
    r"\balternativ|^[\s*_>#|-]*alt\b|\bagainst:|\bhonest case\b|^[\s*_>#|-]*option\s",
    re.I | re.M,
)

# `WebSearch` is capped per session by claude/rules/research-and-verification.md.
SEARCH_CAP = 200

# Longest Bash command worth tokenizing; see "Cost" above.
MAX_COMMAND = 16 * 1024

# Agents whose own definition carries the word cap, so a brief need not repeat it.
CAPPED_AGENTS = frozenset(("log-compressor", "gatherer", "reviewer", "spec-reviewer", "design-judge"))

CONVENTIONAL_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)(\([^)]+\))?!?: \S")
# Every shape a word cap is written in: "at most 400 words", "400 words max", "400 words
# or fewer", "within 400 words", "a 400-word cap", "cap the return at 400 words". A cap
# always carries a number, so "keep it short" is still a miss.
WORD_CAP_RE = re.compile(
    r"(?i)(?:(?:at most|no more than|under|within|max(?:imum)?|≤|<=)\s*\d+\s*[- ]?words?"
    r"|\d+\s*[- ]?words?\s*(?:or (?:fewer|less)|max(?:imum)?|cap)"
    r"|\d+\s*[- ]?word\s+cap"
    r"|cap[^.\n]{0,40}?\d+\s*[- ]?words?"
    r"|word\s+cap\s*(?:of\s+)?\d+)"
)
# The autonomy gate's two marks: the prefix the model re-runs a denied command behind, and the
# signature the grade hook writes into the reason it denies with. The marker pattern mirrors
# `grade-bash.py`'s own `MARKER_RE`, so what the gate lets through is what this counts; a
# quoted value (`HARNESS_CONFIRMED="1"`) is not the marker there and is not one here.
_COMMENT_RE = re.compile(r"^(?:\s*(?:#[^\n]*)?\n)+")
_CONFIRMED_RE = re.compile(r"^\s*(?:env\s+)?HARNESS_CONFIRMED=1\s*;?\s*")
GRADE_SIGNATURE = "(grade-bash hook,"
# A path that says it holds a credential, by basename; see `_is_secret_path`.
ENV_EXAMPLES = frozenset(("example", "sample", "template", "dist"))
KEY_SUFFIXES = (".pem", ".p12", ".pfx")
FIND_FILTERS = frozenset((
    "-name", "-iname", "-path", "-ipath", "-regex", "-iregex", "-type", "-maxdepth", "-mindepth",
    "-mmin", "-mtime", "-newer", "-newermt", "-size", "-perm", "-user", "-group", "-empty",
    "-prune", "-exec", "-execdir", "-delete", "-print0",
))

_PIPE = frozenset(("|", "|&"))
_BREAK = frozenset((";", "&&", "||", "&", ";;", "(", ")"))
_DROP = frozenset(("do", "done", "then", "fi", "else", "esac", "{", "}", "!",
                   "while", "until", "if", "elif", "for", "select", "case", "in"))
_REDIRECTS = re.compile(r"^\d*(<|<<|<<<|<&|>|>>|&>|>&)$")
_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")
_HOOK_BYPASS_ASSIGNMENTS = ("SKIP", "PRE_COMMIT_ALLOW_NO_CONFIG")
_HOOK_AWARE = frozenset(("git", "pre-commit"))

# A heredoc body is lifted out of the command and left behind as this marker, so the
# command a body belongs to is still visible in the token stream.
_MARKER = "__HARNESS_HEREDOC_%d__"
_MARKER_RE = re.compile(r"^__HARNESS_HEREDOC_(\d+)__$")
# `git commit -m "$(cat <<'EOF' … EOF)"`, the form Claude Code writes: the substitution
# exists only to carry the heredoc, so the marker takes its place as the `-m` value.
_CAT_SUB_RE = re.compile(r"\$\(\s*cat\s+<<\s*(__HARNESS_HEREDOC_\d+__)\s*\)")
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,})(.*)$")


def _readonly_grammar():
    """The shipped read-only classifier, imported from the sibling hook, or None."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allow-readonly-bash.py")
    try:
        spec = importlib.util.spec_from_file_location("_harness_readonly_bash", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


_GRAMMAR = _readonly_grammar()
# What the grammar leaves where a command substitution stood; a message that resolves to
# one was never read, so it is not judged.
_PLACEHOLDER = getattr(_GRAMMAR, "_PLACEHOLDER", "__ROSUB__")


# --- shell decomposition -----------------------------------------------------------


def _heredoc_headers(line):
    """`(start, end, delimiter)` for every heredoc operator that is a real shell word.

    `<<` inside quotes is data — `grep -n '<<EOF' file` opens no heredoc — so the scan
    tracks quoting. `<<-`, `<<"EOF"` and `<<'MSG-END'` are all headers; `<<<` is not.
    A substitution quotes afresh, which is what makes the `-m "$(cat <<'EOF' …)"` form
    a heredoc and not a string.
    """
    out = []
    sq = dq = False
    stack = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if sq:
            sq = c != "'"
            i += 1
            continue
        if dq and not line.startswith("$(", i):
            if c == "\\":
                i += 2
                continue
            dq = c != '"'
            i += 1
            continue
        if line.startswith("$(", i):
            stack.append(dq)
            dq = False
            i += 2
            continue
        if c == ")" and stack:
            dq = stack.pop()
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "'":
            sq = True
            i += 1
            continue
        if c == '"':
            dq = True
            i += 1
            continue
        if line.startswith("<<<", i):  # a herestring, not a heredoc
            i += 3
            continue
        if line.startswith("<<", i):
            j = i + 2
            if j < n and line[j] == "-":
                j += 1
            while j < n and line[j] in " \t":
                j += 1
            if j < n and line[j] in "\"'":
                quote = line[j]
                k = line.find(quote, j + 1)
                if k == -1:
                    break
                out.append((i, k + 1, line[j + 1:k]))
                i = k + 1
                continue
            k = j
            while k < n and (line[k].isalnum() or line[k] in "_-."):
                k += 1
            if k > j:
                out.append((i, k, line[j:k]))
                i = k
                continue
        i += 1
    return out


def strip_heredocs(command):
    """`(command with each heredoc body lifted out, [body, ...])`.

    The operator stays as `<< __HARNESS_HEREDOC_n__`, so a segment carrying a heredoc is
    still recognisable as redirected and the body can be bound back to its own command.
    """
    lines = command.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept, bodies = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        headers = _heredoc_headers(line)
        rewritten, cursor = [], 0
        for start, end, delimiter in headers:
            body = []
            while i < len(lines) and lines[i].strip() != delimiter:
                body.append(lines[i])
                i += 1
            i += 1  # the terminator line itself
            rewritten.append(line[cursor:start])
            rewritten.append("<< " + (_MARKER % len(bodies)))
            cursor = end
            bodies.append("\n".join(body))
        rewritten.append(line[cursor:])
        kept.append("".join(rewritten))
    return "\n".join(kept), bodies


def _shell_lines(text):
    """`text` split at the newlines bash treats as command separators: the ones outside
    quotes. A newline inside a `-m "…"` message is part of the message, not a new
    command."""
    out, start = [], 0
    sq = dq = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\" and not sq:
            i += 2
            continue
        if sq:
            sq = c != "'"
        elif dq:
            dq = c != '"'
        elif c == "'":
            sq = True
        elif c == '"':
            dq = True
        elif c == "\n":
            out.append(text[start:i])
            start = i + 1
        i += 1
    out.append(text[start:])
    return out


def tokenize(text):
    """Shell tokens for already-heredoc-stripped `text`, using the read-only hook's own
    decomposition: substitutions become placeholders, comments go, and the newlines that
    separate commands become `;` — the ones inside a quoted argument are left alone."""
    # A continuation is one command, so it is joined before anything is split.
    text = re.sub(r"\\\r?\n[ \t]*", " ", text)
    if _GRAMMAR is not None:
        stripped = _GRAMMAR._strip_subs(text, 0)
        if stripped is not None:
            text = stripped
        text = " ; ".join(_GRAMMAR._strip_comment(line) for line in _shell_lines(text))
    else:
        text = " ; ".join(_shell_lines(text))
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.commenters = ""
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return []


def _pipelines(tokens):
    """Tokens as a list of pipelines, each a list of segments, each a token list."""
    out, pipe, seg = [], [], []
    for token in tokens:
        if token in _BREAK:
            if seg:
                pipe.append(seg)
                seg = []
            if pipe:
                out.append(pipe)
                pipe = []
            continue
        if token in _PIPE:
            if seg:
                pipe.append(seg)
                seg = []
            continue
        if not seg and token in _DROP:
            continue
        seg.append(token)
    if seg:
        pipe.append(seg)
    if pipe:
        out.append(pipe)
    return out


def pipelines(command):
    """`command` parsed from raw text. `analyse()` is the path detectors use; this one
    is for callers with a single command in hand, and for the tests."""
    text, _ = strip_heredocs(command)
    return _pipelines(tokenize(_CAT_SUB_RE.sub(r"\1", text)))


def operands(segment):
    """The segment's positional words: no flags, no redirect operators or targets."""
    out = []
    skip = False
    for token in segment[1:]:
        if skip:
            skip = False
            continue
        if _REDIRECTS.match(token):
            skip = True
            continue
        if token.startswith("-"):
            continue
        out.append(token)
    return out


def has_redirect(segment):
    return any(_REDIRECTS.match(t) for t in segment)


def normalise(command):
    """Whitespace-collapsed command text, without a leading `cd <dir> &&`."""
    text = " ".join(command.split())
    return re.sub(r"^cd\s+\S+\s*&&\s*", "", text).strip()


def _input(event):
    """A tool use's input, always a dict. A transcript is machine-written but not
    schema-checked, so every field is treated as untrusted shape."""
    data = event.get("input")
    return data if isinstance(data, dict) else {}


def _text(value):
    return value if isinstance(value, str) else ""


def _split_assignments(segment):
    """`(leading NAME=VALUE assignments, the command and its arguments)`."""
    i = 0
    while i < len(segment) and _ASSIGNMENT_RE.match(segment[i]):
        i += 1
    return segment[:i], segment[i:]


def _git_calls(parsed, subcommands):
    """`(segment, subcommand, args)` for every `git <subcommand>` in a parsed command."""
    for pipe in parsed.pipelines:
        for segment in pipe:
            _, words = _split_assignments(segment)
            if not words or words[0] != "git":
                continue
            rest = words[1:]
            i = 0
            while i < len(rest) and rest[i].startswith("-"):
                i += 2 if rest[i] in ("-C", "-c") else 1
            if i < len(rest) and rest[i] in subcommands:
                yield segment, rest[i], rest[i + 1:]


def _messages_of(parsed, args):
    """Every `-m` value of one `git commit`, in order, markers resolved to their body.

    `git commit` with no `-m` — `--amend --no-edit`, `-F file`, `-C <commit>` — carries no
    message here: a heredoc elsewhere in the command belongs to that other command, not
    to the commit. Neither does a commit whose message is a substitution the parse could
    not open (`-m "$(cat msg.txt)"`): an unread message is not a bad one, so the whole
    commit yields no messages rather than an empty subject.
    """
    out = []
    i = 0
    while i < len(args):
        token = args[i]
        value = None
        if token == "--message":
            value = args[i + 1] if i + 1 < len(args) else ""
            i += 2
        elif token.startswith("--message="):
            value = token.split("=", 1)[1]
            i += 1
        elif token.startswith("-") and not token.startswith("--") and "m" in token[1:]:
            # A short cluster: everything after the first `m` is the value, as git reads
            # it, so `-am`, `-sm` and `-mfeat: x` all land here.
            rest = token[1:].split("m", 1)[1]
            if rest:
                value = rest
                i += 1
            else:
                value = args[i + 1] if i + 1 < len(args) else ""
                i += 2
        else:
            i += 1
            continue
        value = _text(value)
        match = _MARKER_RE.match(value)
        if match:
            index = int(match.group(1))
            value = parsed.heredocs[index] if index < len(parsed.heredocs) else ""
        if not value.strip() or _PLACEHOLDER in value or "$(" in value:
            return []
        out.append(value)
    return out


def _secret_in(text):
    return any(re.search(p, text) for p in SECRET_PATTERNS)


def _is_secret_path(path):
    """A path whose own name says it holds a credential."""
    base = path.rstrip("/").rsplit("/", 1)[-1]
    if base == ".env":
        return True
    if base.startswith(".env."):
        return base.split(".", 2)[2].lower() not in ENV_EXAMPLES
    if base.lower().endswith(KEY_SUFFIXES):
        return True
    if "id_rsa" in base or "id_ed25519" in base:
        return True
    return base.split(".", 1)[0] == "credentials"


# --- the parsed view ---------------------------------------------------------------


class Parsed(object):
    """One Bash tool use, parsed once and shared by every shell detector."""

    __slots__ = ("event", "command", "skipped", "heredocs", "pipelines", "normalised")

    def __init__(self, event):
        self.event = event
        self.command = _text(_input(event).get("command"))
        self.heredocs, self.pipelines, self.normalised = [], [], ""
        # A command that is absent, a number, a list or bytes parses to nothing at all;
        # the event stays in the list and every shell detector simply passes over it.
        self.skipped = not self.command or len(self.command) > MAX_COMMAND
        if self.skipped:
            return
        try:
            text, self.heredocs = strip_heredocs(self.command)
            self.pipelines = _pipelines(tokenize(_CAT_SUB_RE.sub(r"\1", text)))
            self.normalised = normalise(self.command)
        except Exception:
            self.heredocs, self.pipelines, self.normalised = [], [], ""
            self.skipped = True

    @property
    def turn(self):
        return self.event.get("turn", 0)

    @property
    def id(self):
        return self.event.get("id")


class Context(object):
    """One pass over the events: the Bash parses and the final assistant messages."""

    __slots__ = ("events", "bash", "finals")

    def __init__(self, events):
        self.events = events
        self.bash = []
        self.finals = []
        for event in events:
            kind = event.get("kind")
            if kind == "tool_use" and event.get("name") == "Bash":
                self.bash.append(Parsed(event))
            elif kind == "assistant_text" and event.get("final"):
                self.finals.append(event)


def analyse(events):
    """The parsed view `run()` hands to every detector. Anything that is not a dict
    event is dropped here, so no detector has to defend itself against the shape."""
    if not isinstance(events, (list, tuple)):
        events = []
    return Context([e for e in events if isinstance(e, dict)])


def _hit(event, tool_use_id=True):
    return (event.get("turn", 0), event.get("id") if tool_use_id else None)


# --- detectors ---------------------------------------------------------------------


def whole_file_cat(events, ctx):
    """A lone `cat <one path>`: no pipe, no filter, no heredoc, no redirect."""
    hits = []
    for parsed in ctx.bash:
        for pipe in parsed.pipelines:
            if len(pipe) != 1:
                continue
            segment = pipe[0]
            if not segment or segment[0] != "cat":
                continue
            if has_redirect(segment) or len(operands(segment)) != 1:
                continue
            hits.append(_hit(parsed.event))
            break
    return hits


def unfiltered_find(events, ctx):
    """`find <dir>` with no filtering predicate and nothing consuming its output."""
    hits = []
    for parsed in ctx.bash:
        for pipe in parsed.pipelines:
            if len(pipe) != 1:
                continue
            segment = pipe[0]
            if not segment or segment[0] != "find":
                continue
            if has_redirect(segment) or any(t in FIND_FILTERS for t in segment[1:]):
                continue
            hits.append(_hit(parsed.event))
            break
    return hits


def brief_without_cap(events, ctx):
    """An `Agent` brief with no word cap, for an agent whose definition carries none."""
    hits = []
    for event in events:
        if event.get("kind") != "tool_use" or event.get("name") != "Agent":
            continue
        data = _input(event)
        if _text(data.get("subagent_type")) in CAPPED_AGENTS:
            continue
        if not WORD_CAP_RE.search(_text(data.get("prompt"))):
            hits.append(_hit(event))
    return hits


def _fenced_lines(text):
    """Every line inside a fenced code block, by the CommonMark closing rule: a closing
    fence carries at least as many backticks as the opener and no info string."""
    out, opener = [], None
    for line in (text or "").split("\n"):
        match = _FENCE_RE.match(line)
        if opener is None:
            if match:
                opener = len(match.group(1))
            continue
        if match and len(match.group(1)) >= opener and not match.group(2).strip():
            opener = None
            continue
        out.append(line)
    return out


def executed_from_summary(events, ctx):
    """A Bash command whose first appearance in the session was inside an `Agent` return.

    A command the session already ran, and a subagent then quoted back, is not a hit: the
    rule is about acting on text that arrived from a subagent, not about repetition.
    """
    origin, hits = {}, []
    for event in events:
        kind = event.get("kind")
        if kind == "tool_result" and event.get("tool_name") == "Agent":
            for line in _fenced_lines(_text(event.get("text"))):
                text = " ".join(line.split())
                if text:
                    origin.setdefault(text, "agent")
        elif kind == "tool_use" and event.get("name") == "Bash":
            command = _text(_input(event).get("command"))
            if not command:
                continue
            text = normalise(command)
            if origin.setdefault(text, "bash") == "agent":
                hits.append(_hit(event))
    return hits


def no_verify(events, ctx):
    """A commit or push that walks past the repository's own hooks."""
    hits = []
    for parsed in ctx.bash:
        flagged = False
        for segment, sub, args in _git_calls(parsed, ("commit", "push")):
            if "--no-verify" in args or (sub == "commit" and "-n" in args):
                flagged = True
            if any(t.startswith("core.hooksPath=") for t in segment):
                flagged = True
        for pipe in parsed.pipelines:
            for segment in pipe:
                assignments, words = _split_assignments(segment)
                if not words or words[0] not in _HOOK_AWARE:
                    continue
                for token in assignments:
                    if token.split("=", 1)[0] in _HOOK_BYPASS_ASSIGNMENTS:
                        flagged = True
        if flagged:
            hits.append(_hit(parsed.event))
    return hits


def secret_in_write(events, ctx):
    """A secret-shaped string written to a file or into a heredoc body."""
    hits, parsed_by_id = [], dict((id(p.event), p) for p in ctx.bash)
    for event in events:
        if event.get("kind") != "tool_use":
            continue
        name = event.get("name")
        data = _input(event)
        texts = []
        if name == "Write":
            texts.append(_text(data.get("content")))
        elif name == "Edit":
            texts.append(_text(data.get("new_string")))
        elif name == "Bash":
            parsed = parsed_by_id.get(id(event))
            # An unparsed command is scanned whole: a key in it matters more than which
            # word of it the key sat in.
            texts.extend([parsed.command] if parsed is not None and parsed.skipped
                         else (parsed.heredocs if parsed is not None else []))
        if any(_secret_in(t) for t in texts if t):
            hits.append(_hit(event))
    return hits


def git_add_secret_file(events, ctx):
    """`git add` of a path whose name says it holds a credential."""
    hits = []
    for parsed in ctx.bash:
        for _, _, args in _git_calls(parsed, ("add",)):
            if any(_is_secret_path(a) for a in args if not a.startswith("-")):
                hits.append(_hit(parsed.event))
                break
    return hits


def counts(events):
    """Per-session tool counts the report records whether or not a detector fires."""
    out = {"web_search": 0, "agent": 0, "ask_user": 0}
    keys = {"WebSearch": "web_search", "Agent": "agent", "AskUserQuestion": "ask_user"}
    for event in events or []:
        if isinstance(event, dict) and event.get("kind") == "tool_use":
            key = keys.get(event.get("name"))
            if key:
                out[key] += 1
    return out


def search_over_cap(events, ctx):
    """One hit on the search that takes the session past the per-session cap."""
    seen = 0
    for event in events:
        if event.get("kind") == "tool_use" and event.get("name") == "WebSearch":
            seen += 1
            if seen == SEARCH_CAP + 1:
                return [_hit(event)]
    return []


def model_switch(events, ctx):
    """A model change mid-session rebuilds the cached prefix; one hit per change.

    A synthetic model name (`<synthetic>`, and anything else the transcript brackets)
    marks a harness-generated turn, not a switch the user made; it is ignored.
    """
    hits, current = [], None
    for event in events:
        if event.get("kind") != "assistant_text":
            continue
        model = _text(event.get("model"))
        if not model or model.startswith("<"):
            continue
        if current is not None and model != current:
            hits.append(_hit(event, tool_use_id=False))
        current = model
    return hits


def compaction(events, ctx):
    return [_hit(e, tool_use_id=False) for e in events if e.get("kind") == "compact"]


def _unmarked(text):
    """`text` with quoted and backticked spans blanked, so a phrase under discussion is
    not read as a phrase in use."""
    return re.sub(r"`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"", " ", text)


def banned_opener(events, ctx):
    hits = []
    for event in ctx.finals:
        text = _text(event.get("text"))
        opener = re.sub(r"^[\s*#>_\-]+", "", text)
        if opener.startswith(BANNED_OPENERS) or BANNED_CLOSER in _unmarked(text):
            hits.append(_hit(event, tool_use_id=False))
    return hits


def second_table(events, ctx):
    """Two or more table blocks in one final message; a block is two or more
    consecutive lines starting with `|`."""
    hits = []
    for event in ctx.finals:
        blocks, run_len = 0, 0
        for line in _text(event.get("text")).split("\n"):
            if line.lstrip().startswith("|"):
                run_len += 1
                if run_len == 2:
                    blocks += 1
            else:
                run_len = 0
        if blocks >= 2:
            hits.append(_hit(event, tool_use_id=False))
    return hits


def recommendation_without_alternative(events, ctx):
    """A final message that decides between courses and names only one. The rule asks for
    "the alternatives with their honest case", so a batched `Decisions` block or a
    recommendation line standing alone is the shape it forbids. Markers are read out of
    the raw text rather than the unmarked text, so an alternative named inside a quote
    still counts as named."""
    hits = []
    for event in ctx.finals:
        text = _text(event.get("text"))
        if DECISION_RE.search(_unmarked(text)) and not ALTERNATIVE_RE.search(text):
            hits.append(_hit(event, tool_use_id=False))
    return hits


def _commit_messages(parsed):
    """The `-m` values of every `git commit` in one parsed command, commit by commit."""
    return [_messages_of(parsed, args) for _, sub, args in _git_calls(parsed, ("commit",))]


def non_conventional(events, ctx):
    """A commit subject that is not a Conventional Commit line."""
    hits = []
    for parsed in ctx.bash:
        for messages in _commit_messages(parsed):
            if not messages:
                continue
            subject = messages[0].strip().split("\n")[0].strip()
            if subject and not CONVENTIONAL_RE.match(subject):
                hits.append(_hit(parsed.event))
                break
    return hits


def missing_trailer(events, ctx):
    """A commit whose message carries no `Co-Authored-By:` line, in any `-m`."""
    hits = []
    for parsed in ctx.bash:
        for messages in _commit_messages(parsed):
            if not messages:
                continue
            if not re.search(r"(?im)^\s*Co-Authored-By:", "\n".join(messages)):
                hits.append(_hit(parsed.event))
                break
    return hits


def confirmed_irreversible(events, ctx):
    """A command re-run behind the marker, which is a grade-3 action the user said yes to.

    `env` may carry the assignment, as the shell allows, and leading blank or comment lines
    are nothing the shell runs; anything else before the marker means the gate saw a different
    command from this one, so a marker buried mid-command confirms nothing and counts nothing.
    """
    return [_hit(p.event) for p in ctx.bash
            if _CONFIRMED_RE.match(_COMMENT_RE.sub("", p.command))]


def denied_by_grade(events, ctx):
    """A Bash result carrying the grade hook's signature: the gate fired and the command
    never ran. The hook signs its own deny reason, so the string is the evidence — the
    detector never imports it, and reads no other hook's output as a denial."""
    hits = []
    for event in events:
        if event.get("kind") != "tool_result" or event.get("tool_name") != "Bash":
            continue
        if GRADE_SIGNATURE in _text(event.get("text")):
            hits.append((event.get("turn", 0), event.get("tool_use_id") or None))
    return hits


class Detector(object):
    """One rule, one observable, one function over the event list and its parse."""

    __slots__ = ("id", "rule", "kind", "fn", "stance")

    def __init__(self, id, rule, kind, fn, stance=None):
        self.id = id
        self.rule = rule
        self.kind = kind
        self.fn = fn
        self.stance = stance  # (dimension, allowed variants) or None for always-on

    def __repr__(self):
        return "Detector(%r, rule=%r, kind=%r)" % (self.id, self.rule, self.kind)


_COMMITS_ON = ("commits", None)  # any variant but `off`
_VOICE_ON = ("voice", None)  # the shape is the stance's; `off` imposes none
_COMMITS_ATTRIBUTED = ("commits", ("conventional-attributed",))

_REGISTRY = [
    Detector("transcript-hygiene/whole-file-cat", "transcript-hygiene", "bash", whole_file_cat),
    Detector("transcript-hygiene/unfiltered-find", "transcript-hygiene", "bash", unfiltered_find),
    Detector("transcript-hygiene/brief-without-cap", "transcript-hygiene", "agent-brief", brief_without_cap),
    Detector("delegation/executed-from-summary", "delegation", "bash", executed_from_summary),
    Detector("verification/no-verify", "verification", "bash", no_verify),
    Detector("secrets/secret-in-write", "secrets", "write", secret_in_write),
    Detector("secrets/git-add-secret-file", "secrets", "bash", git_add_secret_file),
    Detector("research/search-over-cap", "research-and-verification", "session", search_over_cap),
    Detector("cache-hygiene/model-switch", "cache-hygiene", "session", model_switch),
    Detector("cache-hygiene/compact", "cache-hygiene", "session", compaction),
    Detector("voice/banned-opener", "voice-and-format", "assistant-final", banned_opener, _VOICE_ON),
    Detector("voice/second-table", "voice-and-format", "assistant-final", second_table, _VOICE_ON),
    Detector("decisions/no-alternatives", "decisions-and-plans", "assistant-final",
             recommendation_without_alternative),
    Detector("autonomy/confirmed-irreversible", "autonomy", "bash", confirmed_irreversible),
    Detector("autonomy/denied-by-grade", "autonomy", "bash", denied_by_grade),
    Detector("commits/non-conventional", "commits", "bash", non_conventional, _COMMITS_ON),
    Detector("commits/missing-trailer", "commits", "bash", missing_trailer, _COMMITS_ATTRIBUTED),
]

DETECTORS = dict((d.id, d) for d in _REGISTRY)

# Rules with nothing a transcript can decide. The reason is what the lint prints.
OPT_OUT = {
    "conciseness": "a comment's redundancy is a judgment over the codebase, not a transcript pattern",
    "working-style": "\"verify before you claim\" needs a semantic link between a claim and a command",
}


def _enabled(detector, stances):
    if detector.stance is None:
        return True
    dimension, allowed = detector.stance
    variant = (stances or {}).get(dimension)
    if not variant or variant == "off":
        return False
    return allowed is None or variant in allowed


def run(events, stances=None, strict=False, errors=None):
    """Every detector over one session's events; detectors with no hits are omitted."""
    try:
        ctx = analyse(events)
    except Exception as exc:
        if strict:
            raise
        if errors is not None:
            errors.append({"detector": "analysis", "error": type(exc).__name__})
        return {}  # a session keeps its usage record even when its transcript is odd
    out = {}
    for detector in _REGISTRY:
        if not _enabled(detector, stances):
            continue
        try:
            raw = detector.fn(ctx.events, ctx)
        except Exception as exc:
            if strict:
                raise
            if errors is not None:
                errors.append({"detector": detector.id, "error": type(exc).__name__})
            continue
        if raw:
            out[detector.id] = [(detector.id, turn, tool_use_id) for turn, tool_use_id in raw]
    return out
