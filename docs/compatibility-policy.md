# Compatibility and release policy

Version 1 protects the interfaces a user or integration must rely on while leaving implementation
details free to improve. A compatibility claim applies to agent-harness itself; it cannot promise
that an external runtime, model provider or client will preserve behavior outside the harness's
control. The versioned [compatibility catalog](compatibility.md) records what was actually observed.

## Stable public interfaces

Semantic versioning applies to these documented interfaces beginning with v1.0.0:

- documented `harness` commands, options, exit-success meaning and machine-readable JSON fields;
- user configuration keys, value types, precedence and the ownership/conflict rules used to merge
  native settings;
- the primitive authoring contract for rules, stance dimensions and variants, skills, roles and
  workflows;
- versioned adapter and process contracts, including capability names and request identities;
- compatibility-catalog status meanings and evidence requirements;
- managed-file ownership, preview, migration, rollback and uninstall behavior; and
- the stable support floor named by the release's compatibility catalog.

Human-readable wording, ordering and whitespace are not stable unless a page says otherwise.
Internal Python modules, helper functions, locks, caches, test fixtures, planning artifacts and
undocumented state are implementation details. Generated native files may change shape while their
documented effective behavior, ownership and migration guarantees remain compatible. A native
runtime's private configuration format is not a harness API.

Preview capabilities may ship behind an explicit label. They still receive safe ownership and
data-preservation behavior, but their feature shape and native support status are not covered by
the v1 stable promise. Promotion to stable requires a release decision and native evidence.

## Versioning rules

- **Patch** releases restore documented behavior, fix security or data-preservation defects, update
  evidence and documentation, or narrow a claim that external facts have made false. They do not
  require a user to change valid configuration.
- **Minor** releases add backward-compatible commands, optional fields, primitives, adapters or
  supported clients. New behavior defaults to inactive or preserves the prior effective behavior.
- **Major** releases may remove a stable interface, reject previously valid configuration, change a
  documented default's effective behavior, reduce the stable support floor by product choice, or
  require a migration that cannot be performed safely and reversibly by the harness.

Changing an enforced hook, permission projection or ownership boundary is classified by its
observable effect, not by the size of the diff. A supposedly additive default that changes an
existing user's agent behavior is breaking unless it is opt-in.

## Deprecation and removal

A stable interface is deprecated before removal. The deprecation names the replacement, affected
configuration or command, migration procedure, first deprecated version and earliest removal
version. Release notes and the relevant reference page carry the notice; diagnostics warn when the
harness can identify affected use without collecting telemetry.

Removal normally waits until the next major release and at least 90 days after the published
notice. A minor release may stop generating a deprecated form only when existing installations are
migrated automatically and reversibly while the old input remains accepted. Preview interfaces may
change in a minor release, with migration guidance whenever user-owned state is affected.

## Configuration and generated-file migration

Migration begins with preview. It identifies owned keys and files, adoption conflicts, backups and
the resulting effective configuration before writing. The harness must preserve unrelated native
settings, user files, adopted backups and visible conflict state. A failed or interrupted migration
recovers to the complete prior state or the complete new state; ambiguous partial state is reported
and never treated as success.

Release notes state either **No migration action required** or list the exact action and recovery
path. When action is required they link the relevant versioned guide. Rollback restores the prior
executable or checkout, managed projections and ownership journal without deleting unrelated data.
Uninstall removes only harness-owned output and reports retained user state.

## Security and external-runtime exceptions

A confirmed vulnerability, credential exposure or data-loss defect may require immediate removal
or disablement without the ordinary notice period. Use the smallest safe change, publish a security
advisory and migration or containment steps, and issue a new version; never move an existing tag.
Legal restrictions may require the same treatment.

When a provider or native runtime changes behavior outside the harness, update the catalog and
public claim as soon as the evidence changes. A patch release may mark a client unqualified or add a
limitation because continuing a false support claim is not compatibility. Restoring or replacing
that support follows the ordinary minor/major rules according to the harness changes required.

## Failed and partial releases

Tags and published artifacts are immutable. If publication fails after a tag exists, record which
surfaces completed, stop, fix the cause and publish a new version under this policy. Do not retarget,
delete and recreate, or silently replace a tag or asset.

The release transaction publishes in order: verified source tag and artifact, reference-site pin,
then project-site metadata. Mutable sites roll back to their prior immutable pins. A corrective
release repeats the affected qualification, lifecycle and audit gates; the prior release remains a
historical record. Release notes always link this policy and state migration actions.
