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

Then run `python3 bin/harness integration check bmad .`. Planning workflows run from the shared checkout;
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

## Spawn confinement is enforced, not requested

The override templates ask each review layer to run itself through `harness role run`. That is a
request in a prompt: a client that paraphrases the brief and names no role used to walk past a
spawn guard that only read the name the model wrote (#291).

So the framework declares itself, in `policy/integrations/bmad.json`, and the spawn hook
classifies against that descriptor instead. A descriptor names the framework, the release it was
read from, the layer-to-role mapping, the input roots a confined worker needs, and how a spawn is
recognised:

- **agents** — the spawn's `subagent_type` is one of the framework's own layer names. Nothing else
  puts that name there, so it is enough on its own.
- **identifiers** — a literal only the framework's routed text carries, such as the path of one of
  its prompt files. Never enough alone, because a brief that edits the override templates quotes
  the same path; an identifier counts only with a phrase beside it.
- **phrases** — whole sentences of the framework's own prompt text. One is a coincidence;
  `corroboration` of them, two by default, is not.

Generic nouns are not phrases. "unified diff" and "list of findings" are what the ordinary fix-up
brief after a review says, and a descriptor that declared them would refuse the work the review
asked for. The loader enforces that: a signal below the minimum length and word count, an
identifier that is an input root or a bare directory under one, a spawn with no phrases at all, or
a role the spawn guard would not constrain, and the descriptor is refused as a whole. A descriptor
that will not parse or will not validate is announced once per session and recorded in the
decision log, never dropped in silence.

A recognised spawn is refused with the same isolated-worker instruction a named role's spawn gets,
and the refusal names the framework, the layer and the input roots the worker has to be given as
read roots. Unlike a refusal the spawn declared by role name or `harness-role:` line, it is not
written into the session's memory of refused work: that memory matches later briefs by prefix and
similarity, so one wrong classification would go on refusing the corrected brief for the rest of
the session. Each spawn is answered on its own evidence.

The `harness-role:` line the templates carry is an optimisation on top: it is read by the marker
guard, which requires it on a line of its own, and a descriptor must not restate it as loose text.

Another framework becomes a tenant by adding its own descriptor file; nothing in the hook is
BMad-specific. Keep `version.pinned` equal to the release the repository installs — a mapping read
from another release names layers that are not there.

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

Run `harness integration check bmad <framework-root>` before
`harness integration apply bmad <framework-root>`; `harness bmad check|apply` is kept as an alias
for both. The command reads `policy/integrations/bmad.json` for the template directory, the
install destination and the skill surface, so the CLI names no framework of its own.
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
without their compatibility shims fail `harness integration check bmad`. Re-run your recorded, version-pinned
installation command with `--shims`, retaining the same modules, tools and module pins. Back up
the installation first, restore any documented runtime patches and artifact-routing YAMLs,
then check both skill projections and verify that existing customizations are unchanged.
Keep `--shims` in the recorded reinstall command while these workflows require the legacy names.
This repairs dependency discovery; a passing check still does not qualify workflow execution.

## The optional integration suite

This framework's own workflow is not run in a release qualification round. `required_cases` carries
the generic `framework-spawn-routing` case instead, which drives the spawn hook against a fixture
recipe and costs one cheap turn; what it proves and what it does not is in
[compatibility](compatibility.md).

What stays in CI is cheap and offline: `tests/test_bmad_templates.py` and
`tests/test_bmad_repository.py` pin the upstream surface against a fixture repository with no
framework installed, and they are what actually catches a renamed key or layer id.

The native run is an optional suite, non-gating, run once per minor release on one target before
the tag:

```sh
BMAD_VERSION=6.12.0
npx --yes bmad-method@"$BMAD_VERSION" install --directory <framework-root> --modules bmm \
  --tools claude-code,codex --output-folder _bmad-output --shims --yes
python3 bin/harness integration apply bmad <framework-root>
# then run the four-layer code review from the shared checkout against an assigned worktree,
# and confirm each layer ran as an isolated worker rather than a native subagent.
```

Record the result in the release's pull request with the harness version, the framework version and
the client it ran on. It gates nothing: a red result is an issue, not a blocked release, and the
release claim says only that the pinned version is the one that was observed.
