# Personal stances and operational settings

Your way of working, across AI agents. Personal stances remain extensible harness primitives;
shared policy resolution carries selected choices to both runtime projections. A choice does not
override native restrictions or prove identical model behavior.

## One effective selection

`harness stances --json` reports selected text, its source, execution bindings, numeric settings,
review routing and adapter coverage. Resolution is defaults, user, explicitly selected project,
then session stance overrides. Project files may select stances only; operational settings,
external scopes and custom bindings are user-owned. Sync projects persistent user defaults;
session/project values never become global defaults. A lifecycle event uses one validated snapshot.

`lib/harness_core/preferences.py` is the shared resolver for the CLI, lifecycle coordinator,
legacy hook entrypoints, workers and telemetry. Invalid selections fail before sync writes.
Operational hooks deny or report unverified policy rather than guess at malformed configuration.

Custom dimensions such as feedback can be arbitrary guidance. A custom variant of an operational
builtin does not silently inherit executable behavior. Explicit user `policy_bindings` can map it
to an existing built-in policy, for example `{"autonomy/careful": "ask"}`. This references a custom
`autonomy/careful.md` variant and preserves its prose while the native policy uses `ask`.
Built-ins cannot be rebound, bindings cannot execute code, and unsupported controls stay visible.

## What is fixed and what can vary

Truthful results, uncertainty, secret protection, explicit authorization and native restrictions
are invariants. Stances select behavioral philosophies. Settings select bounds and mechanics.
Presets supply defaults; explicit user selections win. Existing software/general presets remain
available; init asks the original core questions while advanced choices use `config set`.

- **Verification** selects local-first, ci-authoritative or hybrid evidence. Testing independently
  selects test-writing requirements. CI-authoritative may create a draft before remote checks finish;
  it never authorizes merging pending/failed checks or skipping stronger repository requirements.
- **Integration tests** select fixtures-only, explicit-live or repo-native. A live selection does not
  authorize production access or manufacture credentials. Mark live tests separately.
- **External actions** select draft-first, explicit-request or scoped-standing-authority. Standing
  scopes are exact action/destination pairs with timezone-aware expiration. Remove an entry to revoke it.
  `harness policy external --action ACTION --destination DESTINATION` inspects a match, never executes
  an action or grants native permission. Arbitrary shell/connector interception is not claimed.
- **Documentation** selects concise-reference, explanatory or repo-native. **Document history**
  selects append-only or living; dated evidence, audit records and applied migrations remain immutable.
- **Decision interface** selects prose, structured or adaptive. Unsupported UI falls back to prose;
  authorization must be unambiguous in every presentation.
- **Build versus buy** adds delivery-speed, operational-maturity and balanced to capability-ceiling
  and off. **Change scope** selects minimal-diff, local-cleanup or systemic-fix within the user request.
- **Research** selects quick-check, source-led or exhaustive. All are bounded and preserve evidence,
  contradictions and uncertainty. Exhaustion reports incomplete coverage.
- **Context** selects cost-default, preserve-cache, adaptive or handoff. Under cost-default, max
  permits compaction and other cost presets prefer fresh sessions with explicit handoff. Explicit
  context selection wins; detector hits follow that policy, not an unconditional compaction ban.

## Review and constrained roles

`harness policy review --risk presentation|logic|sensitive` computes the selected review plan.
Self-check stays inline, independent uses one quality reviewer, and scope-and-quality uses separate
scope and quality workers. Risk-adaptive maps presentation to self-check, logic to independent,
and authorization/secrets/persistence/migrations to scope-and-quality. Repository gates can be stronger.
Delegation-off does not silently spawn or downgrade independent review. Unresolved requirements
produce nonzero inspector status. Different-family requires verification of actual family identity;
provide `--author-model` and `--reviewer-model` plus explicit user `model_families` bindings.
Missing or same-family bindings leave review unresolved. The worker must launch with that reviewer
model; configured family labels are not a claim of native model attestation.

Constrained roles keep the approved isolated CLI execution boundary. They cannot redelegate or
write directly. Planner publication retains new-path, symlink and atomic-write protections; only
its content shape follows plan-ceremony (Review Card versus titled light plan).

`delegation_controls.writes` is serial or isolated-worktrees. `max_depth` defaults to 1 (root may
spawn children; children may not spawn). `harness policy delegation --workspace PATH` checks declared
scheduling inputs; repeat `--active-workspace PATH` for every active writer and use `--depth N` for
the intended depth. Parallel writers must use distinct, nonoverlapping linked Git worktrees.
This is an explicit scheduling preflight, not a census of native agents or a new worker launcher.
Constrained workers still cannot redelegate even when a broader user depth is selected.

## Settings

Use `harness config set GROUP.KEY VALUE`. Booleans must be booleans; integers must be integers,
not strings or booleans. Unknown fields and invalid bounds fail before mutation.

