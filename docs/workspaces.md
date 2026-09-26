# Workspaces

This page covers multi-root workspaces: which repositories belong together, how a session is
launched across them, and Claude Code's per-workspace session store. It does not merge Codex
native history or memory. Use [shared task continuation](task-continuation.md) to carry work between runtimes.

Nothing in the harness needs to be the root of a workspace. Everything installs at user level
and loads in every session.

## What the first folder decides

- **Project settings** (`.claude/settings.json`) load from the first folder, the session's
  working directory, only.
- **Instructions** (`CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/`) load from the first folder.
  A later folder, which Claude Code receives as `--add-dir`, contributes its `.claude/skills/`,
  `.claude/commands/` and `.claude/agents/`, and its instructions too only when
  `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` is set in the environment. Claude Code never
  loads an `AGENTS.md` from an added folder, and Codex loads only its own working directory's.
- **Session history and auto memory** are keyed by the first folder's path under
  `~/.claude/projects/`.

So pick as first the repo whose project configuration you want, and never reorder a
workspace's folders casually: the session store would appear to vanish.

## The workspace map

Point `workspaces_dir` at the folder that holds your `.code-workspace` files:

```sh
citizen config set workspaces_dir ~/path/to/workspaces
```

Those files are then the only definition of which folders belong together. Nothing else is
stored: every command reads them again, so editing a file in VS Code is the whole change. A
workspace's name is its file stem, and its members are its `folders[].path` entries in order,
resolved against the file's own folder. Comments and trailing commas are accepted, as VS Code
accepts them; a `uri`-only folder is skipped, and a folder that no longer exists is reported and
left out. With the key absent the feature is off everywhere; remove it from
`~/.config/agent-harness/config.json` to turn it off again.

A session belongs to the member folder that contains its working directory, the longest match
winning, and a linked git worktree counts as its main checkout. When that folder is in more than
one workspace, the first rule that decides wins:

1. `HARNESS_WORKSPACE` names one of them; `workspace open` sets it.
2. Exactly one of them has, as its other members, the folders the session was launched with as
   `--add-dir`, which is how a VS Code window reveals the workspace it opened.
3. The overrides file names the folder.
4. The folder is in only one workspace.
5. The folder is the first member of exactly one of them.

Otherwise nothing is attached and the candidates are listed.

### The overrides file

An optional `overrides.json` beside the workspace files pins a shared folder to one workspace,
or with `null` to none, which opts the folder out entirely. Folder paths resolve against
`workspaces_dir`, and comments are accepted:

```jsonc
{
  "~/repos/shared-lib": "billing",   // shared-lib is in three workspaces; use this one
  "../scratch": null                 // never attach a workspace here
}
```

An override naming a workspace that does not exist, or one that does not contain the folder, is
ignored, and `workspace list` reports it. The file is edited by hand.

## `citizen workspace list`

Prints each workspace with its members in order, each marked with the characters of instructions
it carries (`CLAUDE.md`, else `AGENTS.md`, plus `CLAUDE.local.md`, unscoped `.claude/rules/` and
their `@` imports) or `missing`. Then every folder in more than one workspace, with the workspace
it resolves to and the rule that decided, or its candidates; then ignored overrides and any file
that could not be read. With `workspaces_dir` unset it says how to set it and exits 1.

## `citizen workspace open`

```sh
citizen workspace open NAME [--codex] [--dry-run] [-- ARGS...]
```

Launches Claude Code in the workspace's first existing folder with every other existing folder as
`--add-dir`, and `HARNESS_WORKSPACE=NAME` in its environment. Arguments after `--` go to the
runtime, before the `--add-dir` flags: Claude's `--add-dir` takes several folders, so a prompt
placed after it would be read as one more folder.

- `--codex` launches `codex -C <first> --add-dir <each other>` instead.
- `--dry-run` prints the `cd` and the command, with the environment variable, and runs nothing.

For the added folders' `CLAUDE.md` files to load, set
`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` in your environment.

## One store per workspace

`citizen workspace create <name> <folder…>` writes `<name>.code-workspace` with the folders in
the order given (first is root) and the harness checkout appended as a non-root folder unless
`--no-harness`. It then creates `~/.claude/workspaces/<name>/` and symlinks each folder's
project key under `~/.claude/projects/` to that store, so the same history and memory follow
the workspace whichever folder happens to be first.

If a project key already holds real history, the command leaves it alone and says so. To merge
by hand: move the existing key aside, create the symlink, copy the old contents into the store
without overwriting (`rsync --ignore-existing`), then delete the moved-aside copy. Undo is
removing the symlink and moving the directory back.

## Adding the harness checkout to an existing workspace

Optional, for editing convenience only. Add it as a later folder. Its skills live under
`claude/skills/`, not `.claude/skills/`, so it adds none as an added folder; its `CLAUDE.md`,
which is its `AGENTS.md`, loads there only with the environment variable above set.
