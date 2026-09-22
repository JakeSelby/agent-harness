# BMad in agent-harness and downstream repositories

The harness is framework-agnostic. This page records a pattern that keeps a self-hosted
planning framework (the [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD), MIT)
installed in a code repo without polluting it, and without the harness redistributing any of
the framework's files. Agent Harness itself follows the same runtime boundary but deliberately
publishes its authored BMad corpus in this repository.

## This repository's public planning system

Agent Harness pins BMad Method 6.12.0 with the `bmm` module, Claude Code and Codex projections,
and compatibility shims. Reproduce the local apparatus from the shared checkout:

```sh
BMAD_VERSION=6.12.0
npx --yes bmad-method@"$BMAD_VERSION" install --directory . --modules bmm \
  --tools claude-code,codex --user-name Jake --communication-language English \
  --document-output-language English --output-folder _bmad-output --shims --yes
```

Then run `python3 bin/harness bmad check .`. Planning workflows run from the shared checkout;
implementation still happens in managed worktrees.

The version-control boundary is intentional:

### Commit

- `_bmad/custom/**`: repository configuration, workflow customizations, templates and policy
  extensions.
- `_bmad-output/planning-artifacts/**`: product brief, PRD, developer journey, architecture,
  epics, decisions, source ledger and readiness reports.
- `_bmad-output/implementation-artifacts/**`: stories, public sprint state, retrospectives and
  clearly marked historical reconstructions.
- The pinned install instructions, repository-owned validation/synchronization code and deliberate
  test fixtures.

### Do not commit

- The installed `_bmad` runtime outside `_bmad/custom`.
- Generated `.agents/skills`, `.claude/skills` or `.github/agents` projections.
- Installer caches, temporary renderings, local backups, logs or session state.
- Raw conversations, memory exports or source-ingestion dumps.
- Secrets, private absolute paths, machine-specific configuration or unsanitized personal data.

Every published artifact must be authored or intentionally reconstructed, sanitized, and useful
to a public contributor. `_bmad/custom/config.user.toml` and every `*.user.toml` remain local.
A clean reinstall and customization resolution must leave tracked files unchanged.

## GitHub traceability

GitHub owns scope, discussion, delivery state and acceptance evidence. BMad supplies immutable typed
IDs and public artifacts. `_bmad-output/issue-map.json` records each mapping, primary parent and next
ID; `_bmad-output/implementation-artifacts/AH-*.md` links back to the issue. A generated Planning
block in the issue links to the artifact on `main`.

```sh
python3 scripts/bmad_issue_sync.py audit
python3 scripts/bmad_issue_sync.py plan
python3 scripts/bmad_issue_sync.py apply
```

