# Coordinate a harness release and its public surfaces

A release is a verified source tag plus reference and personal-site deployments identifying that
release. A successful build is not native qualification. `scripts/release_preflight.py` refuses
publication until every required client in the compatibility catalog carries native evidence.
Every release follows the [compatibility policy](compatibility-policy.md); generated notes link it
and state the migration review or exact versioned migration action.

## When a release is proposed, and what it is numbered

Releases are cut by milestone. Every issue meant for the next release carries the `v<next>`
milestone, work merges freely, and a release is proposed when that milestone empties or when a
user-visible unreleased change is seven days old, whichever comes first. A regression fix does not
wait for either: it releases at once as a patch.

The number follows what changed, not where the entry landed in the changelog. Fixes only is a
patch. Added or changed user-visible behaviour is a minor. A major is decided by the
[compatibility policy](compatibility-policy.md), which also defines what counts as a breaking
change. What the release must carry before it can be tagged is the next section.

## Source and qualification

1. Complete each native acceptance case in [compatibility](compatibility.md). Keep exact runtime,
   client and platform versions, source commit, observations and evidence digests. Resolve failed
   controls or record a deliberately narrower support contract before calling a client qualified.
2. Merge reviewed changes through the repository's PR gate. Keep stacked PR bases current without
   overwriting other contributors' history. Preserve personal configuration and the live checkout.
3. Set `VERSION`, `compatibility/catalog.json` and `compatibility/migration.json` to the same
   release. Record exact migration actions and recovery even when the only action is reviewing a
   dry run. Regenerate projections and release notes. Run the CI commands and the Python floor suite
   on committed HEAD; then run:

   ```sh
   python3 scripts/release_preflight.py
   python3 scripts/release_notes.py
   ```

   The preflight also compares the GitHub About panel with `product.json` and looks up every
   `on_the_way` entry that names an issue; an entry whose issue has closed blocks the release
   until it is promoted or removed. Both read GitHub through `gh`, so both run only behind a
   `gh auth status` probe. Without an authenticated `gh` the preflight prints
   `release warning: About and On-the-way checks skipped, gh is not authenticated` and does not
   fail, which is what happens in the tag workflow: its preflight step is passed no token by
   design, so those two checks are expected to warn there and must be run locally before tagging.
   A `gh` call that fails after the probe passed is a blocked release, not a skip.

   Refresh the static context figure for the new version with
   `python3 scripts/cost_bench.py static --write` and commit it; see [benchmarks](benchmarks.md).

   Before freezing the candidate, run `python3 scripts/lifecycle_acceptance.py` under every Python
   and reference operating system named by the candidate record. The runner uses disposable homes,
   verifies the immutable v0.9.0 archive pin, and covers clean install, repeated sync, upgrade,
   rollback, conflicts and uninstall. Store its JSON output with the candidate evidence. This is a
   filesystem/configuration lifecycle check; it does not qualify a native client.

4. Tag the verified commit with the matching immutable `v<version>` tag and push that tag.
   The release workflow repeats qualification and source gates before publishing. Never move an
   existing tag to repair a failed release; fix the source and use a new version.
5. The workflow's `advance-stable` job, which cannot fail the run, fast-forwards the `stable`
   branch to the tag's commit, so `stable` is always the latest release while `main` is the trunk.
   Nothing else pushes to `stable`, and it never moves backward. Confirm it, and repair it from a
   checkout that has the tag if it is stale:

   ```sh
   python3 scripts/advance_stable.py --check
   python3 scripts/advance_stable.py
   ```

   GitHub refuses a workflow token that moves a branch across a change to `.github/workflows/`,
   so a release that edits a workflow can need the second command run by hand.
6. Close the released milestone and open the next one. This is a hand-run step rather than a
   workflow job, so that a published release never depends on it. Read the milestone numbers,
   close the released one, and create the next if it does not exist:

   ```sh
   gh api repos/{owner}/{repo}/milestones \
     --jq '.[] | "\(.number) \(.title) open:\(.open_issues)"'
   gh api -X PATCH repos/{owner}/{repo}/milestones/<number> -f state=closed
   gh api repos/{owner}/{repo}/milestones -f title=v<next> -f state=open
   ```

   Move any issue still open on the closed milestone to the new one first, so the closed
   milestone records what the release actually carried.

## Freeze the qualification branch

