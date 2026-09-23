# Rubric review: ARCHITECTURE-SPINE.md (agent-harness, 2026-09-23)

**Verdict:** Not ready to finalize. The spine covers all 70 FRs in its map and its pinned versions are correct, but its domain and dependency model contradicts the codebase: the resolver and the shared hook libraries live in `policy/hooks/`, and `lib/harness_core` loads them by file. Three `[ADOPTED]` rules (AD-2, AD-5, and AD-18 by implication) claim guarantees the code does not give yet, and several real divergence points for the v0.14 and v0.15 stories are left open.

Counts: 1 critical, 6 high, 11 medium, 7 low.

Line references to the spine are `SPINE:<line>`. All other paths are relative to the `bmad-rebaseline` worktree root.

## Critical

### C1. The domain and dependency model puts the resolver in the wrong place and reverses the real import direction
- **Location:** Design Paradigm (SPINE:36-45), the Invariants dependency diagram (SPINE:71-87), the Structural Seed (SPINE:333-335), and the Capability map's "resolver in `lib/harness_core`" (SPINE:370).
- **Defect:** The stance and cost resolver is `policy/hooks/posture.py`, not a `lib/harness_core` module. Hook-shared libraries (posture, pricing, decisions, telemetry) live beside the hooks because hooks run as standalone scripts. `lib/harness_core` depends on `policy/hooks` and on `adapters/*/worker.py` by loading them from file, which is the reverse of the spine's diagram. None of this is stated, so a #554 builder ("one resolver") following the spine would create a third resolver in `lib/harness_core`.
- **Evidence:**
  - `policy/hooks/posture.py:3-8` says: "The one place a stance and the model ladder are resolved. Not a hook ... `lifecycle.py` loads this same file by path".
  - Core loads hook files: `lib/harness_core/catalog.py:320-329` (posture), `lib/harness_core/decision.py:142-149` (the decisions hook), `lib/harness_core/qualification.py:53-59` (pricing), `lib/harness_core/lifecycle.py:15,39-43` (every policy hook).
  - Core loads adapter code: `lib/harness_core/workers.py:40-42` loads `adapters/<runtime>/worker.py`.
  - An adapter imports core: `adapters/codex/worker.py:5` imports `harness_core.reconcile`.
  - The constraint is stated in code: `policy/hooks/decisions.py:29-31` and `policy/hooks/telemetry.py:11-14` say shared hook code "sits beside the hooks rather than in `lib/harness_core`" because nothing above the hook directory resolves.
  - No rule says where new domain logic goes, although `bin/harness` holds 5,039 lines and 197 functions, including the config precedence ladder (`bin/harness:314-345`).

## High

### H1. AD-2 is tagged `[ADOPTED]` but the code has two precedence ladders
- **Location:** AD-2 (SPINE:98-109) and AD-6 (SPINE:147-153).
- **Defect:** "One resolver owns precedence" does not describe the current code. Both `bin/harness` and `posture.py` implement defaults, then user, then project, then `HARNESS_STANCE_*`, and sync strips the session layer. #294 is still active. The spine gives no migration note and does not say which implementation is the authority.
- **Evidence:** `bin/harness:314-345` (`load_config`, including the project-stances-only check), `policy/hooks/posture.py:721-742` (`_selection`, `resolve`), `bin/harness:1191-1193` (sync drops the session keys), and `_bmad-output/issue-map.json` entry #294 (AH-B024, active).

