# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.10.0] — 2026-09-19

### Added

- Add the shared architecture-viewer profile, lifecycle and external process adapter. The preview
  works with a separately installed protocol 1 viewer and does not bundle or publish that viewer.
- Add bidirectional BMad-to-GitHub issue traceability, deterministic mapping audits and safe
  fallbacks for repositories that cannot project every native issue type or hierarchy.
- Add a versioned compatibility and migration contract, lifecycle acceptance runner and immutable
  release-source pinning.

### Changed

- Qualify the Claude Code and Codex CLIs on macOS and Linux with version-pinned native evidence.
  Keep the VS Code surfaces and Codex Desktop as unqualified previews; keep Cursor and Grok planned.
- Preserve released qualification evidence until runtime source changes, then fail the release
  check rather than silently changing a published support claim.

## [0.9.0] — 2026-09-19

### Provider-agnostic harness

- Lead with your working style, extensible custom primitives and switchable personal stances.
- Keep one shared authority for rules, stances, skills, roles, workflows and presentation;
  project it through Claude Code and Codex adapters.
- Add safe native configuration ownership, structural TOML updates, recovery journals, custom
  homes, drift diagnostics and conflict-preserving uninstall.
- Compose lifecycle policies, strengthen gate invalidation, and normalize usage observations
  while preserving unknown metrics and detector failures.
- Add custom stance authoring, semantic BMad roles and versioned bidirectional task handoffs.
- Add a native compatibility catalog and release gate. Claude Code and Codex are qualified on the
  required CLI, VS Code and desktop surfaces; Cursor and Grok, hosted agents, native memory merging
  and the UML viewer are deferred.
- Coordinate reference-site and personal-site positioning around the same user-aligned primitive
  model and immutable release identity.

### Changed

- Require a dedicated delivery issue for every PR, with a CI ownership check rejecting missing,
  multiple, foreign and reused closing issues. Document replacement PRs and the cross-PR race limit.

- User-authored drafts now defer to an untracked personal voice profile before applying the
  selected reply-layout stance, and the harness documents where that profile belongs. Accidental
  typos are explicitly excluded from imitation.

## [0.8.0] — 2026-09-17

### Added

