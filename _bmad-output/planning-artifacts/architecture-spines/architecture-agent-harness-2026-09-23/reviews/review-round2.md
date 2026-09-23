# Round 2 review: ARCHITECTURE-SPINE.md, DESIGN.md and EXPERIENCE.md (agent-harness, 2026-09-23)

Reviewed against the `bmad-rebaseline` worktree at `e0f1041` (VERSION 0.12.0). Paths are relative to
that worktree root. `SPINE` is `architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md`,
`DESIGN` and `EXP` are the two files in `ux-designs/ux-agent-harness-2026-09-23/`, and `PRD` is
`prds/prd-agent-harness-2026-09-23/prd.md`. All three documents are under `_bmad-output/planning-artifacts/`.

**Verdict:** the rewrite fixed most of round 1, including the critical finding. The spine now has a new
contradiction with the ledger code, a dependency rule the session hook breaks, and a gap in the `act`
stage. Both UX documents describe CLI output and journeys that the code does not produce, and they do not
mark those parts as planned.

**Counts:** round 1: 20 fixed, 4 partially fixed, 1 not fixed. New findings: 8 high, 13 medium, 11 low.

## 1. First-round status

| ID | Status | Note |
| --- | --- | --- |
| C1 | Fixed | The kernel is placed in `policy/hooks/`, the load-by-path direction matches the code, and a "where logic goes" rule exists (SPINE:35-62, 85-101, 384). The new finding N2 covers what is still missing. |
| H1 | Fixed | AD-2 is tagged "resolver unification in progress" and names #294 and #554 as the migration (SPINE:116, 126-127). |
| H2 | Fixed | AD-7 now lists ask, the stop-event block, and post-tool and session notices (SPINE:192-197). |
| H3 | Fixed for Codex | AD-15 marks `act` unsupported where `ask` becomes `deny` (SPINE:300-302). The same gap on Claude Code is new finding N5. |
| H4 | Partially fixed | Ledgers are carved out and the migration is named (SPINE:339-342). The helper has no name or location, and it is scoped to three writers. Kernel writers also do a temp-file-then-replace, and under the spine's own dependency rule they cannot import a `lib/harness_core` helper: `policy/hooks/posture.py:224-231`, `policy/hooks/stop-gate.py:209-221`, `policy/hooks/usage-feed.py:280-288`, `policy/hooks/usage-log.py:1433-1436`. |
| H5 | Fixed | AD-11 has the additive-schema rule (SPINE:253-256). |
| H6 | Fixed | AD-2 records the init-default versus explicit-choice constraint, and #557 chooses the mechanism (SPINE:129-131). |
| M1 | Not fixed | AD-5 is still tagged `[ADOPTED from #620]` and says "everything after the block is preserved byte for byte" (SPINE:164, 174-175). The sync tool still rewrites the whole file (`scripts/bmad_issue_sync.py:600`), and PRD FR-64 says planned (v0.14.0, #620) (PRD:1196). There is no migration note like the ones AD-2 and AD-18 now carry. |
| M2 | Fixed | The event table is the one declaration, and it changes only after a probe (SPINE:199-200). |
| M3 | Fixed | AD-17 names `remote_control.py` and the pin-and-doctor migration (SPINE:328-329). |
| M4 | Fixed | The viewer is noted as predating the contract (SPINE:237-238), and `integrations/` is in the seed (SPINE:417). |
| M5 | Partially fixed | The catalog states and tier words are now correct. The capability-mode list still omits `instruction-and-setting`, which `adapters/claude-code/capabilities.json` uses for `stances.cost.mode` (SPINE:113, 387). |
| M6 | Fixed | AD-18 marks the stop-gate counter as the one to migrate (SPINE:337-338). |
| M7 | Partially fixed | A definition exists (SPINE:385), but three things are wrong. First, the dispatcher registers only `adapters/<runtime>/hook.py` (`lib/harness_core/lifecycle.py:592-596`); it invokes the policy scripts. Second, `rule-detectors.py`, `allow-readonly-bash.py` (loaded as a library by `grade-bash.py:79`, never invoked by the dispatcher) and `usage-log.py` (loaded, `lifecycle.py:582`) are neither hooks nor listed libraries. Third, decision points are not listed by the dispatcher (see N7). |
| M8 | Fixed | The operational envelope and deployment diagram now cover the installer, plugin, platform, audit, release and benchmarks (SPINE:426-452). |
| M9 | Fixed | AD-20 binds FR-8, FR-59 and FR-61, and AD-18 binds FR-62 (SPINE:333, 362). |
| M10 | Partially fixed | The spine now covers NFR-16, NFR-9 and the sync lock (SPINE:142, 386, 391). The NFR-6 batch rollback on a partial failure (PRD:1255-1256) is still unstated. |
| M11 | Fixed | AD-21 (SPINE:371-378). |
| L1 | Fixed | FR-18, FR-42, FR-43, FR-53, FR-54, FR-69 and FR-70 are all bound. N9 covers a new mis-binding. |
| L2 | Fixed | SPINE:60-61 and 421. |
| L3 | Fixed | SPINE:47. |
| L4 | Fixed | SPINE:466 and 471. |
| L5 | Fixed | SPINE:315-316. |
| L6 | Fixed | SPINE:281-289. |
| L7 | Fixed | `SOURCE_PATHS` is named as the authority, with per-runtime scope (SPINE:155-159). N6 covers the carve-out that is still missing. |

## 2. New findings

### Spine

**N1**
- **Severity:** high
- **Location:** SPINE AD-11, the Rule (SPINE:248).
- **Defect:** "Hooks append rows with a locked or `O_APPEND` single write, and never rewrite a ledger" contradicts the SessionEnd usage worker. The worker rewrites the whole `usage.jsonl` through `upsert`, and neither AD-11 nor AD-18 records this or plans a migration.
- **Evidence:**
  - `policy/hooks/usage-log.py:1399-1437`: `upsert` reads every row and writes a temp file, then calls `os.replace`.
  - `policy/hooks/usage-log.py:1692-1698`: the `--worker` path calls `upsert(records)`.
  - `policy/hooks/usage-log.py:1687`: the rescan path.
  - `policy/hooks/usage-log.py:1721-1722`: the worker is spawned from the hook.

**N2**
- **Severity:** high
- **Location:** SPINE Invariants dependency rule and diagram (SPINE:41, 85-101), and AD-6 (SPINE:184-185).
- **Defect:** The rule "kernel imports nothing above itself; nothing outside the kernel resolves stances" leaves out three edges:
  - The `harness-session` kernel hook shells out to `bin/harness`: `stances --json`, `diff`, `integration check` and `task show`. It reports session stances from the CLI's `load_config` ladder, so retiring that ladder under #554 breaks the hook, and the spine does not say so.
  - The CLI loads kernel modules directly by path.
  - `rule-detectors.py` imports from `lib/vendor`.
- **Evidence:**
  - `policy/hooks/harness-session.py:70, 99, 159, 253`.
  - `bin/harness:2405-2409`: `cmd_stances` calls `load_config`.
  - `bin/harness:149-153` and `bin/harness:3840-3844`: direct kernel loads.
  - `policy/hooks/rule-detectors.py:28-29`.

**N3**
- **Severity:** high
- **Location:** SPINE AD-8 (SPINE:214-215) and AD-19 (SPINE:356).
- **Defect:** AD-8 requires "every spawn path is guarded or declared unguarded". AD-19 approves a plugin that carries no hooks. That plugin ships `gatherer`, `planner`, `reviewer` and `spec-reviewer` as native agents, so their spawns are unguarded. The catalog declares only `installs_hooks: false`, not an unguarded constrained-role path.
- **Evidence:**
  - `.claude-plugin/plugin.json:12-24`.
  - `compatibility/catalog.json:66-75`.
  - The `harness compatibility` limitations text has no plugin-role entry.
  - PRD adversarial review #25.

**N4**
- **Severity:** high
- **Location:** SPINE AD-15 (SPINE:300-302), with AD-7.
- **Defect:** At `act`, the only move AD-15 allows is allow to ask. The first planned `act` consumer is the stop-claim check, #141. A Stop event has no allow or ask, only block, so AD-15 either forbids #141 at `act` or leaves its meaning undecided.
- **Evidence:**
  - PRD:912: "the stop-claim check first (#141)".
  - `lib/harness_core/lifecycle.py:572-573` and `lifecycle.py:611-612`: Stop answers `{"decision": "block"}`.
  - `_bmad-output/implementation-artifacts/AH-SP001.md` is a 26-line stub.

**N5**
- **Severity:** medium
- **Location:** SPINE AD-15 (SPINE:300-302).
- **Defect:** AD-15 treats only Codex as a runtime that cannot answer `ask`. On Claude Code, in `auto` and `bypassPermissions` modes, an `ask` is ignored, which is why the grader switches to `deny` there. An `act`-stage ask would therefore be a silent allow in those modes.
- **Evidence:**
  - `policy/hooks/grade-bash.py:27-31` quotes the hooks reference: 'The "ask" decision is ignored'.
  - `policy/hooks/grade-bash.py:55` (`DENY_MODES`).
  - `lib/harness_core/lifecycle.py:481`.

**N6**
- **Severity:** medium
- **Location:** SPINE AD-4 (SPINE:157-159).
- **Defect:** The spine says "a change to one runtime's adapter directory invalidates that runtime's targets together". This leaves out the shared-file carve-out that PRD FR-51 keeps: a change to `bindings.json`, `capabilities.json` or `worker.py` under either adapter invalidates every target. Only `hook.py` is private to a runtime.
- **Evidence:** `compatibility/catalog.json` `evidence_invalidation.shared_files` and `runtime_files`, `lib/harness_core/compatibility.py:141-156`, and PRD:1008-1009.

**N7**
- **Severity:** medium
- **Location:** SPINE Consistency Conventions, "Hook ids" (SPINE:385).
- **Defect:** The spine says "Named decision points are listed by the dispatcher". In fact, two copies of the list exist, one in the kernel and one in core, kept in step by a test. The dispatcher lists none. The #555 builder has no stated authority to follow.
- **Evidence:** `policy/hooks/decisions.py:46`, and `lib/harness_core/decisions/controls.py:35-39`: "A copy rather than an import".

**N8**
- **Severity:** medium
- **Location:** SPINE, from AD-6 to AD-21 (SPINE:178-378).
- **Defect:** Only AD-1 to AD-5 carry a status tag. Several untagged ADs state planned behaviour in the present tense and give no migration note, so a builder cannot tell which rules the code already follows:
  - AD-13: "Both tools read declarative detectors identically".
  - AD-16: "Every overlap is logged".
  - AD-15: the `act` stage.
- **Evidence:**
  - AD-13: PRD FR-67 says harness loading is planned (PRD:550-562), and `bin/harness:3742-3751` reads `DETECTORS` only.
  - AD-16: FR-63 is planned for v0.15.0 (PRD:1157-1160).

**N9**
- **Severity:** low
- **Location:** SPINE AD-5 Binds (SPINE:166).
- **Defect:** AD-5 (public planning) binds FR-54 (landing copy as data), which AD-19 owns.
- **Evidence:** PRD:1034 and SPINE:351.

**N10**
- **Severity:** low
- **Location:** SPINE Design Paradigm diagram (SPINE:76-78) and AD-11 (SPINE:242, 249).
- **Defect:** The diagram draws the decision log inside the store that is replicated by OTLP replay. The log is a separate file and is never exported.
- **Evidence:** `policy/hooks/telemetry.py:124`, `policy/hooks/decisions.py:5, 128`, and PRD:647.

**N11**
- **Severity:** low
- **Location:** SPINE Stack, the Remote Control row (SPINE:404), and AD-17.
- **Defect:** The pin names 2.1.280 only. The code also relies on pointer-mtime behaviour that it records as verified on 2.1.278.
- **Evidence:** `lib/harness_core/remote_control.py:186` and `lib/harness_core/remote_control.py:99, 193`.

**N12**
- **Severity:** low
- **Location:** SPINE AD-4 (SPINE:162) and AD-19 (SPINE:354).
- **Defect:** The spine says "every public surface reads its version and status from the catalog and `product.json`", but the plugin manifests hard-code `0.11.1` against VERSION 0.12.0, and the spine gives no migration note.
- **Evidence:** `.claude-plugin/plugin.json` `version` and `.claude-plugin/marketplace.json` `metadata.version`.

**N13**
- **Severity:** low
- **Location:** SPINE AD-18 (SPINE:345-346).
- **Defect:** The spine requires every substituted-HOME launch to get its keychain "from `harness_core.keychain`". The native acceptance driver has its own implementation instead, which does fail closed.
- **Evidence:** `scripts/native_acceptance.py:133-149` and `lib/harness_core/workers.py:204`.

### DESIGN.md and EXPERIENCE.md

**N14**
- **Severity:** high
- **Location:** DESIGN Colors (DESIGN:48) and EXP Voice and tone (EXP:121-122).
- **Defect:** The closed support set is "supported, preview, planned, unsupported, unknown, failed". No field in the code can hold "supported", "unknown" or "failed". The set contradicts the spine's convention (catalog states, with "preview" as a display word only), and DESIGN's own status-line example uses `unqualified`, which is outside the set.
- **Evidence:** `lib/harness_core/compatibility.py:8-9`, `adapters/*/capabilities.json` (`qualification`, `mode`), SPINE:387, and DESIGN:71-72.

**N15**
- **Severity:** high
- **Location:** EXP UJ-2 (EXP:56-59).
- **Defect:** The journey says a `delegation` change "for one repository" plus `sync` makes "one authored choice reach both native formats". But `sync` strips `HARNESS_PROJECT_CONFIG` and links only the user-level stances. This is a declared limitation (#276, #294), and the journey does not mark it.
- **Evidence:**
  - `bin/harness:1190-1192`.
  - `harness compatibility` limitation: "harness sync links user-level stance selections only; ... a project selection changes what harness stances and the hooks resolve, not the linked stance text".

**N16**
- **Severity:** high
- **Location:** EXP UJ-4 (EXP:78).
- **Defect:** `harness usage --by role --by day` cannot express two groupings. `--by` takes a single choice, so the command silently reports by day only.
- **Evidence:** `harness usage --help`: `--by {day,repo,model,role,rule,stance,decision,provider,prefix}`; also PRD adversarial review #19.

**N17**
- **Severity:** high
- **Location:** EXP UJ-8 (EXP:107-110).
- **Defect:** The journey promises four things `remote-control status` does not do:
  - list each host's environment id and live sessions;
  - report environment reuse after a restart;
  - list archived sessions with a manual command.

  What `status` actually prints:
  - launchd state and a log path per folder;
  - the heal state;
  - only sessions that are active but disconnected. Archived sessions are deliberately excluded.
- **Evidence:** `bin/harness:3300-3320`, `bin/harness:3417-3441`, and `lib/harness_core/remote_control.py:611-626` ("An archived session is past recovery ... so both are left out").

**N18**
- **Severity:** medium
- **Location:** EXP UJ-3 (EXP:63-66).
- **Defect:** The journey has two errors:
  - `ruleprobe` states the measured, dark and unmeasured counts only when `--rules <dir>` is given, and it gives counts, not a share.
  - A rule with a reason is `dark`; an `unmeasured` rule has no reason. The journey's "unmeasured rules, each with the reason it has no detector" conflates the two states.
- **Evidence:** In the vendored wheel `lib/vendor/ruleprobe-0.1.0-py3-none-any.whl`, see `ruleprobe/rules.py:12-15, 33, 74-75`. Also PRD adversarial review #45.

**N19**
- **Severity:** medium
- **Location:** EXP UJ-5 (EXP:83-88).
- **Defect:** The journey describes story files that hold the design, and an `issue-ownership` check on required sections, as current. Both belong to FR-64, which is planned for v0.14.0. Today's stories are 26-line stubs, and the check does not read story files.
- **Evidence:** `.github/scripts/check_issue_ownership.py:33-72`, which only validates the pull request and its mapping. Also `_bmad-output/implementation-artifacts/AH-S200.md` (26 lines) and PRD:1195-1206.

**N20**
- **Severity:** medium
- **Location:** EXP UJ-7 (EXP:102-103).
- **Defect:** The journey says "preflight passes only when the tag, the compatibility catalog, the changelog and About all agree". Preflight never reads the changelog. It checks the tag only with `--reference-repo`, and it skips About with a warning when `gh` is not authenticated.
- **Evidence:** `scripts/release_preflight.py:46-73`, `scripts/release_preflight.py:16`, and `lib/harness_core/compatibility.py:287-294`.

**N21**
- **Severity:** medium
- **Location:** DESIGN Usage table (DESIGN:77-81) and EXP Component patterns, "Usage output" (EXP:134-135) and UJ-4 (EXP:79).
- **Defect:** The documents' usage-output claims do not match the report:
  - `partial` is reported in a header line and the `unpriced` footer, not on the row.
  - The dollar column is a bare `usd`, not labelled as a list-price equivalent.
  - The fewer-than-30 warning exists only for `--by role`. `--rules` uses a threshold of 20 and blanks the note instead.
- **Evidence:** `bin/harness:4387-4389`, `bin/harness:4400`, `bin/harness:4076`, `bin/harness:4150`, `bin/harness:3712` and `bin/harness:3786`.

**N22**
- **Severity:** medium
- **Location:** DESIGN Layout, "Narrow screens" (DESIGN:66-67), and the EXP Accessibility floor (EXP:161-162).
- **Defect:** The documents say every report reads on a phone at under 80 columns. The fixed-column usage tables are 113 and 147 columns wide.
- **Evidence:** `bin/harness:4388-4389` (the main table header) and `bin/harness:4122-4125` (the role table header).

**N23**
- **Severity:** medium
- **Location:** DESIGN Components, "Drift line" and "Mismatch line" (DESIGN:82-85).
- **Defect:** Both are presented as existing components with no planned marker. The drift report is FR-50, planned for v0.15.0 (#135). The mismatch line is planned for v0.14.0. Today's `--rules` view is keyed by detector and notes `unobserved`.
- **Evidence:** PRD:946-954, PRD:539, and `bin/harness:3782-3791`.

**N24**
- **Severity:** medium
- **Location:** EXP UJ-2 confirmation (EXP:58-59) and Component patterns, "Compatibility output" (EXP:132-133).
- **Defect:** The documents promise more than `harness compatibility` prints:
  - It prints each stance's qualification state (`unqualified`), not whether a hook enforces it or it is only advisory. The mode is only in `stances --json` `adapter_coverage`.
  - Its text output names no client version.
- **Evidence:** `bin/harness:4595-4602`, a live `harness compatibility` run, and `bin/harness:2414`.

**N25**
- **Severity:** medium
- **Location:** EXP Component patterns, "Previews" (EXP:130), and State patterns, "Operations" (EXP:144).
- **Defect:** `sync --dry-run` prints a flat list keyed by action kind (`link`, `render`, `ignore`, `path`, `codex`, `vscode`), not grouped by runtime and owner. It uses none of the operation states. Under DRY RUN it also prints past-tense lines such as "added to PATH", "hooks registered" and "sync complete".
- **Evidence:** `bin/harness:1163`, `bin/harness:1485` and `bin/harness:1525`, and a dry run under a throwaway HOME.

**N26**
- **Severity:** medium
- **Location:** EXP Component patterns (EXP:140).
- **Defect:** "A refused relaxation of a floor names the scope that set the floor" describes floors as existing behaviour. The spine defers floor semantics, and the PRD leaves them as open question 6.
- **Evidence:** SPINE:477 and PRD:1537. The code has no floor mechanism.

**N27**
- **Severity:** low
- **Location:** EXP UJ-1 (EXP:51-52) and Information architecture step 6 (EXP:34-38).
- **Defect:** The documents do not match how doctor and the inspect commands behave:
  - `doctor` prints no published-qualification line. Qualification lives in `harness compatibility`, which the Inspect step leaves out.
  - `doctor` always exits 0.
- **Evidence:** `bin/harness:1799-1934` (`cmd_doctor`) and `bin/harness:1840` ("native trust and activation unverified").

**N28**
- **Severity:** low
- **Location:** DESIGN "Selection report" (DESIGN:86-90) and EXP Interaction primitives (EXP:157).
- **Defect:** The documents describe `harness selection`, mode keys and a headless session fact without a planned marker. All of them are FR-16, planned for v0.14.0. EXP marks UJ-6 as 0.14 but not these parts.
- **Evidence:** PRD:405-419.

**N29**
- **Severity:** low
- **Location:** EXP State patterns, "Evidence" (EXP:145).
- **Defect:** The code has only three evidence results: `passed`, `failed` and `unverified`. `superseded` and `contaminated` are not evidence states.
- **Evidence:** `lib/harness_core/compatibility.py:274`.

**N30**
- **Severity:** low
- **Location:** DESIGN Colors (DESIGN:50) and EXP State patterns (EXP:147).
- **Defect:** The decision stages leave out `off`, which is the default.
- **Evidence:** `lib/harness_core/decisions/controls.py:41-42`.

**N31**
- **Severity:** low
- **Location:** DESIGN Review Card (DESIGN:91-95).
- **Defect:** DESIGN does not say which limits are enforced. The hook enforces only an 85-line cap. The 70-line limit, the 12-node and 80-column diagram limits and the Mermaid placement are authoring rules only.
- **Evidence:** `policy/hooks/validate-plan-card.py:13` and `policy/hooks/validate-plan-card.py:83-86`.

**N32**
- **Severity:** low
- **Location:** DESIGN Status line (DESIGN:71-72).
- **Defect:** The documented format is "state: subject (scope)". The CLI prints `subject: state` with no evidence scope.
- **Evidence:** `bin/harness:4596`.

## 3. Checked and consistent

- Neither UX document says `doctor` uses ok, warn or fail.
- Neither UX document claims per-target invalidation. UJ-7's "qualifies each required target once" fits per-runtime scoping.
- `harness decisions eval` and `remote-control heal` exist.
- `init` presets exist: `bin/harness:94` and `bin/harness:3153`.
- The sync lock is taken at `bin/harness:1180`.
- The standing-context cap is 4,202 tokens (12607 // 3, `bin/harness:176-183`).
- CI runs lint, smoke, corpus and test on pull requests and in the merge queue (`.github/workflows/ci.yml`).
