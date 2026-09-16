# Workspaces

Nothing in the harness needs to be the root of a workspace. Everything installs at user level
and loads in every session. This page is about multi-root VS Code workspaces in general,
because Claude Code keys two things off the workspace's **first** folder.

## What the first folder decides

- **Project-level configuration** (`.claude/settings.json`, `.claude/skills/`, `CLAUDE.md`)
  loads from the first folder. Later folders contribute only `.claude/skills/`,
  `.claude/commands/` and `.claude/agents/`.
- **Session history and auto memory** are keyed by the first folder's path under
  `~/.claude/projects/`.

So pick as first the repo whose project configuration you want, and never reorder a
workspace's folders casually: the session store would appear to vanish.

## One store per workspace

`harness workspace create <name> <folder…>` writes `<name>.code-workspace` with the folders in
the order given (first is root) and the harness checkout appended as a non-root folder unless
`--no-harness`. It then creates `~/.claude/workspaces/<name>/` and symlinks each folder's
project key under `~/.claude/projects/` to that store, so the same history and memory follow
the workspace whichever folder happens to be first.

If a project key already holds real history, the command leaves it alone and says so. To merge
by hand: move the existing key aside, create the symlink, copy the old contents into the store
without overwriting (`rsync --ignore-existing`), then delete the moved-aside copy. Undo is
removing the symlink and moving the directory back.

## Adding the harness checkout to an existing workspace

Optional, for editing convenience only. Add it as a later folder. It contributes nothing to
load order (its skills live under `claude/skills/`, not `.claude/skills/`), and its own
`AGENTS.md` loads only when you open the harness repo by itself.