`audit` is local and non-mutating. `plan` compares the manifest with live GitHub state. `apply`
refuses to run until every artifact exists on `main`, then idempotently maintains the Planning block,
exact `type::*` label and primary parent. It never changes a title, state or comment. GitHub native
issue types are [organization-managed](https://docs.github.com/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization)
and cannot be assigned in this personal-account repository, so the manifest records `labels-only`
projection explicitly rather than reporting permanent false drift.
File maintainer work already mapped, from the worktree that will deliver it, and reserve an ID
for a community issue during triage before implementation ownership:

```sh
python3 scripts/bmad_issue_sync.py new --title TITLE --kind story --body-file BODY.md --parent PARENT_NUMBER
python3 scripts/bmad_issue_sync.py reserve --issue N --kind story --parent PARENT_NUMBER
```

Both write the map and a new artifact in the current checkout; commit them in the pull request that
delivers the issue. The required `issue-ownership` check refuses a pull request whose delivery
issue is absent from the map, and `apply` adds the Planning block once the artifact is on `main`.

Because `next_ids` lives in the map, it knows only what this checkout has seen. Before allocating,
both commands survey every issue map this clone can reach — the working copy of each linked
worktree, so an uncommitted reservation counts, and every local and remote-tracking branch — and
refuse when the counter is not past every ID of that kind already in use, naming each one and where
it was found. Rebasing onto the branch that took them is the usual answer; `--advance` skips them
instead and says which IDs it leaves permanently unused. Heads `git ls-remote` advertises that this
clone holds no object for are reported, so an incomplete survey is never read as a clean one.

### Live verification

```sh
python3 scripts/bmad_issue_sync.py audit --live
python3 scripts/bmad_issue_sync.py refresh
```

`audit --live` is read-only. It fails when a mapped issue's title or open/closed state differs from
the manifest, when a mapped issue is missing or lacks its Planning block, label or parent, and when
an issue a maintainer has accepted — filed by a maintainer, or carrying a milestone or a `type::*`
label — has no BMad ID. A community issue still waiting for triage is a notice, not a finding, and
so is an unmapped issue closed as not planned or as a duplicate.

The manifest owns the primary parent and `apply` projects it, so `audit --live` never tells you to
apply a parent GitHub already records: it reports a mapped parent the manifest lacks as `run
refresh`, an unmapped one as `run reserve for it first`, and a parent that differs on both sides as
a conflict for you to settle.

`refresh` copies GitHub's title and state into the manifest and its generated artifacts, and adopts
a mapped parent the manifest records as none. It checks
every drifted artifact before writing any of them and refuses the whole run when one carries
amendments; it never touches GitHub, and it leaves an issue GitHub no longer returns for the audit
to report as missing.

Run the full live audit before a release and after any triage pass. The `bmad traceability`
workflow runs it daily, on issue events and when the map changes, with `--ignore-lifecycle` and
`--grace-days 2`: an issue closes before its map entry can follow it through a pull request, and a
new issue gets two days to receive its ID. That workflow is not a required check.

IDs are never reused and never encode hierarchy. Reparent the metadata rather than renaming the ID.
Completed historical issues are marked `reconstructed`; the record never claims those artifacts
existed during the original delivery.

## The pattern

- **Install into the repo, commit only your overrides.** `.gitignore` carries
  `/_bmad/*`, `!/_bmad/custom/`, `/.claude/skills/`, `/.agents/skills/`. The runtime and the
  skill projections are installer-regenerable; only `_bmad/custom/` is yours.
- **Choose the artifact authority explicitly.** In `_bmad/custom/config.toml`, point
  `planning_artifacts`, `implementation_artifacts`, `project_knowledge` and `output_folder` at
  the intended repository using `{project-root}`-relative paths. A separate planning repository
  can keep a very large private corpus out of every worktree; public projects such as agent-harness
  can instead commit a sanitized local corpus.
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
- **Keep delivery output native.** Do not add generated attribution footers or internal runtime
  paths to ordinary issues and PRs. Public documentation and planning artifacts may identify BMad
  deliberately, and issues may link to their public story artifacts.

## Shared roles and explicit installation

`templates/bmad/custom/` names harness roles: `builder`, `reviewer`, and `spec-reviewer`.
The active runtime adapter supplies their model and effort; the framework's own skill text does
not, and the spawn hook tiers a framework repository like any other.

A framework spawn that names one of those roles is priced from that role's row in the active cost
variant. A framework spawn that names no role at all — the "launch a subagent" a step file writes,
which no override template reaches — is routed to the variant's default band worker and priced
from that band's row instead, so its class, effort and soft budget come from the posture rather
than from the recipe. Nothing in the framework's own templates changes. Constrained review roles use
`harness role run` with explicit input roots; builders retain their normal
workflow. See [isolated role workers](role-workers.md). Recipes retain
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

BMad 6.12.0 provides `--shims` on its installer. GDS v0.7.2 still invokes the legacy
`bmad-review-adversarial-general` and `bmad-review-edge-case-hunter` names; installations
without their compatibility shims fail `harness bmad check`. Re-run your recorded, version-pinned
installation command with `--shims`, retaining the same modules, tools and module pins. Back up
the installation first, restore any documented runtime patches and artifact-routing YAMLs,
then check both skill projections and verify that existing customizations are unchanged.
Keep `--shims` in the recorded reinstall command while these workflows require the legacy names.
This repairs dependency discovery; a passing check still does not qualify workflow execution.

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