### H2. AD-7's list of enforcement mechanisms leaves out ones that its own bound FRs rely on
- **Location:** AD-7 Rule (SPINE:159-164).
- **Defect:** The list allows only "pre-tool deny, pre-tool input rewrite, isolated role workers, local ledger". It leaves out:
  - the Stop-hook block (FR-36, and the first FR-48 `act` consumer, the stop-claim check #141);
  - the pre-tool `ask` (FR-35 maps grades to ask);
  - post-tool context notices (FR-37 neutralization, the FR-32 feed).

  Read literally, the rule forbids features it binds.
- **Evidence:** `lib/harness_core/lifecycle.py:558-573` (`neutralize-tool-output`, `usage-feed`, `stop-gate` dispatch) and `lib/harness_core/lifecycle.py:410-419` (ask and deny composition).

### H3. On Codex, AD-15's "act may only turn allow into ask" becomes a deny
- **Location:** AD-15 (SPINE:256-259), which interacts with AD-7 (SPINE:165-166).
- **Defect:** On Codex the dispatcher turns every `ask` into `deny`. A provider at `act` on Codex would therefore deny, which FR-48 forbids. The spine does not say what an `act` point does on a runtime that cannot answer `ask` (stay in `advise`, count as unsupported, or something else). The #141 and #372 builders will choose differently.
- **Evidence:** `lib/harness_core/lifecycle.py:418`: `fields["permissionDecision"] = "deny" if runtime == "codex" and strongest == "ask" else strongest`.

### H4. AD-18's atomic-write rule is too broad, does not match the code, and names no shared helper
- **Location:** AD-18 Rule (SPINE:294).
- **Defect:** "Writes go through a temporary file and an atomic replace, preserving the file's mode" does not fit the append-only ledgers. They use locked or `O_APPEND` single writes, and rewriting them by replace would lose concurrent rows. The three existing atomic writers differ, none of them preserves the file's mode, and the issue map and story files (named in NFR-6) are written non-atomically.
- **Evidence:**
  - Append-only ledger writes: `policy/hooks/usage-log.py:1498-1506` (a lock, then `open("a")`), `policy/hooks/decisions.py:499` (`O_APPEND`), `policy/hooks/usage-feed.py:177-182`.
  - `lib/harness_core/reconcile.py:14-27`: `mkstemp` creates the file as 0600 and the original mode is not restored.
  - `bin/harness:292-302`: a fixed `.harness-tmp` name, no `fsync`, and no mode handling.
  - `scripts/cost_bench.py:579` is a third writer.
  - Non-atomic issue-map and story writes: `scripts/bmad_issue_sync.py:262-263` and `scripts/bmad_issue_sync.py:600` (`write_text`).

### H5. How the ledger schema evolves is neither decided nor deferred
- **Location:** AD-11 (SPINE:205-216) and the Consistency Conventions "Data and formats" row (SPINE:311).
- **Defect:** PRD §7 makes the ledger schema and the exported attribute names public surface, and FR-66 requires the ledger to stay readable across upgrades. The spine has no rule for this: no version field, no additive-only rule, no reader-tolerance rule. Many independent writers exist or are planned: `usage-log`, `decisions`, the worker sweep, and the #541 archive.
- **Evidence:** A grep for `schema_version` in `policy/hooks/usage-log.py`, `policy/hooks/decisions.py` and `policy/hooks/telemetry.py` finds nothing. See PRD §7 "Public surface" and FR-66.

### H6. The Deferred item on mode precedence lets the v0.14 stories diverge
- **Location:** Deferred (SPINE:386-387) and AD-2 (SPINE:105-106).
- **Defect:**
  - The spine says mode precedence "is decided in #557", but #557 is active and its story is a 26-line stub.
  - #554, #555, #557 and #558 build in parallel in v0.14.0.
  - PRD FR-16 already constrains the answer: user keys shadow mode keys, but a mode must override what a default `init` wrote. That requires telling init-written values apart from user-chosen ones.
  - The spine records none of these constraints.
- **Evidence:** `_bmad-output/implementation-artifacts/AH-S200.md` (26 lines, no precedence text), `_bmad-output/issue-map.json` entries #554-558 (all active), and the PRD FR-16 consequences.

## Medium

### M1. AD-5 is tagged `[ADOPTED]`, but the sync tool still rewrites whole story files
- **Location:** SPINE:134-145.
- **Defect:** On drift, the sync tool re-renders the entire story file. It refuses only when it detects amendments. Byte-preserved bodies are the planned FR-64 (#620, active).
- **Evidence:** `scripts/bmad_issue_sync.py:600` and `scripts/bmad_issue_sync.py:192` (`render_artifact`).

### M2. AD-7's "Codex event support is probed, never hard-coded" contradicts the code, with no migration note
- **Location:** SPINE:167-168.
- **Evidence:** `lib/harness_core/lifecycle.py:18-21` (the `EVENTS` table hard-codes the Codex event set) and the usage-feed limitation in `adapters/codex/capabilities.json`.

### M3. AD-17 has no implementation and no location
- **Location:** SPINE:275-283.
- **Defect:**
  - Remote Control carries no version pin: 2.1.278 and 2.1.280 appear only in comments.
  - The doctor does not check the running client's version.
  - The code lives in `lib/harness_core`, not in an adapter, and the rule does not say which adapter it means.
- **Evidence:** `lib/harness_core/remote_control.py:99,186,193` and `bin/harness:1937-1976` (`remote_control_doctor`).

### M4. The architecture viewer contradicts AD-10
- **Location:** SPINE:193-203 and the Structural Seed (SPINE:336).
- **Defect:** The viewer is integration code, not a data descriptor. Only BMad has a descriptor. The top-level `integrations/` directory is missing from the seed, and the spine does not say whether the viewer will move to a descriptor.
- **Evidence:** `lib/harness_core/upstream_viewer.py`, `lib/harness_core/viewer_profile.py`, `integrations/architecture-viewer/upstream.py`, and `policy/integrations/` (holds only `bmad.json`).

### M5. The spine's status vocabulary contradicts the code's
- **Location:** SPINE:310 and SPINE:167.
- **Evidence:**
  - `lib/harness_core/compatibility.py:8`: `STATES = {"qualified", "unqualified", "planned", "unsupported"}`.
  - `lib/harness_core/compatibility.py:9`: `TIER_RESTRICTIONS = {"enforced", "advisory", "none"}`.
  - Capability modes in `adapters/*/capabilities.json` are `instruction` and `instruction-and-hook`.
  - The spine uses supported, preview, unknown and failed, and "enforced, advisory or unsupported".

### M6. The stop-gate counter is kept per checkout, which contradicts AD-18, with no migration note
- **Location:** SPINE:293.
- **Evidence:** `policy/hooks/stop-gate.py:197` (`state_path(root)`) and `policy/hooks/stop-gate.py:295`: another session's write resets the counter. FR-36 records this as a partial.

### M7. "Hook id" is undefined, which the #555 hook switch kind needs
- **Location:** SPINE:41 ("one script per hook") and SPINE:309.
- **Defect:**
  - `policy/hooks/` holds modules that are not hooks: `posture`, `pricing`, `telemetry`, `decisions`, `filter-lines`, `otel-headers`.
  - Only `adapters/<runtime>/hook.py` is registered with the runtime, and dispatch happens inside `lifecycle.py`.
  - Decision points such as `evasion-deny` are not scripts.
  - The spine says neither what the switchable set is nor where a switch is applied.
- **Evidence:** `policy/hooks/posture.py:5`, `lib/harness_core/lifecycle.py:592-596` (registration), `lib/harness_core/lifecycle.py:499-573` (dispatch), `lib/harness_core/lifecycle.py:342`.

### M8. The operational envelope is incomplete and partly unenforced
- **Location:** SPINE:320-321 and SPINE:347-363.
- **Defect:**
  - CI runs one `ubuntu-latest` system `python3`. Neither 3.9 nor 3.14 runs in CI, and no test enforces the 3.9 syntax floor.
  - The envelope says nothing about:
    - the installer and `stable` distribution channel;
    - the plugin marketplace channel;
    - platform support (NFR-4);
    - the scheduled live BMad audit;
    - the release workflow's own gates;
    - where the live benchmarks run and under what budget.
- **Evidence:**
  - `.github/workflows/ci.yml:17-61`.
  - `scripts/install.sh:8,21-22`.
  - `.claude-plugin/plugin.json`.
  - `bin/harness:1187-1189` (Windows is refused).
  - `.github/workflows/bmad-traceability.yml:5-28`.
  - `.github/workflows/release.yml:18-27`.

### M9. The session-operations FRs have no governing AD
- **Location:** Capability map (SPINE:381). AD-16 and AD-17 cover none of these FRs.
- **Defect:**
  - FR-8: approvals and verification never transfer between runtimes.
  - FR-62: every runtime launched under a substituted HOME gets a throwaway keychain. This rule cuts across four launchers.
  - FR-59 and FR-61 are bound to no AD.
- **Evidence:** `lib/harness_core/workers.py:200-204` (provisions a keychain), `scripts/native_acceptance.py:144` (substitutes HOME), and `scripts/cost_bench.py` and `lib/harness_core/remote_control.py`, which also use `keychain`.

### M10. Cross-cutting NFR divergence points go unstated
- **Defect:** The spine states none of these:
  - the NFR-16 hook overhead bar (250 ms p95);
  - the NFR-9 standing-context budget;
  - the NFR-6 batch rollback on a partial failure;
  - the NFR-10 rule that two syncs never interleave.

  The code already follows conventions for them that builders cannot see from the spine.
- **Evidence:** `policy/hooks/posture.py:23-24` ("Import-cheap on purpose ... the dispatcher loads this on every tool call"), `lib/harness_core/lifecycle.py:594-595` (per-event timeouts), and `lib/harness_core/reconcile.py:30-41` (the `sync.lock` flock).

### M11. The spine has no dependency rule
- **Location:** Stack (SPINE:316-327).
- **Defect:** PRD §7 says "standard library first; vendored wheels only for components owned or cleared". The spine states this only for export (AD-11). A builder could add a pip dependency or a new vendored wheel without the licensing check.
- **Evidence:** PRD §7 "Dependencies". Wheels are loaded by `sys.path` insertion at `lib/harness_core/reconcile.py:10` and `policy/hooks/rule-detectors.py:28-29`.

## Low

### L1. The FR mappings are incomplete
- FR-18 is missing from the Capability map (SPINE:367-382).
- The map assigns FR-69 and FR-70 to AD-3, but AD-3's Binds line omits them (SPINE:113).
- FR-42, FR-43, FR-53 and FR-54 appear in no AD's Binds.

### L2. `claude/` is described as generated, but it is not
- **Location:** SPINE:45.
- **Defect:** The spine says `claude/` is "generated projections, never sources". In fact, `claude/hooks`, `rules`, `skills`, `stances` and `output-styles` are symlinks into `primitives/` and `policy/hooks/`. `settings.template.json` and `OWNERSHIP.json` are hand-authored sources.

### L3. `adapters/<runtime>/hook.py` does not translate events
- **Location:** SPINE:42.
- **Defect:** The spine says this file "translates each runtime's event protocol". It is an 8-line shim. The translation happens in `lib/harness_core/lifecycle.py:16-17` (`ALIASES`) and `lib/harness_core/lifecycle.py:418`.

### L4. Worktrees and workspaces are mapped to the wrong place
- **Location:** SPINE:376 and SPINE:381.
- **Defect:** Worktrees (FR-44) and workspaces (FR-61) live in `bin/harness:4878-4898`. The map does not list them there.

### L5. AD-16 has no carve-out for runtimes without a pre-write hook
- **Location:** SPINE:270-271.
- **Defect:** The rule says "logging is not optional", but FR-63 requires the adapter to declare the gap on a runtime with no pre-write hook.

### L6. AD-14 reads as a global rule
- **Location:** SPINE:246-247.
- **Defect:** "Hooks enforce only two things" reads as applying to every hook, which conflicts with AD-7 and with AD-8's confinement denies. It should be scoped to cost.

### L7. AD-4 does not point at the authority for "source paths"
- **Location:** SPINE:131.
- **Defect:** The authority is `lib/harness_core/compatibility.py:10` (`SOURCE_PATHS`). The scope is also derived per runtime directory: `compatibility/catalog.json` has `evidence_invalidation.runtime_paths`, and see `lib/harness_core/compatibility.py:141-156`. So all clients of one runtime are invalidated together, not one "target" at a time.

## Verified consistent (no finding)

- The vendored wheels match the Stack table: `lib/vendor/ruleprobe-0.1.0-py3-none-any.whl` and `lib/vendor/tomlkit-0.15.1-py3-none-any.whl`.
- The 0.11.1 evidence client versions match the Stack table: 2.1.273 and 2.1.278 for Claude Code, 0.154.0-alpha.6.2 and 0.155.1 for Codex. The lifecycle records show Python 3.9.x and 3.14.x.
- BMad is 6.12.0 (`_bmad/_config/manifest.yaml:2`).
- The plugin manifest has no `hooks` key (`.claude-plugin/plugin.json`).
- The issue map uses `AH-<type><nnn>` IDs and the `github_number` key.
- CI runs in the merge queue (`merge_group` in `ci.yml`, `issue-ownership.yml` and `landing-copy.yml`).
- Every script and module named in the Capability map exists.
- All 70 FRs appear in the `binds` frontmatter.