- `docs/getting-started.md`: zero to a first useful session for someone who has not used a coding
  agent before. What the harness is and is not, the prerequisites as a table with a way to check
  each, install, `init`, a first session with three things to actually type, what changed about the
  answers, the five commands with which of them need a code project, what a session costs, and the
  three commands that diagnose a broken install. The README links it above the install block and
  from the docs list; `SUPPORT.md` now opens with it and says plainly that everything else there
  needs a GitHub account and is public. (#82)

- A **Before you start** block on the README's first screen: a Claude account on a plan that
  includes Claude Code — stated, rather than discovered after `install` has already run — the
  supported platforms, `git` and Python 3.9, and which of the rest are optional. (#82)

- A **What a session costs** section in `docs/preferences.md`, naming the rate-limit window, the
  commands that fan out, and the `cost` stance as the dial. Nothing previously said that a
  `/research` run costs several times a plain turn. (#82)

- `identity.expertise`, `expert` or `beginner`, selecting one paragraph of the personal file. The
  line telling the agent to communicate at expert level and skip fundamentals was hardcoded in
  `CLAUDE.personal.template.md` and reached every user, including one who had never written code —
  instructing the agent to withhold exactly the explanation they needed. `expert` is the default,
  so a config predating the field resolves to the behaviour it had. (#83)

- Stance presets, asked by `init`: `software` is the shipped defaults, `general` turns off the
  commit, test, licensing and build-vs-buy ceremony and lightens plans, for work that is not
  shipping software. Escaping the professional-SDLC defaults previously meant discovering five
  separate opt-outs. A preset only supplies the defaults for the questions that follow, so every
  stance is still asked. `delegation`, `autonomy` and `cost` are untouched by either: how work is
  spread, how far it runs unattended and what it costs are the same questions whatever the work
  is. (#83)

- A `voice` stance dimension, closing the last always-loaded rule that was a pure preference (#68).
  `scannable` defers to the output style as before and is the default, so nothing changes for an
  existing install. `answer-card` is for reading on a phone: the answer in the first line, then why,
  the catch, and the alternatives, about 150 words, no tables, with the reasoning left in the file
  it links rather than re-argued in the message. `off` imposes no shape at all. The two `voice/`
  detectors are gated on the dimension, so a voice nobody selected is not measured as a violation.

### Changed

- The three rules written entirely about code work say so in their headings — `verification`,
  `secrets` and `conciseness` — and one line of the always-loaded preamble states that a rule
  about repositories, tests or pull requests does not apply elsewhere. Rules link as a directory
  rather than per file, so they cannot be deselected; the fix is for them to read as inapplicable
  instead of as instructions about work the reader is not doing. Length-neutral apart from that
  one line. (#83)

- `voice-and-format.md` drops from thirteen lines to six, keeping only what no variant changes:
  a subagent inherits no voice, so its brief has to carry the output shape itself. Always-loaded
  context moves 193 to 195 of the 196-line budget.

- A `decisions/no-alternatives` detector, and `decisions-and-plans` leaves `OPT_OUT`. The rule
  asks for "the alternatives with their honest case", and nothing measured whether a decision
  block carried one: the opt-out reasoned from the Review Card and the chooser, and left the
  clause that does the work unobserved. The detector fires on a final message whose batched
  `Decisions` block or recommendation line names no other course, reading the markers out of the
  raw text so an alternative named inside a quote still counts. A recommendation in running prose is not a
  decision block and does not fire. (#78)

- `harness init`: a first-run wizard that writes `config.json` by asking for identity one field
  at a time and offering each stance's variants with the default in brackets, so configuring the
  harness no longer means hand-editing JSON. It detects the timezone from `/etc/localtime` and the
  GitHub handle from `gh` when it is logged in, refuses to clobber an existing config without
  `--force`, and names `config set` when there is no terminal to ask in. (#81)

- `harness config set KEY VALUE`, which validates before it writes: an unknown stance variant,
  stance, identity field, permission posture or top-level key is refused with the options named,
  rather than being written and failing at the next sync. (#81)

- `sync` and `doctor` report identity fields still carrying the example file's value. `load_config`
  backfills from `config.example.json` and `render_personal` writes the result into always-loaded
  context, so an unedited config had the agent address you as the placeholder name with nothing on
  screen to say so. Reported, never fatal: a dry-run sync against the example config still
  succeeds. (#81)

### Fixed

- `install` and `sync` refuse to run on Windows and name WSL2, rather than half-working: the
  harness links into `~/.claude` with symlinks and every hook is a POSIX command. Nothing in the
  README or the docs had ever said which platforms are supported. `_run` also treats an absolute
  path that does not exist as a missing tool, so `/bin/bash` being absent reports rather than
  raises. (#82)

- `doctor` now reports whether each registered hook can actually run, instead of printing an
  executable bit that never mattered. It resolves the interpreter and the script path of every
  hook command in the live settings and names what is missing. Claude Code treats a hook that
  fails to start as non-blocking, so a machine without `python3` on PATH, or an install that was
  never synced, turned all eleven hooks into silent no-ops — the command grader that asks before
  something irreversible and the stop gate that runs the repository's checks among them. Both
  guards disappeared with nothing on screen to say so. (#85)

- The two hook messages a user actually sees are written for a reader now. The grade-bash denial
  said "No prompt exists in this mode" and told them to re-run with a marker; it now says the
  command was refused because nothing can prompt, and what to say before running it again. Every
  grade carries its meaning in words — "this cannot be undone" — alongside the label. The stop
  gate says where the failing command came from, and the untrusted-folder notice names the command
  that fixes it. (#85)

- The four commands that assume a git repository now check for one before they start, and name a
  fallback instead of stopping dead. `/build` says up front that it needs a repository, a remote
  and `gh`, offers to make the change in place when there is no repository, and stops at the local
  commit when there is no remote — rather than failing at `gh pr create` with the work already
  done. `/review` says there is no diff to review outside a repository, before it spawns either
  pass, and offers named files or a pasted patch. `/plan` and `/handoff` write beside the work in
  the current directory when there is no repository root, and `/plan` now says outright that it
  needs neither a repository nor code. (#84)

- `bin/harness install` no longer ends in a traceback on a machine that lacks `gh` or `npm`.
  `subprocess.run` raises `FileNotFoundError` when argv[0] does not exist and `check=False`
  suppresses only a non-zero exit, so the unguarded `gh auth status` at the end of every install
  and the `npm install -g @openai/codex` step both crashed rather than reported — reachable with
  `--no-brew` on macOS and on every Linux run. Every external call now goes through one helper
  that resolves the executable first, names it when it is missing, and carries on. The lookup also
  searches the keg-only `node@22` bin directory, which Homebrew does not link into its prefix, so
  `npm` is found after a plain `brew install` on a machine with no other node. (#80)

## [0.7.0] — 2026-09-17

### Added

- A `code-quality-instruments` skill: branch coverage over line coverage, mutation score as the
  only instrument here that measures assertions rather than execution, complexity joined to
  coverage to rank the risky functions, and duplication as a refactor signal that is never a gate.
  Carries per-language instruments for Python, TypeScript, Rust and Go, and the operating rules
  that keep them usable: mutate the diff rather than the tree, run one instrument at a time, bound
  the workers. The `testing: required` variant gains a one-line pointer, which is the whole
  always-loaded cost. Adapted from `unclebob/swarm-forge`, whose engineering article pins real
  instruments per language where our stance only asked that tests exist. (#73)

- An eleventh hook, `brief-guard`: PreToolUse on `Agent`, it appends a 400-word return bound to
  a subagent brief that states none, rather than asking the orchestrator to write one.
  `transcript-hygiene/brief-without-cap` fired 536 times across 30 percent of sessions, so the
  prose was not working. What counts as a bound and which agents are exempt are imported from
  `rule-detectors.py` rather than copied, and a test asserts the appended text satisfies the
  detector, since a bound the detector cannot see would never move the number. Adapted from
  `unclebob/swarm-forge`, whose handoff helper fills the commit SHA so the agent never types
  one. No-op under `delegation: off`, where `tier-agent-spawns` already gates the spawn. (#72)

- A `commit-msg` hook in `templates/repo/hooks/`, installed per repository, refusing a subject
  that is not a Conventional Commit. It reads the `commits` stance and does nothing under `off`
  or `as-you-go`; under `conventional-attributed` it also warns on a missing `Co-Authored-By:`
  trailer, which it cannot add because the model name is session state a git hook cannot see.
  Adapted from `unclebob/swarm-forge`, which appends its byline the same way. A git hook was the
  right surface because it sees the final message however it was written, where the
  `commits/non-conventional` detector parses only `-m` and undercounts. (#71)

## [0.6.1] — 2026-09-17

### Fixed

- The instruction to gather with subagents unasked no longer loads under every stance. It sat in
  `claude/CLAUDE.md` and `claude/rules/delegation.md`, both always-loaded, and contradicted the
  `delegation: off` variant outright, so the selection did not decide the behaviour it named. It
  now lives in the `tiered` and `session-model` variants that mean it, and a regression test
  asserts that no always-loaded file carries one. Always-loaded context drops from 195 to 192
  lines. (#67)

### Changed

- The README, `docs/how-it-works.md` and `docs/preferences.md` say which layer is switchable and
  which is the floor, name the test a stance has to pass, and list the rules that do not pass it
  yet instead of leaving them implicit. (#67, #68)

## [0.6.0] — 2026-09-17

### Added

- A rule-detector registry (`claude/hooks/rule-detectors.py`): fourteen deterministic
  detectors over a session transcript, one or more per always-loaded rule, with an explicit
  opt-out list for the three rules nothing in a transcript can decide. `harness lint` now fails
  on a rule with neither, and reads its secret patterns from the same module. (#58)
- A tenth hook, `grade-bash`: every Bash command is graded 0–3 on the read-only grammar's
  decomposition (read-only, local, remote-mutating, irreversible) and the autonomy stance sets
  the gate: `execute` on grade 3, `confirm-writes` on 2 and up, `ask` on 1 and up. Prompting
  modes get `ask` with a one-line reason; `auto` and `bypassPermissions`, where a hook's `ask`
  is ignored, get `deny` with the same reason and a chat-confirmed re-run prefixed
  `HARNESS_CONFIRMED=1`. (#60)
- The session-end worker runs the detector registry and records `rules`, `counts` and `stances`
  per session; `harness usage --rules [--by rule|repo|stance]` reports hits, sessions and share per
  detector, marks `promote?` above 30 percent of at least 20 sessions and `unobserved` at zero over
  at least 20, and `--rescan` backfills from existing transcripts. (#59)

### Changed

- The README leads with the positioning line; the docs explain command grades, the ask-versus-deny
  split per permission mode with the hooks-reference quotes, and rule telemetry as the signal for
  pruning the always-loaded rules. (#61)

## [0.5.1] — 2026-09-16

### Changed

- Provenance credits a year of coding agents, most of it in Cursor and the last two months in
  Claude Code, rather than a year in `~/.claude`.
- The README and the comparison no longer claim the read-only hook is what stops plan mode
  prompting: Claude Code's own classifier does that by default in auto mode. The hook's value
  is deterministic, no-round-trip approval that also covers Manual mode and API, Bedrock and
  Vertex sessions.

## [0.5.0] — 2026-09-16

### Added

- A `tier-agent-spawns` hook (`PreToolUse` on `Agent`) applies the `delegation` stance to every
  subagent spawn that names no agent definition and no model, which is what a planning
  framework's or a plugin's "launch a subagent" produces: one tier below the session under
  `tiered`, untouched under `session-model`, a prompt under `off`. Frontmatter and explicit
  model choices are left alone. Inside a repository that carries a framework runtime
  (`_bmad/scripts/` or `_bmad/core/`), a bare spawn keeps the session model: the framework's
  lenses are judgment work its overrides cannot rename, and its own rule is same capability.
- `templates/bmad/custom/` carries override files in BMad's own format for `bmad-build`,
  `bmad-build-auto` and `bmad-code-review` that run their review layers as the `reviewer` and
  `spec-reviewer` agents and the implementation handoff on the builder's tier. `harness bmad
  apply` installs them into a repository's `_bmad/custom/`, skipping a template whose keys or
  layer ids the installed skill no longer declares, and `harness bmad check` reports that drift.
  The `harness-session` hook runs `apply` for the repository a session starts in and says so
  once when it wrote, kept or skipped a file.
- `docs/bmad.md` records how the two pieces keep the delegation stance in charge of a
  framework's spawns, and why the implementation handoff is not routed to `builder`.

## [0.4.1] — 2026-09-16

### Security

- The `readonly-bash` hook approved any command placed after a `#` comment and a newline: the
  lines were joined with `;` before tokenizing, so shlex's comment handling swallowed the rest
  and only the benign prefix was judged. Each line now loses its own comment first and a `#`
  inside a word stays part of the word, as in bash. Found by an independent review of 0.4.0.

### Fixed

- A bare `date MMDDhhmm` operand, which sets the system clock, falls through to the prompt.
- `harness uninstall` removes the PATH line it added to `~/.zprofile` and the ignore block it
  added to `~/.config/git/ignore`, leaving every other line in place.

### Changed

- CI runs `harness sync --dry-run` against the example config, as CONTRIBUTING said it did.
- The README points at `--help` for the full command surface and names `config get`;
  `docs/preferences.md` documents the `vscode.manage` and `codex.manage` keys.

## [0.4.0] — 2026-09-16

### Added

- `harness trust <path>` records a repository root whose `## Gate` block the stop gate may
  run, and `--remove` forgets it; the list lives in `~/.config/agent-harness/trusted.txt`.

### Security

- The `stop-gate` hook runs a repository's `## Gate` block only in a folder whose trust dialog
  has been accepted in Claude Code, or whose root is listed by the new `harness trust <path>`
  command, so a freshly cloned repository can no longer run commands on the first Stop. Until
  then it skips with a note on stderr.
- The `session` hook frames the handoff file it injects at session start as repository
  content on both sides, to be treated as data rather than instruction, the way the
  `neutralize` hook frames tool output.

### Fixed

- The `readonly-bash` hook approved several commands that write or execute: a second command
  after a newline, `awk` scripts calling `system()` or redirecting output, `env` with a program
  argument, `fd -x`, `rg --pre`, `sed -n` scripts using `w` or `e`, `sort -o`, `tree -o`,
  `yq -i`, `git grep --open-files-in-pager`, a `PATH=` or `GIT_*=` prefix, any binary run by
  absolute path with a read-only name, and the `>|`, `&>>`, `>&` and `<>` redirections. Each now
  falls through to the permission prompt. `tests/test_allow_readonly_bash.py` pins the corpus.
- The settings template no longer carries the allow rules that granted the same primitives
  without the hook: `Bash(awk *)`, `Bash(sort *)`, `Bash(sed -n *)`, `Bash(fd *)`, `Bash(rg *)`,
  `Bash(tree *)`, `Bash(file *)`, `Bash(date *)` and the leading-wildcard `Bash(* --version)`.
  The hook approves the safe invocations of every one of them.

### Changed

- `harness sync` removes an allow rule that an earlier template added and the current one has
  dropped, while still keeping rules the user added themselves.

## [0.3.0] — 2026-09-16

### Added

- A `plan-webfetch` PreToolUse hook that approves `WebFetch` while in plan mode, for
  `http`/`https` URLs only, so gathering context for a plan no longer prompts for every
  documentation URL. Every other permission mode is unchanged, and the `neutralize` hook still
  scans the fetched text (#37).

### Changed

- The `readonly-bash` hook now decomposes compound commands — `;`/`&&`/pipelines,
  `for`/`while`/`until`/`if` blocks, subshell `( )` and group `{ }`, and command substitutions
  `$(...)`, backticks and `<(...)` — and approves the whole only when every command inside is
  read-only, so plan mode stops prompting for read-only loops and substitutions. A write
  anywhere still falls through, and a reserved word used as an argument, such as `grep -q done`,
  is treated as data rather than syntax (#37).

## [0.2.0] — 2026-09-16

### Added

- `permissions.deny` rules in the settings template for credential files and generated
  directories, so the file tools and the Bash commands that read files are both covered.
- Three subagent definitions — `gatherer`, `reviewer` and `log-compressor` — carrying their
  model, effort level and tool list, so the delegation tiers hold without a retyped brief.
- A `sandbox` skill: container or built-in sandbox posture for an unattended loop.
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

[Unreleased]: https://github.com/JakeSelby/agent-harness/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.8.0
[0.7.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.7.0
[0.6.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.6.1
[0.6.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.6.0
[0.5.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.5.1
[0.5.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.5.0
[0.4.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.4.1
[0.4.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.4.0
[0.3.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.3.0
[0.2.0]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.2.0
[0.1.1]: https://github.com/JakeSelby/agent-harness/releases/tag/v0.1.1
