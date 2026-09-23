"""Read an existing CLAUDE.md, AGENTS.md or `.cursorrules` into primitives.

Adopting the harness should not mean discarding the instructions a repository already carries,
so the file is split rather than replaced: each top-level `##` section becomes one rule, the
prose above the first section becomes a preamble rule, a CLAUDE.md `@`-import is followed one
level and becomes a rule of its own, and `.cursor/rules/*.mdc` front matter is carried through
unchanged. Nothing is dropped. Anything the splitter cannot place — a heading that yields no
identifier, a second section claiming a name already taken, a front-matter line that is not a
field — lands in one `-unsorted` rule with a note saying so, because a silent omission from a
file of instructions is the one outcome an import must never produce.

The splitter is deliberately conservative about what a heading is: a `##` inside a fenced code
block is text, not structure.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

# The front-matter keys a Cursor `.mdc` rule carries. They decide when a rule applies, so they
# survive the split verbatim rather than being re-derived from the body.
MDC_KEYS = ("description", "globs", "alwaysApply")
HEADING = re.compile(r"^##(?!#)\s*(.*?)\s*$")
IMPORT = re.compile(r"^\s*@(\S+)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
UNSORTED_NOTE = ("Imported content the splitter could not place under a heading of its own. "
                 "Nothing here was dropped; sort it into rules by hand.")


def kind_of(path):
    """Which kind of instruction file this is, from its name and suffix."""
    path = Path(path)
    if path.name == "CLAUDE.md":
        return "claude"
    if path.name == "AGENTS.md":
        return "agents"
    if path.name == ".cursorrules":
        return "cursorrules"
    if path.suffix == ".mdc":
        return "mdc"
    raise ValueError("import reads CLAUDE.md, AGENTS.md, .cursorrules or a .cursor/rules/*.mdc "
                     "file; got " + path.name)


def slug(text):
    """A primitive identifier for a heading, or an empty string when it yields none."""
    flattened = "".join(c.lower() if (c.isascii() and c.isalnum()) else "-" for c in text)
    parts = [part for part in flattened.split("-") if part]
    name = "-".join(parts)
    return ("rule-" + name) if name[:1].isdigit() else name


def default_name(path, kind):
    """The import's name: the `.mdc` file's own stem, else the directory it was found in."""
    path = Path(path)
    candidates = [path.stem] if kind == "mdc" else [path.parent.name, path.stem]
    for candidate in candidates:
        found = slug(candidate)
        if found:
            return found
    return "imported"


def frontmatter(text):
    """`(fields, unparsed lines, body)` for a leading `---` block; empty fields when there is none."""
    if not text.startswith("---\n"):
        return {}, [], text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, [], text
    header, body = text[4:end], text[end + 4:].lstrip("\n")
    fields, extra = {}, []
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and key.strip() == key.strip().split()[0] and key not in fields:
            fields[key.strip()] = value.strip()
        elif line.strip():
            extra.append(line)
    return fields, extra, body


def _sections(body):
    """`(preamble lines, [(heading, lines)])`, with fenced blocks left alone."""
    preamble, sections, fence, current = [], [], None, None
    for line in body.splitlines():
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = token if fence is None else (None if fence == token else fence)
        heading = None if fence else HEADING.match(line)
        if heading:
            current = (heading.group(1), [line])
            sections.append(current)
            continue
        (current[1] if current else preamble).append(line)
    return preamble, sections


def _imports(body):
    """Whole-line `@path` imports outside fenced blocks, in order and without duplicates."""
    found, fence = [], None
    for line in body.splitlines():
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = token if fence is None else (None if fence == token else fence)
            continue
        match = None if fence else IMPORT.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def _render(fields, lines):
    body = "\n".join(lines).strip("\n")
    header = "".join(key + ": " + value + "\n" for key, value in fields.items())
    return "---\n" + header + "---\n\n" + body + "\n"


def _heading_of(text):
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def plan(path, name=None, today=None):
    """`(files, notices)`: every rule the import would write, and what it could not resolve.

    A file is `{"path": "rules/<slug>.md", "text": ...}` relative to the primitive root the
    caller has chosen. Nothing is written here; the caller decides whether this plan is printed
    or applied.
    """
    path = Path(path).expanduser()
    kind = kind_of(path)
    source = str(path.resolve())
    stamp = today or date.today().isoformat()
    text = path.read_text(encoding="utf-8")
    fields, extra, body = frontmatter(text)
    name = slug(name) if name else default_name(path, kind)
    if not name:
        raise ValueError("--name must be a primitive identifier: lowercase letters, digits, hyphens")
    carried = {key: fields[key] for key in MDC_KEYS if key in fields}

    def base(**more):
        return dict({"source": source, "imported": stamp}, **dict(carried, **more))

    files, notices, unsorted, taken = [], [], [], set()
    if extra:
        unsorted.append("Front-matter lines that are not fields:")
        unsorted.extend(extra)
    preamble, sections = _sections(body)
    if "\n".join(preamble).strip():
        files.append({"path": "rules/" + name + "-preamble.md",
                      "text": _render(base(), preamble)})
        taken.add(name + "-preamble")
    for heading, lines in sections:
        identifier = slug(heading)
        if not identifier or identifier in taken:
            unsorted.extend(lines if identifier else [""] + lines)
            if identifier:
                notices.append("second section named '" + heading + "'; kept in " + name + "-unsorted")
            else:
                notices.append("heading '" + heading + "' yields no identifier; kept in " + name + "-unsorted")
            continue
        taken.add(identifier)
        files.append({"path": "rules/" + identifier + ".md",
                      "text": _render(base(heading=heading), lines)})
    for reference in _imports(body) if kind in ("claude", "agents") else []:
        target = Path(reference).expanduser()
        if not target.is_absolute():
            target = path.parent / target
        if not target.is_file():
            notices.append("@" + reference + " does not resolve to a readable file; its line was kept")
            continue
        imported = target.read_text(encoding="utf-8")
        identifier = slug(target.stem) or (name + "-import")
        while identifier in taken:
            identifier += "-import"
        taken.add(identifier)
        files.append({"path": "rules/" + identifier + ".md",
                      "text": _render({"source": str(target.resolve()), "imported": stamp,
                                       "heading": _heading_of(imported) or target.stem},
                                      imported.splitlines())})
    if "\n".join(unsorted).strip():
        files.append({"path": "rules/" + name + "-unsorted.md",
                      "text": _render(base(), [UNSORTED_NOTE, ""] + unsorted)})
    return files, notices


def digest(root, files):
    """A stable fingerprint of one plan, so a second run can recognise the plan it printed."""
    payload = json.dumps([str(root)] + [[item["path"], item["text"]] for item in files],
                         sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
