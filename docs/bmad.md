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

## Shared roles and explicit installation

`templates/bmad/custom/` names harness roles: `builder`, `reviewer`, and `spec-reviewer`.
The active runtime adapter supplies their native registration, model and effort. Recipes retain
complete keyed review-layer records so BMad's replacement merge does not discard required fields.
The assigned implementation worktree, framework checkout, artifact root, baseline commit and
review diff must be separate explicit inputs; run framework scripts from the framework checkout.

Run `harness bmad check <framework-root>` before `harness bmad apply <framework-root>`.
Check resolves either `.agents/skills` or `.claude/skills`, refuses conflicting mirrors, and
parses customization TOML structurally. It also compares mirrored Markdown/TOML sources and
checks literal `Invoke via the … skill` dependencies in installed workflows; other forms of dynamic
skill routing still require workflow acceptance. Apply writes only declared keys and existing layer ids;
it preserves differing user overrides unless you explicitly pass `--force`. Session start only
checks. It never silently installs configuration.

BMad uses two entry mechanisms: build skills render `workflow.md`, while code review resolves
the `workflow` customization block with `resolve_customization.py`. A missing `workflow.md` in a
resolver-based skill is not an installation defect. Test the entry mechanism its `SKILL.md` names.

The inspected BMad 6.12.0 renderer supports `--project-root` and `--skill`. Do not invent an
`--overrides` or `--set` flag from newer documentation. Use its `_bmad/custom/` seam. Renderer
patches and absent GDS review shims are integration findings, not reasons to reinstall a framework
inside an implementation worktree. Missing review skills must be restored through the framework's
supported shim installation or an upstream fix before that workflow is qualified.

## Continue a task in either runtime

The shared human-readable snapshot is `.agent-harness/progress.md`; session start reads the old
`.claude/progress.md` only when the shared file is absent. Plans live in `.agent-harness/plans/`.
Native transcripts and memory stay in their own runtime stores.

For a structured handoff, prepare a JSON file:

```json
{
  "objective": "Complete the selected change",
  "next_steps": ["Inspect the current diff", "Run the repository gate"],
  "decisions": ["Keep the public API stable"],
  "artifacts": ["docs/design.md"],
  "framework_root": "/path/to/shared-checkout",
  "baseline": "the-reviewed-base-commit"
}
```

```sh
harness task show
harness task save --input task-input.json --runtime claude-code --revision 0
# In Codex, from the same worktree:
harness task show
harness task save --input task-input.json --runtime codex --revision 1
```

The revision rejects concurrent stale writers. Repository identity and a content fingerprint
prevent a changed tree from inheriting a verification claim. Shared plans and progress count as
inputs even when ignored by Git; only task bookkeeping is excluded. Reported verification is retained
as unverified evidence; the receiving session runs the gate itself. Next steps are data, never
executed by the loader, and approvals never transfer. Storage rejects symlinks. Keep personal
handoff data out of commits with a project ignore entry when needed.
