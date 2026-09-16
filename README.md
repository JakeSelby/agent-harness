# agent-harness

[![CI](https://github.com/JakeSelby/agent-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/JakeSelby/agent-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

An installable harness for Claude Code: the rules, preference stances, skills, hooks, output
style and settings that make a coding agent **legible** (you can read what it did without
scrolling), **predictable** (it delegates, verifies and asks the same way every time), and
**reviewable** (a plan fits on one screen and ends with numbered decisions). It also sets up
VS Code and Codex to match, and it keeps itself honest: the git checkout *is* the live
configuration, so every change is a commit.

It grew out of one person's daily setup. Everything personal was stripped, everything
opinionated became a switch, and the result is meant to be forked, compared with, and argued
about.

## Install in sixty seconds

```sh
git clone https://github.com/JakeSelby/agent-harness.git ~/repos/agent-harness
cd ~/repos/agent-harness
bin/harness install          # Homebrew packages, VS Code + extensions, Claude Code, Codex, gh, then sync
```

Or, if the tools are already installed, just link the harness in:

```sh
bin/harness sync --adopt     # --adopt moves any pre-existing ~/.claude files aside (recorded, reversible)
```

Then edit `~/.config/agent-harness/config.json` (your name, your stances), run `bin/harness sync`
again, and start a session. `/context` lists the harness rules; `/hooks` lists its eight hooks.
An agent can do all of this from this README; the CLI is Python 3.9 standard library and
every step is idempotent.

`bin/harness doctor` reports versions, logins, links and drift. `bin/harness usage` summarizes
per-session tokens and cache hit rate from a local file ([docs/usage.md](docs/usage.md)).
`bin/harness uninstall` puts everything back.

## What you get

| Layer | What it does | Where |
| --- | --- | --- |
| **Rules** (10) | Behaviour on every turn: read narrowly, never reprint subagent output, verdict first, verify before claiming, no secrets in tracked files. Operative lines only — with `CLAUDE.md` and the selected stances they are capped at 200 lines, enforced by the lint | `claude/rules/` |
| **Stances** (8, 23 variants) | Preferences a reasonable engineer might hold the other way: licensing, commit style, plan ceremony, delegation tiers, testing, autonomy, build-vs-buy, cost | `claude/stances/` |
| **Skills** (13) | Procedures loaded on demand, carrying the reasoning the rules point at: one-screen plan authoring, delegation tiering, transcript hygiene, API verification, design loop with an independent judge, licensing review, migration safety, sandboxing an unattended loop, upstream contribution, worktree per agent, spike contract, harness authoring, workflow status | `claude/skills/` |
| **Agents** (7) | Subagent definitions carrying their model, effort level and tool list, so the delegation tiers hold without a retyped brief: `builder` implements one issue in a worktree and commits without pushing, `design-judge` scores a render against the rubric, `gatherer` gathers read-only, `log-compressor` reduces a run to its failures, `planner` writes the plan file, `reviewer` reviews a diff in a fresh context, `spec-reviewer` checks that diff against what was asked for | `claude/agents/` |
| **Commands** (5) | The ritual in five keystrokes: `/research` fans out read-only gatherers for one digest, `/plan` writes the Review Card and stops at the build gate, `/build` implements in a worktree and opens the PR, `/review` makes two fresh-context passes over the diff, scope then quality, `/handoff` writes the progress file the next session reads | `claude/commands/` |
| **Hooks** (8) | Enforced, not advised: a plan-card validator, a read-only command classifier so plan mode stops prompting, a plan-mode web-research approver, an output filter, a tool-output scanner, a session-start drift, override and handoff check, a stop gate that runs the repo's own gate, a usage logger | `claude/hooks/` |
| **Output style** | Scannable: verdict first, registers separated, action items in one place | `claude/output-styles/` |
| **Settings** | Only the keys the harness owns, merged into yours: hooks, a read-only allowlist, the output style | `claude/settings.template.json` |
| **VS Code, Codex** | Owned editor keys and the extension list; a generated `AGENTS.md` and owned config keys for Codex | `vscode/`, `codex/` |
| **Repo starter** | What a repository needs so agents work well in it, given the global rules already load | `templates/repo/` |

## How it works

```
your checkout ──symlinks──▶ ~/.claude/{CLAUDE.md, rules/harness, rules/harness-stances, skills/*, hooks/harness, output-styles}
             ──merge─────▶ ~/.claude/settings.json          (owned keys only)
             ──render────▶ ~/.claude/CLAUDE.personal.md      (from config.json; yours, untracked)
             ──merge─────▶ VS Code user settings             (owned keys only)
             ──generate──▶ ~/.codex/AGENTS.md               (rules + chosen stances + your personal file)
```

Claude Code reads rule and CLAUDE.md text literally, with no variable substitution, so the
harness personalises three ways and never by editing tracked files: identity is rendered into
an untracked personal file, preferences are variants chosen at sync, and per-session
`HARNESS_*` environment overrides are injected by a SessionStart hook. The layer diagram, the
sync model and the ownership contract are in [docs/](docs/):

- [how-it-works.md](docs/how-it-works.md) — the layers and why each exists
- [sync-model.md](docs/sync-model.md) — links, adoption, the settings merge, other surfaces
- [settings-ownership.md](docs/settings-ownership.md) — exactly which keys the harness may write
- [preferences.md](docs/preferences.md) — identity, stances, posture, env overrides
- [sandboxing.md](docs/sandboxing.md) — fencing an unattended loop, and why sync writes no key
- [workspaces.md](docs/workspaces.md) — multi-root workspaces and session stores
- [bmad.md](docs/bmad.md) — keeping a planning framework out of the way
- [comparison.md](docs/comparison.md) — what to compare against other harnesses
- [provenance.md](docs/provenance.md) — where the ideas came from

## The dogfood loop

Because the live paths are symlinks, an edit in the checkout is in effect in the next session
with no further step. `bin/harness diff` reports the other direction: a setting changed through
the tool's own UI shows as *live-only* so it can be brought back into the repo, and a template
change not yet applied shows as *pending sync*. The `harness-authoring` skill takes any "add a
rule that…" or "remember this" request, decides which layer it belongs to, writes it under the
checkout, runs the lint and the sync, and commits. Nothing harness-owned is ever edited under
`~/.claude/` by hand.

## Preferences and overrides

```json
{
  "identity": { "name": "…", "pronouns": "…", "role": "…", "github": "…", "timezone": "…" },
  "stances": { "licensing": "permissive-commercial", "commits": "conventional-attributed",
               "plan-ceremony": "review-card", "delegation": "tiered", "testing": "required",
               "autonomy": "execute", "build-vs-buy": "capability-ceiling", "cost": "balanced" },
  "permissions": "inherit"
}
```

`HARNESS_STANCE_TESTING=off claude` flips one stance for one session. `permissions` is the one
setting-level knob: `inherit`, `bypass`, `auto` or `manual`, applied to Claude Code, VS Code and
Codex together. Full list in [docs/preferences.md](docs/preferences.md).

## What is deliberately not here

Anything about one person (rendered from config instead), anything about one project (that is
the project's `AGENTS.md`), credentials or MCP server configurations, and any planning
framework's files. The lint refuses personal-data shapes, home-directory paths and secret
patterns in every file with none exempt, reads your own terms from an untracked file, and runs
in CI and in a pre-commit hook. It deliberately contains no list of real values.

## Contributing

Ideas are as welcome as patches. If a rule, stance or skill here made your agent better or
worse, open an [Idea issue](../../issues/new?template=02-idea.yml) or start a
[Discussion](../../discussions) and say what happened. If you have a fix, fork the repo, branch
on your fork, and open a pull request against `main`; CI runs the lint and the tests, and every
PR gets a review. Anything bigger than a typo is faster after a short thread first.
[CONTRIBUTING.md](CONTRIBUTING.md) has the flow, the checks, and the ladder that decides where a
change lands.

## License

MIT, see [LICENSE](LICENSE). Third-party notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). If this harness shapes yours, a link back is
appreciated; it is not required.
