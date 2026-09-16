# Using a planning framework alongside the harness

The harness is framework-agnostic. This page records a pattern that keeps a self-hosted
planning framework (the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD), MIT)
installed in a code repo without polluting it, and without the harness redistributing any of
the framework's files.

## The pattern

- **Install into the repo, commit only your overrides.** `.gitignore` carries
  `/_bmad/*`, `!/_bmad/custom/`, `/.claude/skills/`, `/.agents/skills/`. The runtime and the
  skill projections are installer-regenerable; only `_bmad/custom/` is yours.
- **Redirect artifacts to a planning repo.** In `_bmad/custom/config.toml`, point
  `planning_artifacts`, `implementation_artifacts`, `project_knowledge` and `output_folder` at
  a separate repository using `{project-root}`-relative or absolute paths, so a design corpus
  of hundreds of files never lands in the code repo (or in every worktree of it).
- **Pin the install.** One command, with versions, in the repo's `AGENTS.md`, for example
  `npx bmad-method@<version> install --directory <repo> --modules <list> --tools claude-code,codex --yes`.
- **Record post-install repairs in one place.** Anything you patch in the installed runtime
  must be re-applied after every reinstall; list each patch at the bottom of
  `_bmad/custom/config.toml` with the date and the reason, and file it upstream so it can
  disappear.
- **Run it from the shared checkout only.** The framework resolves its scripts against the
  working directory; a worktree has no `_bmad/scripts/`, halts, and that halt is the intended
  guard. Do implementation work in worktrees; run planning skills from the checkout.
- **Keep sibling installs at the same version.** Two repos in one workspace both project
  skills into `.claude/skills/`; a name clash resolves silently, first wins. While the copies
  are byte-identical it is harmless; the moment they drift, one version's skill calls the
  other's scripts.
- **Post-sprint hygiene.** Update the architecture document's status, the decisions ledger and
  the changelog before moving on; the framework will not do it for you.
- **Nothing framework-shaped in team-facing output.** No attribution footers, no `_bmad/`
  paths, no story references in anything shipped to a shared repo.

## Why the harness does not ship framework extensions

Almost every customisation in practice is a path redirect or a project persona. The portable
part is this pattern. Redistributing modified copies of a framework that ships new versions
weekly would turn every upstream release into harness maintenance, and it would make the
harness harder to compare with others on the things that matter: legibility, delegation, the
plan gate, permission posture.
