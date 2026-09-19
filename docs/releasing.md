# Coordinate a harness release and its public surfaces

A release is a verified source tag plus reference and personal-site deployments identifying that
release. A successful build is not native qualification. `scripts/release_preflight.py` refuses
publication until every required client in the compatibility catalog carries native evidence.
Every release follows the [compatibility policy](compatibility-policy.md); generated notes link it
and state the migration review or exact versioned migration action.

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

   Before freezing the candidate, run `python3 scripts/lifecycle_acceptance.py` under every Python
   and reference operating system named by the candidate record. The runner uses disposable homes,
   verifies the immutable v0.9.0 archive pin, and covers clean install, repeated sync, upgrade,
   rollback, conflicts and uninstall. Store its JSON output with the candidate evidence. This is a
   filesystem/configuration lifecycle check; it does not qualify a native client.

4. Tag the verified commit with the matching immutable `v<version>` tag and push that tag.
   The release workflow repeats qualification and source gates before publishing. Never move an
   existing tag to repair a failed release; fix the source and use a new version.

## Reference and personal site

5. In the reference-site checkout, pin `vendor/agent-harness` to that exact tag, commit the gitlink,
   and run its CI commands: `npm ci`, `npm test`, `npm run build`, `node scripts/smoke.mjs`.
   The manifest must identify both version and source commit. From the harness checkout run
   `python3 scripts/release_preflight.py --reference-repo <reference-checkout>`.
6. Merge the reference update with its PR and deploy through its existing main-branch workflow.
   A skipped deployment job is not a deployment. Record the workflow run and distribution identity.
7. Merge the personal-site card change; run `npm ci`, `npm run build` and its complete-site artifact
   checks on HEAD. Inspect the infrastructure diff before its guarded deployment script, avoiding
   unrelated infrastructure changes. The shared card links to reference compatibility facts and
   does not maintain its own inventory count or version claim.
8. Set GitHub About description and topics from `product.json`, keeping the reference homepage URL.
   Verify production HTML, SEO/social metadata, compatibility statuses, search results, deep links,
   install instructions, the exact release manifest and both personal-site card placements.
   Record HTTP statuses and rendered inspection results; mark any unavailable check unverified.

## Rollback

Keep the previous harness tag, both site commits, reference gitlink and deployed artifact identity
before publishing. A regression gets a revert PR and a new harness release; do not retarget the
old tag. Restore the reference site's previous immutable pin and deploy its rebuilt artifact;
restore the personal site's previous card commit through its normal pipeline. Reconcile local
configuration through its ownership journal, preserving conflicts and adopted backups. Verify
live pages and release identity again. Infrastructure rollback is separate and must not be inferred
from a static-content rollback.

## Release status

The 0.9.0 catalog records every required Claude Code and Codex client as qualified. The release is
complete only when the exact merged commit carries the immutable `v0.9.0` tag and the release
workflow publishes it. Reference and personal-site deployment status remains independently
verifiable; never infer a deployment from a source merge or bypass the release preflight.
