"""The retired-name lint: the project's pre-rename brand, slug and site host stay out of living files.

The repository was renamed to Model Citizen. GitHub and the old site host redirect, so a stale link
still resolves, which is exactly why it would creep back unnoticed. `harness lint` fails a line in a
living file that names the old brand, the old repository slug or the old site host.

Three kinds of material keep the old names on purpose and are allowed:

- **Dated areas**, which record what was true when they were written and are never rewritten: the
  BMad corpus (whose issue map keeps the old slug because every mapped issue's planning block renders
  it), dated plans and handoffs, the changelog's released sections, compatibility evidence, any file named for its date,
  and the BMad test fixtures that mirror the issue map's stored slug.
- **On-disk names** such as the config directory, the local work directory and launchd labels. The
  patterns below need the owner prefix, the site domain or the capitalised two-word brand, so a
  bare on-disk name never matches and needs no entry.
- **The "Formerly" lines**, which name the old brand so a reader can find the project by it.

The retired strings are assembled at run time, so this file passes its own rule.
"""
import re
from pathlib import PurePosixPath

_OLD = "agent" + "-harness"
_OWNER = "Jake" + "Selby"
_DOMAIN = "jake" + "selby.com"

# (label, pattern). The slug and host are case-insensitive, as GitHub and DNS are; the brand is
# matched as written, since "an agent harness" is an ordinary phrase.
PATTERNS = (
    ("brand", re.compile(r"\b" + "Agent" + r" Harness\b")),
    ("repository slug", re.compile(r"(?i)\b" + _OWNER + "(?:/|%2F)" + _OLD + r"(?![\w-])")),
    ("site host", re.compile(r"(?i)\b" + re.escape(_OLD + "." + _DOMAIN) + r"\b")),
)

# Path prefixes of dated areas, each with the reason it keeps the old names.
ALLOWED_PREFIXES = (
    ("_bmad-output/", "the BMad corpus is dated, and the issue map keeps the old slug"),
    ("docs/plans/", "dated plans"),
    (".agent-harness/", "dated local plans and handoffs"),
    ("compatibility/evidence/", "dated qualification evidence"),
    ("tests/test_bmad_", "fixtures mirror the issue map's stored slug"),
)
DATED_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}")
FORMERLY = re.compile(r"^\W*Formerly\b")
CHANGELOG = "CHANGELOG.md"
# A released section is headed by its version or its date; `## [Unreleased]` is still living text.
RELEASED_HEADING = re.compile(r"^## \[?(?:v?\d+\.\d+|\d{4}-\d{2}-\d{2})")


def applies(root):
    """Whether the rule binds this checkout: this repository only, the guard the changelog uses."""
    return (root / "primitives" / "roles").is_dir()


def allowed_path(rel):
    """The reason a repository-relative path may keep the old names, or None."""
    text = str(rel).replace("\\", "/")
    for prefix, reason in ALLOWED_PREFIXES:
        if text.startswith(prefix):
            return reason
    if DATED_NAME.match(PurePosixPath(text).name):
        return "the file is named for its date"
    return None


def released_lines(rel, lines):
    """The 1-based numbers of the changelog lines inside a released, and so dated, section."""
    if str(rel).replace("\\", "/") != CHANGELOG:
        return set()
    dated, released = set(), False
    for number, line in enumerate(lines, 1):
        if line.startswith("## "):
            released = bool(RELEASED_HEADING.match(line))
        if released:
            dated.add(number)
    return dated


def line_findings(line):
    """The labels of the retired names a line carries, unless it is a "Formerly" line."""
    if FORMERLY.match(line):
        return []
    return [label for label, rx in PATTERNS if rx.search(line)]
