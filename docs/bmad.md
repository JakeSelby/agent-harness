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

## Keeping the delegation stance in charge

A framework's skills spawn subagents by saying so in prose: "launch a context-free subagent
with this prompt". In Claude Code that is an `Agent` call with no `subagent_type` and no
`model`, so it runs as `general-purpose`, on the session model, with every tool, and the
frontmatter that carries the harness's tiers never applies. Two pieces close that, and neither
copies a framework file.

- **The `tier-agent-spawns` hook** runs on every `Agent` call. A call that names an agent
  definition or passes a model is left alone; a bare one gets the `delegation` stance: one tier
  below the session under `tiered`, untouched under `session-model`, a prompt under `off`. The
  session model is read from the transcript's newest assistant record, so a spawn in the very
  first assistant turn of a session is left alone. Inside a repository that carries the
  framework's runtime (`_bmad/scripts/`), a bare spawn keeps the session model instead: the
  framework's finalize reviewers, validators and lenses launch from step logic or prompt-only
  lists that no override can rename, and its own rule is same capability. The second piece
  names the harness's agents where the recipe allows, which is what carries tools and effort.
- **Override templates** under `templates/bmad/custom/` use the framework's own customization
  contract to name the harness's agents where the framework's spawns are judgment work: the
  review layers of `bmad-build`, `bmad-build-auto` and `bmad-code-review` run as `reviewer`, the
  acceptance and intent layers as `spec-reviewer`, and the implementation handoff on the
  builder's tier. `harness bmad apply <repo>` installs them into `_bmad/custom/` as user
  overrides: the framework keeps them across reinstalls and its own `.gitignore` keeps them
  out of the repo, so run it once per clone that runs the framework, or rename a file to
  `<skill>.toml` to commit it for a team whose members all run the harness. An existing
  override is never replaced without `--force`.
- **`harness bmad check <repo>`** compares every key and layer id the templates rely on with the
  installed skill's `customize.toml`. The framework's renderer drops a key it does not declare
  and appends an unknown layer id beside the renamed original, so after an upgrade this is the
  command that says whether the routing still holds.

Research fan-outs (`bmad-deep-recon`) have no template: their researchers are bare spawns and
keep the session model like every other bare spawn in a framework repo; the skill's own
`subagent_models` knob is the place to make them cheaper. Routing the implementation handoff
to the `builder` agent was considered and rejected: the framework's review step diffs the tree
it ran in against `baseline_commit`, so the implementer has to work in place, the pinned
handoff already carries the builder's tier, and what `builder` adds (isolation, one commit,
the repo gate) the framework does itself later in the run.

## What the harness ships for a framework, and what it does not

Almost every customisation in practice is a path redirect, a project persona, or a spawn
routing. The portable part is the pattern above and the override templates, which are files of
your own in the framework's override format, not modified copies of its files. Redistributing a
framework that ships new versions weekly would turn every upstream release into harness
maintenance, and it would make the harness harder to compare with others on the things that
matter: legibility, delegation, the plan gate, permission posture. The templates carry a check
instead of a copy: when a release renames a key, `harness bmad check` says so.
