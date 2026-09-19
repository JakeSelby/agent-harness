# agent-harness

A user-aligned, model-provider-agnostic harness with shared custom primitives and switchable
personal stances. `bin/harness` projects one policy authority into Claude Code and Codex. The global
rules an agent runs under in this repo come from the harness itself, so this file carries only
what is true of this repository.

## Commands

```sh
bin/harness lint                          # personal strings and secret patterns; must be clean
python3 -m unittest discover tests        # merge, link, config, lint logic
bin/harness sync --dry-run                # what a sync would do from this checkout
bin/harness doctor                        # versions, logins, links, drift
```

**Expected clean-tree output:** `lint: 0 finding(s) in …` and `OK` from unittest with no
skipped tests. Tests run under the system Python 3.9 and under a current Python; keep the
code free of syntax newer than 3.9.

## Gate

```sh
python3 bin/harness lint
python3 -m unittest discover -s tests
```

The `stop-gate` hook runs this block when the tree has changed since its last green run,
blocks the turn while it is red, and releases after eight consecutive blocks. It runs only
once this checkout is trusted: accept Claude Code's folder dialog or run `bin/harness trust .`.

## BMad planning

BMad Method 6.12.0 with BMM, Claude Code and Codex projections, and compatibility shims is the
repository's public planning system. Its authored corpus stays in `_bmad-output`; do not redirect
it to another repository. The complete pinned install command and version-control boundary are in
`docs/bmad.md`. Run planning workflows from the shared checkout and implementation from a managed
worktree.

## How the checkout is used

- **This checkout is live.** `harness sync` symlinks `claude/rules`, each `claude/skills/*`,
  `claude/hooks` and the output style into `~/.claude`. An edit here is in effect in the next
  session with no further step; a half-finished rule is live too. Work in a worktree branched
  off `main`, so the live checkout only ever carries merged content.
- **Every change lands through a pull request.** The `main` ruleset requires green `lint` and
  `test` checks on an up-to-date branch and a squash merge; there is no direct push.
- **One delivery issue per PR, one PR per delivery issue.** Create or select a dedicated issue
  before changing files, including docs. Add `Closes #N` to the PR. Split separately delivered
  work into child issues; contextual references do not establish ownership. Reuse is allowed
  only when a previous PR was closed without merging. The `issue-ownership` check enforces
  current GitHub closing links; verify ownership again immediately before merging.
- **Code changes** (`bin/harness`, `claude/hooks/*.py`, `tests/`) carry a test with every
  change. Content changes (rules, stances, skill text, docs) are gated by the lint and review.
- Nothing personal, nothing project-specific, nothing copyleft. The lint enforces the first;
  review enforces the rest.

## Layout

- `primitives/` — the shared authoring authority. `policy/` — shared lifecycle policy.
- `adapters/` — runtime bindings; `compatibility/` — native qualification evidence and status.
- `claude/` — compatibility projections and native settings; what gets linked into `~/.claude`: `CLAUDE.md`, `rules/`, `stances/`, `skills/`,
  `hooks/`, `output-styles/`, plus `settings.template.json` and `OWNERSHIP.json`.
- `bin/harness` — the CLI. `tests/` — its unit tests.
- `vscode/`, `codex/`, `templates/repo/` — the other surfaces the harness manages.
- `docs/` — how it works; the only place project provenance names are allowed.

## `AGENTS.md` and `CLAUDE.md` are one file

`CLAUDE.md` is a symlink to this file. Edit `AGENTS.md`.
