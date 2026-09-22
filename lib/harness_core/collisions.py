"""Duplicate skill, agent and command names across primitive roots.

A runtime resolves two definitions of one name silently, first-wins, with no warning: the
loser is simply never loaded, and nothing in a transcript says which one ran. Two sibling
installs projecting the same skill into `~/.claude/skills/` is the shape this repository has
already been bitten by (`docs/bmad.md`), so the names are collected across every root a
configuration registers and a duplicate is refused before sync writes anything.

wshobson/agents ships `tools/check_agent_name_collisions.py` against the same problem; this
check is written for the harness's own roots and kinds rather than adapted from it.

A project-level `.claude/agents/*.md` or `.claude/skills/<name>/` is not a collision: a project
definition legitimately outranks a user-level one. It is reported as a shadow instead, so the
precedence is visible rather than discovered.
"""
from pathlib import Path

# The kind each caller sees, and the primitives directory it is authored in.
KINDS = (("skill", "skills"), ("agent", "roles"), ("command", "workflows"))


def roots(root, config):
    """The primitive roots to search: the built-in one, then the configured ones, in order."""
    found = [Path(root) / "primitives"]
    entries = config.get("primitive_roots") if isinstance(config, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            path = Path(entry).expanduser()
            if path.is_absolute():
                found.append(path)
    return found


def _display(path, root):
    """A path as a reader can place it: relative inside the checkout, absolute outside it."""
    try:
        return str(Path(path).relative_to(Path(root)))
    except ValueError:
        return str(path)


def _sources(directory, kind):
    """Every definition of one kind in one directory, as (name, path), sorted by name."""
    if not directory.is_dir():
        return []
    if kind == "skill":
        return sorted((child.name, child / "SKILL.md") for child in directory.iterdir()
                      if child.is_dir() and (child / "SKILL.md").is_file())
    return sorted((path.stem, path) for path in directory.glob("*.md") if path.is_file())


def names(root, config):
    """Every defined name, as {kind: {name: [display paths, in root order]}}."""
    found = {kind: {} for kind, _ in KINDS}
    for source in roots(root, config):
        for kind, directory in KINDS:
            for name, path in _sources(source / directory, kind):
                found[kind].setdefault(name, []).append(_display(path, root))
    return found


def collisions(root, config):
    """Names defined more than once, as (name, kind, [paths]), sorted for a stable report."""
    found = names(root, config)
    return sorted(((name, kind, paths) for kind, _ in KINDS
                   for name, paths in found[kind].items() if len(paths) > 1),
                  key=lambda item: (item[1], item[0]))


def findings(root, config):
    """One line per collision, naming every source, plus what to do about it."""
    lines = ["collision: " + kind + " '" + name + "' is defined in " + " and ".join(paths)
             for name, kind, paths in collisions(root, config)]
    if lines:
        lines.append("collision: a runtime resolves a duplicate name silently, first-wins; rename one "
                     "of them or unregister the primitive root that carries it")
    return lines


def shadows(root, config, project):
    """Project definitions that outrank a user-level name, as one warning line each.

    Not a failure: a project's own `.claude/` is how a repository overrides the user's harness,
    and saying which name it takes over is the whole remedy.
    """
    if project is None:
        return []
    claude = Path(project) / ".claude"
    found = names(root, config)
    lines = []
    for kind, directory in (("skill", "skills"), ("agent", "agents")):
        for name, path in _sources(claude / directory, kind):
            if name in found[kind]:
                lines.append("shadowed: project " + kind + " '" + name + "' at " + str(path) +
                             " outranks the user-level definition in " + found[kind][name][0])
    return sorted(lines)
