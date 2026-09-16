# agent-harness

An installable Claude Code harness: rules, stances, skills, hooks, an output style, and the
`bin/harness` CLI that links them into `~/.claude` and keeps settings in step. The global
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

## How the checkout is used

- **This checkout is live.** `harness sync` symlinks `claude/rules`, each `claude/skills/*`,
  `claude/hooks` and the output style into `~/.claude`. An edit here is in effect in the next
  session with no further step; a half-finished rule is live too. Work on `main` for content;
  use a worktree and a PR for code.
- **Content changes** (rules, stances, skill text, docs) commit straight to `main` and push.
- **Code changes** (`bin/harness`, `claude/hooks/*.py`, `tests/`) go through a PR so CI gates
  them; every code change carries a test.
- Nothing personal, nothing project-specific, nothing copyleft. The lint enforces the first;
  review enforces the rest.

## Layout

- `claude/` — what gets linked into `~/.claude`: `CLAUDE.md`, `rules/`, `stances/`, `skills/`,
  `hooks/`, `output-styles/`, plus `settings.template.json` and `OWNERSHIP.json`.
- `bin/harness` — the CLI. `tests/` — its unit tests.
- `vscode/`, `codex/`, `templates/repo/` — the other surfaces the harness manages.
- `docs/` — how it works; the only place project provenance names are allowed.

## `AGENTS.md` and `CLAUDE.md` are one file

`CLAUDE.md` is a symlink to this file. Edit `AGENTS.md`.
