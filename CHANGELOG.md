# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- The `stop-gate` hook runs a repository's `## Gate` block only in a folder whose trust dialog
  has been accepted in Claude Code, or whose root is listed by the new `harness trust <path>`
  command, so a freshly cloned repository can no longer run commands on the first Stop. Until
  then it skips with a note on stderr.

## [0.2.0] — 2026-09-16

### Added

- `permissions.deny` rules in the settings template for credential files and generated
  directories, so the file tools and the Bash commands that read files are both covered.
- Three subagent definitions — `gatherer`, `reviewer` and `log-compressor` — carrying their
  model, effort level and tool list, so the delegation tiers hold without a retyped brief.
- A `sandbox` stance and skill: container or built-in sandbox posture for an unattended loop.
- A `filter-output` PreToolUse hook that pipes a test, build, lint or type-check run through a
  line filter, keeping failures, summaries and the tail while preserving the exit status.
- A `cost` stance with `frugal`, `balanced` and `max` variants, and a `cache-hygiene` rule.
- A `neutralize` PostToolUse hook that flags instruction-shaped text in `Bash`, `WebFetch` and
  `Read` output, advisory only, never blocking or rewriting a result.
- A `stop-gate` Stop hook that runs the fenced `## Gate` block of a repository's `AGENTS.md`
  and refuses to end the turn while it is red, bounded by a block count and a time budget.
- Four slash commands — `/research`, `/plan`, `/build` and `/review` — each composing skills
  the harness already ships.
- A `usage-log` SessionEnd hook and `harness usage`, reporting per-session tokens and cache hit
  rate from a local file; see `docs/usage.md`.
- A `/handoff` command that writes `.claude/progress.md` and promotes durable learnings into a
  dated file under `docs/solutions/`, and a SessionStart hook that reads that progress file and
  the last five commits back as context. The progress file is added to the global git ignore.
- A `builder` agent carrying the standing implementation brief — a worktree of its own, tests
  with every change, the repository's gate, one local Conventional Commit and no push — so
  `/build` spawns it and verifies the gate itself instead of retyping the steps.
- A `spec-reviewer` agent that reports scope deviations only, and a two-stage `/review` that runs
  it before the quality `reviewer`, each in a context that has not seen the other's findings.
- A `planner` agent carrying the Review Card contract, so `/plan` can hand the file-writing to a
  fresh context and keep its own for the review conversation.
- A `design-judge` agent carrying the design loop's scored critique and its hard gates, so the
  independent judge is a fixed definition the skill names rather than a rubric pasted each round.

### Fixed

- The agent sync tests restore the environment they change, so a later test in the same run is
  no longer affected by them.

### Changed

- Always-loaded context (`claude/CLAUDE.md`, every rule, and the longest variant of each stance) is
  capped at 200 lines and `harness lint` fails with a per-group breakdown when it is exceeded. The
  rules keep their operative lines and point at the skill holding the reasoning; the rationale,
  examples and evidence moved verbatim into `delegation-tiering`, `plan-authoring`,
  `harness-authoring`, the new `transcript-hygiene` and `api-verification` skills,
  `docs/how-it-works.md` and `docs/preferences.md`. 583 lines before, 185 after.

## [0.1.1] — 2026-09-16

The repository was re-created with a fresh history for this release. The 0.1.0 tag and its
history are gone: the lint in that release embedded a denylist of the maintainer's own
identifiers, which is a disclosure of the very values it existed to catch.

### Changed

- The lint carries no list of real values. It matches personal-data shapes (12-digit account
  ids, email addresses, home-directory paths, cloud ARNs, hosted-zone ids, identity-provider
  tenants, private IPs) and secret patterns everywhere in the tree with no file exempt, derives
  the maintainer's name from `LICENSE` and `CODEOWNERS`, and reads personal terms from the
  untracked `~/.config/agent-harness/lint-terms.txt` (see `lint-terms.example.txt`).
- `harness lint --staged` and a `.githooks/pre-commit` hook, installed by `harness sync`, lint
  every commit in the checkout before it is made.
- `permissions: bypass` is refused unless `permissions_bypass_acknowledged` is `true` in the
  config file, and is documented as unsuitable for any machine that touches regulated data.
- Test fixtures assemble identifier-shaped strings at run time, so the tests are linted like
  everything else; a regression test asserts no file in the tree carries an identifier shape.

## [0.1.0] — 2026-09-16 (withdrawn)

### Added

- Nine core rules, seven stances with twenty variants, ten skills, three hooks and the
  Scannable output style, extracted from a working harness and rewritten in second person.
- `bin/harness` with `install`, `sync`, `diff`, `doctor`, `uninstall`, `lint`, `workspace
  create` and `config get`; standard library only.
- Symlink-based live sync into `~/.claude`, ownership-scoped settings merge, identity rendered
  from `~/.config/agent-harness/config.json`, per-session `HARNESS_*` overrides.
- VS Code owned settings and extension lists; generated Codex `AGENTS.md`; repo starter
  templates.
- Community files, issue and PR templates, CI with lint and tests, Dependabot for actions.

[Unreleased]: https://github.com/JakeSelby/agent-harness/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.2.0
[0.1.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.1.1