Cut `release/v<version>` at the commit the round qualifies and record it in
`compatibility/freeze.json` as `state: frozen` with that branch and full commit, then run every
target on that branch so `main` keeps merging without invalidating evidence. `harness freeze`
prints the drift between the frozen commit and `origin/main` under the runtime source paths —
`VERSION`, `bin`, `lib`, `adapters`, `primitives`, `policy`, `templates`, `config.example.json` —
and `harness freeze --merge-check <ref>` refuses a merge into the frozen branch that changes any of
them, because such a change costs part of the round again. How much of it is scoped per target: a
change under one runtime's adapter directory invalidates only that runtime's targets, unless it
touches a file shared code reads for every runtime, and a change to shared source invalidates them
all. The carve-out and its limits are in [compatibility](compatibility.md).
Return `state` to `open` after the tag. The evidence commit must stay an ancestor of the
qualification source commit, which `evidence_errors` enforces, so a diverged release branch fails
closed rather than publishing an unqualified source.

**Fix no defect mid-round.** A round runs all four required targets to completion and collects
their defects; a fix landed between targets invalidates the targets already observed and forces a
re-run of each. Land the collected fixes together on `main` afterwards, cut a new freeze commit,
and re-qualify once.

## Reference and personal site

7. The reference site vendors this repository by tag and repins itself hourly through its own
   workflow, so a release needs no hand repin. Confirm the repin run, the deploy job that followed
   it, and that the live `/manifest.json` names both the version and the source commit. A skipped
   deployment job is not a deployment; record the workflow run and distribution identity. When the
   repin has to be made by hand, pin `vendor/agent-harness` to that exact tag, commit the gitlink,
   run the site's CI commands (`npm ci`, `npm test`, `npm run build`, `node scripts/smoke.mjs`),
   and from the harness checkout run
   `python3 scripts/release_preflight.py --reference-repo <reference-checkout>`.
8. The personal-site card links the latest release rather than naming a version, so a release needs
   no card change. Confirm both placements still resolve. The shared card links to reference
   compatibility facts and does not maintain its own inventory count or version claim.
9. Set GitHub About description, topics and homepage from `product.json` (see below).
   Verify production HTML, SEO/social metadata, compatibility statuses, search results, deep links,
   install instructions, the exact release manifest and both personal-site card placements.
   Record HTTP statuses and rendered inspection results; mark any unavailable check unverified.

## GitHub About

`product.json` is the source of the landing copy, the README grid and the About panel.
`scripts/sync_about.py` compares its `github_description` and `topics` with
`gh repo view --json description,repositoryTopics,homepageUrl`, treating topics as a set because
GitHub returns them in its own order. A `homepage` key in `product.json` is compared too; while
the file names none, the live homepage URL is left alone.

```sh
python3 scripts/sync_about.py --check    # names each differing field, exits non-zero on drift
python3 scripts/sync_about.py --apply    # writes them through `gh repo edit`
```

Run both locally. `--apply` changes the repository's public metadata, so it needs the owner's
approval on each run, and it cannot be moved into the release workflow: editing repository
settings needs administration access, which is not among the permission scopes available to the
workflow's `GITHUB_TOKEN` ([workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)).
The `--check` side of it runs inside `scripts/release_preflight.py`, which warns rather than fails
when `gh` is unauthenticated.

`scripts/sync_about.py --apply` writes whatever `product.json` the *current checkout* holds. Run it
only from a worktree fast-forwarded to `origin/main` (`bin/harness worktree create main-sync <repo>`,
then `git merge --ff-only origin/main`); a stale checkout once reverted the About panel.

## Rollback

Keep the previous harness tag, both site commits, reference gitlink and deployed artifact identity
before publishing. A regression gets a revert PR and a new harness release; do not retarget the
old tag, and leave `stable` where it is until that release advances it. Restore the reference
site's previous immutable pin and deploy its rebuilt artifact;
restore the personal site's previous card commit through its normal pipeline. Reconcile local
configuration through its ownership journal, preserving conflicts and adopted backups. Verify
live pages and release identity again. Infrastructure rollback is separate and must not be inferred
from a static-content rollback.

## Release status

The 0.12.0 release ships without native qualification. No client carries evidence for this
source and none is marked required for release, which is what lets the preflight publish it;
0.11.1 remains the last release qualifying Claude Code CLI and Codex CLI on macOS and Linux.
The narrowed contract was taken deliberately for a pre-1.0 release, and the required flags
return with the next qualification round. The VS Code surfaces and Codex Desktop are
unqualified previews. The architecture-viewer
integration is also a preview for a separately installed implementation, with no bundled viewer
or distribution-clearance claim. The release is identified by the exact commit carrying the
immutable `v0.12.0` tag. Reference and
personal-site deployment status remains independently verifiable; never infer a deployment from
a source merge or bypass the release preflight.
