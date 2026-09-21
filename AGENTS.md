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
  before changing files, including docs — file it with `scripts/bmad_issue_sync.py new`, or
  `reserve` an existing one, because `issue-ownership` also fails a PR whose issue has no BMad ID
  in `_bmad-output/issue-map.json`. Add `Closes #N` to the PR. Split separately delivered
  work into child issues; contextual references do not establish ownership. Reuse is allowed
  only when a previous PR was closed without merging. The `issue-ownership` check enforces
  current GitHub closing links; verify ownership again immediately before merging.
- **Code changes** (`bin/harness`, `claude/hooks/*.py`, `tests/`) carry a test with every
  change. Content changes (rules, stances, skill text, docs) are gated by the lint and review.
- Nothing personal, nothing project-specific, nothing copyleft. The lint enforces the first;
  review enforces the rest.

## Issues, milestones and releases

- **Every issue carries one `type::*` label**, and the `v<next>` milestone when it is meant for the
  next release. Create that milestone when the first issue is filed against it.
- **A pull request that adds or changes a user-visible capability updates `product.json` in the
  same pull request**: a new feature line, or an `on_the_way` entry promoted into `capabilities`.
  That file is the one source of the landing copy, the README grid and the GitHub About
  description. Planned work worth advertising goes in `on_the_way`, capped at five entries, and
  each entry names the issue, planned client or document it stands for.
- **Releases are cut by milestone.** Merge freely; propose a release when the milestone empties or
  when a user-visible unreleased change is seven days old. A regression fix releases at once as a
  patch.
- **Number by what changed**, not by where it landed in the changelog: fixes only is a patch;
  added or changed user-visible behaviour is a minor; `docs/compatibility-policy.md` decides a
  major. What a release must carry before it is tagged is the "Source and qualification" section
  of `docs/releasing.md`, which also holds the milestone close-and-open commands.
- **After every merge run `/land`**, and after every tag work the seven surfaces below.

## A release is not done at the tag

A release has seven surfaces, and each one goes stale on its own. Work them in this order and
report each as done, skipped or unverified — never infer one from another. The procedure, the
commands and the rollback are in `docs/releasing.md`; this list exists so none is forgotten.

1. **Source and evidence** — every fix merged; native qualification and lifecycle records for the
   frozen commit in `compatibility/evidence/`, the catalog `qualified` with digests and limitations.
2. **Release metadata** — catalog `released` and pinned, the changelog's Unreleased entries folded
   into the version section, status prose in `README.md`, `docs/compatibility.md` and
   `docs/releasing.md`.
3. **Tag and GitHub release** — `scripts/release_preflight.py` clean in a fresh clone, then the
   annotated `v<version>` tag; confirm the release workflow ran, the release is published and
   `scripts/advance_stable.py --check` finds `stable` at the tag.
4. **Reference site** — verify only. A separate repository vendors this one by tag and repins
   itself hourly through its own workflow. Confirm the repin run, the deploy job that followed it,
   and that the live `/manifest.json` names the version and the commit.
5. **Personal-site card** — verify only. The card links the latest release rather than naming a
   version, so a release needs no card change. Confirm both placements still resolve.
6. **GitHub About** — description, topics and homepage must equal `product.json`. Run
   `python3 scripts/sync_about.py --check` every release even when nothing changed, and say so.
7. **Development resumes** — the first runtime-source change after a release makes the catalog
   report drift by design; the next version needs a candidate opened before it can be qualified.

No step here deploys by hand: steps 4 and 5 verify deployments the other repositories run
themselves. Step 6 with `--apply` changes public repository metadata, so it needs its own
explicit approval each time it is run.

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