- `budgets.gather_words`: 1–100000, default 400; `digest_words`: same range, default 600.
- `budgets.search_calls`: 1–10000, default 200; provider limits remain separate hard ceilings.
- `budgets.fan_out`: 1–32; cost defaults are frugal 3, balanced 6, max 16.
- `budgets.review_rounds`: 1–10, default 3. Explicit budget values override cost defaults.
- `delegation_controls.max_depth`: 1–8; `writes`: serial or isolated-worktrees.
- `gates.mode`: blocking or advisory; `max_blocks`: 1–100, default 8;
  `timeout_seconds`: 1–3600, default 240.
- `observability.enabled`: boolean, default true; `retention_days`: 0–36500, default 0;
  `include_repo` and `include_branch`: booleans, default true.

Gather limits feed the brief guard; search limits feed detectors. Other budgets are explicit
workflow guidance: no universal native agent/search census is available. Native hard limits win.
The gate uses configured bounds and includes them in cached-evidence identity. Advisory failure,
timeout, error, changed-tree and retry release never become green evidence. Registered Stop deadlines include a margin above the configured gate command deadline. A lower
external client limit still leaves an interrupted run unverified.

Disabled telemetry prevents detached collection, rescan and ledger writes. Retention runs under
the ledger lock, on successful writes, using the UTC session end timestamp, falling back to the original collection timestamp. Rescans
do not refresh the collection age or revive already expired sessions. Zero keeps history;
unknown-age records are retained rather than guessed expired. Metadata opt-outs affect newly
written records; they do not silently purge existing records. Remove old records explicitly if
needed. No command or message bodies are added to the usage ledger. Rescan preserves recorded
stance/settings provenance; missing historical provenance remains a rescan inference.

## Ownership and migration

Old configurations inherit new defaults. Explicit selections remain intact. `voice=off` and
answer-card no longer install Scannable; the ownership ledger restores the previous style if
it still owns the last value. A user-edited field is preserved, reported once as a conflict, and released from harness ownership.
If an installation predates ownership provenance, an existing style is not safe to delete by
inference. It remains user-owned until explicitly reconciled. Uninstall uses the same ledger.

No candidate is synced into a real user home during tests. Isolated homes cover off/on/off,
repeated sync, session override non-persistence and user-style changes after release.

## Coverage and acceptance

Each preference spans up to six surfaces. Inapplicable surfaces do not acquire fake enforcement:

- **Rules and stance text:** invariants and selected behavioral guidance; shared by both runtimes.
- **Skills:** follow selected documentation, plan, research and delegation policies.
- **Workflows and framework recipes:** select review/scope/verification and supply worker artifacts.
- **Settings:** one validated schema; output-style ownership restored on transitions.
- **Hooks:** shared resolved snapshot; gate/collection bounds and brief limits applied where supported.
- **Detectors:** selected context/search policy and recorded provenance; missing observations stay unknown.

Tests exercise every shipped variant, custom bindings, precedence, malformed policy, ownership,
worker light-plan publication, scope expiration, declared worktree isolation, telemetry disable/
retention and gate behavior. Critical pairs are cost/context, voice/style, review/delegation,
testing/verification/gates and autonomy/external-actions. Instruction tests do not prove a model
will follow guidance. Source tests and generated projections do not qualify native clients.
The existing compatibility/release gate remains authoritative; no new qualified client is claimed.

## Delivery trace

The implementation issues below share the resolver contract. New choices inherit the defaults
listed above; old configuration files need no rewrite. Selected text is instruction coverage,
not native qualification. The focused regression suite is `tests/test_preference_contract.py`;
existing lifecycle, worker, ownership and detector suites continue to apply.

| Issue | Owning surfaces and acceptance evidence |
| --- | --- |
| #117 | Resolver, hooks, detectors, settings: project/session precedence and voice off/on/off restoration. |
| #118 | Verification/integration stances, rules, builder and review workflows: every variant renders; gate failures remain unverified. |
| #119 | External-action stance and scope inspector: exact destination, expiration and malformed scope tests. No connector interception. |
| #120 | Delegation settings, workflows and preflight: real linked-worktree isolation, overlap and depth rejection. |
| #121 | Decision-interface/plan-ceremony guidance, planner worker: titled light plans and existing Review Card validation. |
| #122 | Documentation/history stances, conciseness rules and authoring skills: all variants resolve and render. |
| #123 | Context/cost stances, settings, brief guard and detectors: explicit budget precedence and cost/context pairs. |
| #124 | Review inspector, workflows and framework recipes: depth, delegation-off and model-family resolution; actual worker confinement stays adapter-owned. |
| #125 | Build-versus-buy variants: each resolves and renders for both runtime worker prompts. |
| #126 | Change-scope variants and build guidance: each resolves and renders; no authority beyond the approved task. |
| #127 | Research variants, workflow and skill: shared word/search budgets and detector boundaries. |
| #128 | Usage collection: disabled launch/scan/write, metadata exclusion, expiration and preserved collection age. |
| #129 | Stop policy: advisory failure, retry release, timeout, cache invalidation and registered deadline margin. |
| #130 | Shared resolver and diagnostics: old config, custom bindings, every variant, schema boundaries, isolated sync and generated projections. |

Native qualification remains a separate release prerequisite recorded by the compatibility
catalog; these source-level checks do not mark previously unqualified targets qualified.
