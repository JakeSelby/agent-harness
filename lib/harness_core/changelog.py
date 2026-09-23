"""Changelog fragments: one file per change, assembled into CHANGELOG.md at release time.

Every branch used to add its entry to the same `## [Unreleased]` block, so any two branches in
flight conflicted there; new files merge. The naming, the waiver and the assembly are described
for contributors in `changelog.d/README.md`.
"""
import re
import subprocess
from pathlib import Path

DIRECTORY = "changelog.d"
# Keep a Changelog order; `none` is the waiver and is never rendered.
KINDS = ("added", "changed", "removed", "fixed")
WAIVER = "none"
NAME = re.compile(r"^([1-9][0-9]*)\.([a-z]+)\.md$")
IGNORED = ("README.md",)
ROOTS = ("bin/", "lib/", "adapters/", "primitives/", "policy/", "docs/", "scripts/")
MINIMUM_REASON = 20
BASE = "origin/main"
# Entries for this version and earlier were written into `## [Unreleased]` by hand; a branch
# cut while VERSION is older may still satisfy the rule with a CHANGELOG.md edit.
FIRST_FRAGMENT_RELEASE = (0, 13, 0)


def parse_name(name):
    """(number, kind) for a fragment file name, or ValueError naming the expected shape."""
    match = NAME.match(name)
    kinds = KINDS + (WAIVER,)
    if not match or match.group(2) not in kinds:
        raise ValueError("changelog fragment %s is not named <issue-or-pr>.<%s>.md"
                         % (name, "|".join(kinds)))
    return int(match.group(1)), match.group(2)


def fragments(root):
    """Every fragment as (number, kind, text), in render order. Malformed names are refused."""
    directory = Path(root) / DIRECTORY
    found = []
    if not directory.is_dir():
        return found
    for path in sorted(directory.iterdir()):
        if path.name in IGNORED or not path.is_file():
            continue
        number, kind = parse_name(path.name)
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("changelog fragment %s is empty" % path.name)
        found.append((number, kind, text))
    order = {kind: index for index, kind in enumerate(KINDS + (WAIVER,))}
    return sorted(found, key=lambda item: (order[item[1]], item[0]))


def _entry(number, text):
    reference = "(#%d)" % number
    if not text.endswith(reference):
        text += " " + reference
    lines = text.splitlines()
    return "\n".join(["- " + lines[0]] + [("  " + line) if line.strip() else "" for line in lines[1:]])


def render(entries):
    """The body of a version section: one `###` block per kind that has entries."""
    blocks = []
    for kind in KINDS:
        items = [_entry(number, text) for number, found, text in entries if found == kind]
        if items:
            blocks.append("### %s\n\n%s" % (kind.capitalize(), "\n\n".join(items)))
    return "\n\n".join(blocks)


def assemble(changelog, version, date, entries):
    """CHANGELOG.md text with a `## [version] — date` section inserted under an empty Unreleased.

    Refuses rather than guesses when Unreleased still holds hand-written entries, when the
    version already has a section, or when there is nothing to assemble.
    """
    body = render(entries)
    if not body:
        raise ValueError("no changelog fragments to assemble")
    if re.search(r"^## \[%s\]" % re.escape(version), changelog, re.MULTILINE):
        raise ValueError("CHANGELOG.md already has a section for %s" % version)
    heading = re.search(r"^## \[Unreleased\][^\n]*\n", changelog, re.MULTILINE)
    if heading is None:
        raise ValueError("CHANGELOG.md has no ## [Unreleased] heading")
    following = re.search(r"^## \[", changelog[heading.end():], re.MULTILINE)
    end = heading.end() + following.start() if following else len(changelog)
    if changelog[heading.end():end].strip():
        raise ValueError("## [Unreleased] still holds hand-written entries; fold them into a "
                         "version section or move them into fragments first")
    section = "## [%s] — %s\n\n%s\n" % (version, date, body)
    rest = changelog[end:]
    return changelog[:heading.end()] + "\n" + section + ("\n" + rest if rest else "")


def _git(root, *argv):
    out = subprocess.run(["git", "-C", str(root)] + list(argv), capture_output=True, text=True,
                         timeout=10)
    return out.stdout if out.returncode == 0 else None


def changed_paths(root, base=BASE):
    """Paths this branch changes against where it left `base`, uncommitted work included.

    None when there is no `base` to compare with or the branch has no commit of its own, so a
    checkout sitting on the trunk, a tag build and a push to main are never judged.
    """
    head = _git(root, "rev-parse", "HEAD")
    fork = _git(root, "merge-base", "HEAD", base)
    if not head or not fork or head.strip() == fork.strip():
        return None
    diffed = _git(root, "diff", "--name-only", fork.strip())
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if diffed is None or untracked is None:
        return None
    return sorted(set(diffed.splitlines() + untracked.splitlines()) - {""})


def _version(root):
    try:
        return tuple(int(part) for part in (Path(root) / "VERSION").read_text().strip().split("."))
    except (OSError, ValueError):
        return None


def findings(root, paths=None):
    """Lint findings: a malformed fragment anywhere, or a branch that touches ROOTS without one."""
    root = Path(root)
    hits = []
    try:
        fragments(root)
    except ValueError as error:
        hits.append("changelog: %s" % error)
    if paths is None:
        paths = changed_paths(root)
    if not paths:
        return hits
    touched = [path for path in paths if path.startswith(ROOTS)]
    if not touched:
        return hits
    added = [path for path in paths if path.startswith(DIRECTORY + "/")
             and Path(path).name not in IGNORED and (root / path).is_file()]
    if added:
        for path in added:
            try:
                number, kind = parse_name(Path(path).name)
            except ValueError:
                continue
            if kind == WAIVER and len((root / path).read_text(encoding="utf-8").strip()) < MINIMUM_REASON:
                hits.append("changelog: waiver %s must give a reason of at least %d characters"
                            % (path, MINIMUM_REASON))
        return hits
    version = _version(root)
    if "CHANGELOG.md" in paths and version is not None and version < FIRST_FRAGMENT_RELEASE:
        return hits
    hits.append("changelog: this branch changes %s but adds no fragment; add %s/<issue-or-pr>.<%s>.md, "
                "or %s/<issue-or-pr>.%s.md saying in at least %d characters why no entry is needed"
                % (touched[0] + (" and %d more" % (len(touched) - 1) if len(touched) > 1 else ""),
                   DIRECTORY, "|".join(KINDS), DIRECTORY, WAIVER, MINIMUM_REASON))
    return hits
