---
title: "Sprint change proposal: the measurable-harness roadmap"
date: 2026-09-24
delivery_issue: 783
bmad_id: AH-D013
mode: batch
scope: major
path: hybrid of direct adjustment and an MVP review
approval: approved in the maintainer's roadmap review of 2026-09-24, with all decisions accepted; this document is reviewed in its pull request
---

# Sprint change proposal: the measurable-harness roadmap

**Verdict.** Reorder the plan so the MVP claim ships in two milestones. v0.14.0 makes every module a switch
you can see, and v0.15.0 publishes proof set 1 against bare Claude Code. Superpowers interop, the Jev judge,
randomised real sessions and Codex parity follow in v0.16.0 and v0.17.0. The v1.0.0 contract gains an
evaluation gate.

**Artifacts this proposal changes:**
- `_bmad-output/planning-artifacts/prds/prd-agent-harness-2026-09-23/prd.md` and its `.memlog.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-agent-harness-2026-09-23/EXPERIENCE.md`, `DESIGN.md` and
  their `.memlog.md`
- `_bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md`
  and its `.memlog.md`
- `_bmad-output/implementation-artifacts/AH-D013.md`, AH-D013's own reservation in
  `_bmad-output/issue-map.json`, and the regenerated `_bmad-output/implementation-artifacts/sprint-status.yaml`
- the spine's round-3 review record, `reviews/review-round3.md`
- **Later, in step 3:** GitHub milestones and labels, the new stories' entries in the issue map and sprint
  status, and `_bmad-output/planning-artifacts/epics.md`. N20 later updates
  `_bmad-output/planning-artifacts/v1-release-plan.md`.

**N1 to N20 are this proposal's working labels** for the new stories. Step 3 maps each one to its BMad ID
and GitHub issue in an amendment appended to this document. The PRD, the spine and the UX specification
never use these labels.

## 1. Issue summary

**The trigger has two parts.**
- **The layered-harness vision** (#778, AH-D012, merged in PR #779). The harness is independent layers,
  every module switchable, and measurable by construction. Every module declares its claims, its surface
  and its instrument, and a module with no instrument reports as unmeasured.
- **The 2026-09-24 review of the release cost evaluation.** A read-only review of how the cost evaluation
  runs at release. It found that the replay's current bar cannot support a claim.

**The problem.** PRD §9 puts the Superpowers mode and the four-arm benchmark in v0.14.0, and ties a
published live cost result to decision-provider consumers in v0.15.0. The MVP claim needs neither. It needs
every module switchable, attributable and measured, and a defensible result against bare. SM-2's bar, a
same-day ratio from three reps, is too weak to carry that result.

**Issue type:** a new requirement from the maintainer (the vision), together with a technical limitation
found in the evaluation.

**Evidence from the review:**
- **Release runs only the static tier.** The live replay is not a release step, and no benchmark history is
  committed.
- **Manifest drift.** The task manifest holds 8 tasks, and the replay runs all of them. The benchmark docs
  still say "4 tasks x 2 arms x 2 reps".
- **The turn cap is never passed.** `max_turns: 60` is validated but never reaches the CLI. Scored runs are
  bounded only by the soft budget cap and the run timeout.
- **The stop gate cannot fire in replay.** Each run is a fresh temporary snapshot that no profile trusts.
  None of the 64 saved runs from 23 Sep contains stop-hook feedback.
- **The two arms have different web access.** The harness profile allows web search and fetch on docs
  domains, and bare allows nothing.
- **The usage-prices task is probably not honestly passable.** Its held-back test pins exact live prices,
  and the fence blocks the web.
- **Zero subagent spawns** in all 64 saved eight-task runs, in both arms.
- **Unscored spend on eight tasks, 23 Sep.** Pass and fail were not saved. The harness cost 1.284x bare
  ($8.51 against $6.63) in one run and 1.446x in a redo, and cost more in 15 of 16 task cells.
- **A fixed prefix.** The harness's first-turn cache write is about 24.1k tokens against 12.5k for bare,
  about 11.6k extra per session.

## 2. Impact analysis

**Epic impact:**
- **#552, the selection model (AH-E011):** stays in v0.14.0 as the control-plane core. The Superpowers mode
  (#558) and its copy (#561) move to v0.16.0, and #553 becomes a v0.15.0 spike.
- **#632, measurement (AH-E013):** spans v0.14.0 and v0.15.0, and gains the observation, attribution and
  proof-set stories.
- **#135, Jev as controller (AH-E003):** splits. #140 moves to v0.16.0, and the rest parks in the backlog.
- **#116, the stance and settings contract (AH-E002):** the policy preferences park in the backlog, apart
  from #117, #130, #276 and #685 in v0.14.0 and #120, #123 and #128 in v0.17.0.
- **#206, v1.0.0 (AH-E005):** gains the evaluation gate (N20).
- **#212, adoption (AH-E006):** moves to v0.17.0 with its cohort work.
- **#745, cache-rebuild spend:** a v0.17.0 epic, with #746 to #751.

**Story impact:** 153 open issues were classified on 2026-09-24: 20 core, 37 enabling, 66 later, 20
backlog and 10 to close. Twenty new stories, N1 to N20, are added. Every open issue moves to the milestone
in the map below.

**Artifact conflicts:**
- **PRD:** §9.2 contradicts the new map; SM-2's target and power are too weak; FR-56 treats 0.85 as a
  publish bar; FR-58 is dated v0.14.0; many status lines name a milestone that no longer holds.
- **Architecture spine:** no decision covers the module manifest, zero-footprint observation, per-module
  attribution or estimand labels. AD-16's tag names v0.15.0.
- **UX specification:** UJ-6, UJ-9 and the drift line are dated to milestones that move.

**Technical impact:** none in this change, which edits planning documents only. The v0.14.0 work adds a
manifest to every module kind, a fingerprint and attribution to every ledger row, and a test that
observation adds nothing to the bare arm's context.

## 3. Recommended approach

**Path: a hybrid of direct adjustment and an MVP review.** **Scope: major.**
- **Direct adjustment:** existing stories move milestone, and N1 to N20 are added. No completed work is
  reverted.
- **MVP review:** the MVP is redefined as the switchable, measured harness with proof set 1, and the line
  is drawn after v0.15.0.
- **Rollback** was not viable: nothing merged conflicts with the new order.

**Rationale.** Work is ordered by what the claim cannot ship without: control plane, then observation, then
evaluation, then proof. The Superpowers north star needs the slot model and a measured baseline first, so
running it later costs nothing the claim needs. The #553 spike in v0.15.0 keeps its risk visible early.

**Effort, risk and timeline:**
- **Effort:** five milestones, about 20 new stories.
- **Risk: medium.** v0.14.0 is heavy, at about 37 existing issues and 7 new. If the control-plane core
  has not merged by the midpoint, the release-hygiene decisions and docs move to v0.15.0.
- **Delegation may never fire (#429).** Proof set 1 then reports the cost claim as unsupported under SM-2's
  stop condition, and the roadmap continues on adherence and effectiveness.
- **Timeline:** the Superpowers north star slips two milestones, to v0.16.0.

## 4. Detailed change proposals

The after-text below is what went into validation. Two review rounds then refined the wording of SM-2, FR-56
and the new spine decisions. The PRD and the spine hold the text of record, and their memlogs record each
refinement.

### 4.1 Stories and milestones

**The MVP claim.** Every harness module is switchable, attributable and measured, and the harness shows its
effect on instruction adherence, output effectiveness and cost against bare Claude Code, in a defensible
proof set.

**v0.14.0, Switchable**
- **Control plane:** #552 (the epic), #554, #555, #556, #557, #117, #130, #643, #294, #276
- **Observation:** #644, #760, #577, and #685, which decides whether message bodies may be stored
- **Enforcement fixes:** #687, #576, #739, #761, #772
- **Evaluation plane:** #482, #428, #509, and the #632 epic, which spans v0.14.0 and v0.15.0
- **Docs:** #562 (the selection model and modes; its four-arm part moves to v0.16.0), #648
- **Release hygiene:** #563, #582, #612, #677, #688, #689, #759, #762, #773, #741, #742, #640
- **New:**
  - **N1:** manifest fields on #554: claims, surface, instruments, slot, dependencies and conflicts.
  - **N2:** a profile fingerprint on every ledger row, extending #482 beyond the replay.
  - **N3:** per-module attribution of context tokens and hook decisions.
  - **N4:** zero-footprint observation. A test proves the bare arm's model context is identical with
    observation on and off.
  - **N5:** adherence events: each recommendation emitted, and the user's response within N turns.
  - **N6:** the replay fixes found on 2026-09-24: the task count, `max_turns`, the stop gate in snapshots,
    equal web access, the usage-prices task, and hook events through `stream-json`.
  - **N7:** the evidence standard and a pre-registration template (the 12-item checklist).
- **Moving out:** #553 to v0.15.0 as a spike; #558, #561 and #430 to v0.16.0; #707 and #753 to the backlog.

**v0.15.0, Measured (the MVP)**
- **Eval tiers:** #510, #511, #512
- **Bench:** #559, the two-arm path, decoupled from #553 and #558; #560, harness against bare; #754, the
  one-policy pair, extended to the 2×2; #514, after #482
- **Rules:** #602, #647
- **Delegation:** #429, #513
- **Observation:** #748, cache-rebuild attribution for the soft estimates
- **Interop spike:** #553
- **New:**
  - **N8:** Cost-of-Pass and pass rate with task-clustered paired CIs and a Pareto view, plus Wilson or
    Bayesian intervals on pass rates.
  - **N9:** a task set sized by power analysis and above the break-even size, long multi-turn tasks
    included, at five or more trials.
  - **N10:** the 2×2 unit design: bare, the rule, the economy slice, and the rule plus the economy slice.
  - **N11:** the soft-estimate report: the adherence rate and the if-followed estimator, every figure
    labelled as a soft estimate.
  - **N12:** the proof bundle, `harness evidence verify`, evidence cards, and landing copy gated on proof
    status.
- **Moving out:** the #135 epic splits, with #140 to v0.16.0 and #141, #143, #145, #147, #156, #157, #372,
  #373 and #374 to the backlog; #377 and #755 to v0.16.0; #128, #120, #523, #524 and #692 to v0.17.0;
  #541, #542, #543 and #693 to the backlog.

**v0.16.0, Composable**
- **Existing:** #558, informed by the #553 spike; #559 and #560, extended to four arms; #561, and #562's
  four-arm part; #545, #525, #430; #377, #140, #755
- **New:**
  - **N13:** the slot model and the adapter contract.
  - **N14:** Jev compliance packs calibrated on #377's labels, reporting κ, ECE and bias audits.
  - **N15:** the layer-swap design on the four-arm bench.
- **Moving out:** #544 to the backlog.

**v0.17.0, Real work**
- **Existing:** #128, #692; the #745 epic, with #746 to #751; #123, #523, #120, #493, #524; #292, #293;
  #212, #213, #214
- **New:**
  - **N16:** the field experiment: assignment, outcomes, ITT, a sample-ratio check, a novelty split and
    CUPED.
  - **N17:** Codex parity: Codex OTel ingest, and a Codex arm.
  - **N18:** a factorial screening runner.
  - **N19:** the Harbor external task set, after `licensing-review`.

**v1.0.0, Stable**
- **Existing:** #206, #207, #209, #210, #211, #134, #633, #639, #686, #694, #215
- **New:** **N20:** the evaluation gate in the 1.0 contract.

**Backlog**
- **Jev decision consumers:** #135, #141, #143, #145, #147, #156, #157, #372, #373, #374, #753
- **Policy preferences:** #116, #118, #119, #121, #122, #124, #125, #126, #127, #129
- **Session archive:** #541, #543, #544, #546, #693
- **Editor and desktop clients:** #216, #217
- **Other:** #542, #634, #636, #641, #645, #646, #707, #715
- **Papercuts, taken any time as maintenance:** #406, #410, #411, #412, #413, #420, #421, #635, #642, #650,
  #690, #691, #695, #697, #698, #699, #774, #775

**Step 1 closures:** #369 (superseded by #560), #392, #433 and #537 (duplicates of #774), #538 (duplicate of
#606), #776 (duplicate of #413), #531 after its Python 3.9 check, #533 and #638 (absorbed), and #696. #530
stays open until its audit check. The v0.12.1 milestone is closed.

### 4.2 PRD

**§9, Release scope and roadmap.**
- **Before:** §9.2 lists v0.14.0 as the selection model with the `superpowers` mode and the four-arm
  benchmark, v0.15.0 as "close the loop" with decision-provider consumers and "a published live cost
  result, pass or fail", and v0.16.0 as credibility breadth.
- **After:** §9.2 keeps that text, headed by a line saying its v0.14.0 to v0.16.0 entries are superseded
  and kept as the plan of record at 2026-09-23. The v0.12.1 entry notes it closed on 2026-09-24 without a
  release, superseded by 0.13.0 and 0.13.1. A new `### Amendment 2026-09-24: the measurable-harness roadmap`
  at the end of §9 carries the MVP claim, v0.14.0 Switchable to v1.0.0 Stable with what each newly
  delivers, the MVP line after v0.15.0, and the evaluation gate. §9.1 gains an **Evaluation gate** bullet
  pointing to it.
- **MVP impact:** the MVP becomes the end of v0.15.0.

**SM-2, Measured cost claim.**
- **Before:** "on the release task set, a same-day ratio of 0.85 or less, with the pass rate at least bare
  minus one"; "a claim is published only from three or more reps, with a stated minimum detectable effect
  and the per-task figures beside the headline".
- **After:**
  - **Target:** Cost-of-Pass and pass rate, harness against bare. Paired, task-clustered 95% intervals
    govern the comparison; Wilson or Bayesian intervals describe each arm's pass rate and are descriptive
    only.
  - **Power:** five or more trials per task and arm; α 0.05 two-sided, power 0.8, a reference ratio of 0.85
    against a null of 1.0; a task set sized so the minimum detectable effect is at most 15%, stated before
    the run; long multi-turn tasks included.
  - **Pre-registered hypothesis:** the Cost-of-Pass ratio is at most 0.85 of bare, with the pass rate no
    lower than bare minus one task. That margin is δ, pre-registered as 1/k for k tasks.
  - **Decision rule:** supported only when both hold. The paired, clustered interval on the ratio excludes
    1.0 with the point estimate at or below 0.85, and the lower bound of the paired, clustered interval on
    the pass-rate difference (harness minus bare) is above −δ. Published whatever it shows. The
    evidence-standards review recommends no explicit rule, so the maintainer's stated rule applies.
  - **Current:** the 1.052 figure becomes history, a point ratio with no interval and not a test of the
    hypothesis. The 23 Sep eight-task runs were unscored and ran with unequal web access, so they are not a
    result.
  - The stop condition is unchanged, and the old text is kept under **Superseded 2026-09-24**.
- **Sources cited:** Cost-of-Pass (https://arxiv.org/pdf/2504.13359), clustered and paired errors
  (https://arxiv.org/html/2411.00640), the delta method for clustered ratios
  (https://arxiv.org/pdf/1803.06336), small-n intervals (https://arxiv.org/pdf/2503.01747).

**FR-56, Live replay against a bare arm.**
- **Before:** "The publish bar is fixed in advance: at most 0.85 of bare, while passing at least as many
  tasks as bare minus one."
- **After:** the 0.85 figure is a pre-registered hypothesis tested under SM-2, with δ defined as 1/k. The
  status notes the replay defects found on 2026-09-24 are planned for v0.14.0. The old sentence is kept as
  superseded.

**FR-54, Landing copy as data.**
- **Before:** "No published copy says "cheaper" until a same-day ratio passes the publish bar (FR-56)."
- **After:** "… until a result supports SM-2's pre-registered hypothesis (FR-56)".

**FR-58, Per-rule regression and the four-arm benchmark.**
- **Before:** "planned (v0.14.0: #514, #559, #560)".
- **After:** "planned: per-rule attribution and the two-arm path (v0.15.0: #514, #559, #560); four arms
  (v0.16.0: #559, #560, #561)".

**Status lines re-dated to the map:**
- UJ-6 "(planned 0.14)" → "(planned 0.16)"; UJ-9 "(planned 0.15)" → "(planned 0.16)".
- FR-16 "(v0.14.0, #557, #558)" → "(v0.14.0, #557; v0.16.0, #558, the `superpowers` mode)".
- FR-22 "(#602, v0.14.0)" → "(#602, v0.15.0)".
- FR-34 "planned (unscheduled, #513)" → "planned (v0.15.0, #513)".
- FR-48 "`act` consumers are planned for v0.15.0" → "planned (backlog, #141, #372)".
- FR-49 "per-point criteria are planned (v0.15.0)" → "(v0.16.0)", with #377 marked v0.16.0.
- FR-50 "planned (v0.15.0, #135)" → "planned (v0.17.0, #692; the #135 epic is in the backlog)". #692 is the
  FR-50 story itself.
- FR-63 "planned (v0.15.0: #542, #543, …)" → "planned (backlog, #542, #543, …)".
- FR-2 "(#294, unscheduled)" → "(#294, v0.14.0)"; FR-37 "(#292, unscheduled)" → "(#292, v0.17.0)"; FR-44
  "(#413, unscheduled)" → "planned (backlog, #413)".
- FR-20's unmeasured-rule listing "unscheduled" → "v0.15.0, with the module scorecard".
- FR-67 and its §12 entry → "unscheduled: the 2026-09-24 roadmap does not place it".
- SM-C5 "the §9.2 breadth work" → "the v0.17.0 Codex parity work and any later runtime work".
- §11: Q2 and Q3 → "backlog (#420)" and "backlog (#421)", with Q2 re-pointed to the issue map's lifecycle
  field; Q7 and Q9 → v0.17.0 with Codex parity; Q8 → v0.17.0 with the adoption cohort; Q12 → the backlog
  with the session archive; Q14 → unscheduled.
- The status legend defines `planned (backlog)`: accepted, but not scheduled to a milestone before 1.0.

**Status lines re-derived from tag containment.** Status lines that cite a closed issue were re-derived
here from `git tag --contains` on the merge commit. Other stale "unreleased" lines, which predate 0.13.0,
are a follow-up chore:
- FR-12: the minimum required target is implemented (0.13), for both Claude Code CLI targets (#533). The
  Codex CLI part is planned (v0.14.0, #612; v1.0.0, #686).
- FR-36: the interleaved-session fix is implemented (0.13, #611, merged in PR #624).
- FR-64: implemented (0.13, #620, PR #629). FR-65: implemented (0.13: #621, #623, PRs #631 and #683).

### 4.3 Architecture spine

- **AD-22, Modules declare a manifest** [PLANNED: fields and checks v0.14.0, #554; scorecard v0.15.0;
  slots and adapters v0.16.0]:
  - claims, surface, instruments, slot, dependencies and conflicts, kept with each primitive in the catalog
    and resolved by `posture.py`;
  - a shared slot is a resolution error unless one module cedes it, and a conflict never switches off an
    invariant without acknowledgement;
  - a module with no instrument reports as unmeasured;
  - the fingerprint is a digest of the resolved selection.
- **AD-23, Observation adds nothing to any arm's model context, and every new row is attributable**
  [PLANNED: v0.14.0, #482]:
  - an observation-only hook path, the only one installed in the bare arm;
  - a per-arm test that the first model request is byte-identical with observation on and off;
  - the fingerprint on every new row, soft-estimate token attribution on usage rows, and hook-decision
    attribution on decision-log rows.
- **AD-12, amended in place,** since it already holds the measurement invariants. It defines measured, soft
  estimate and unmeasured, orthogonal to FR-11's availability words. The soft series is never pooled with
  the measured one (planned for v0.15.0).
- **Review:** the spine's round-3 review found 11 issues, all fixed; see `reviews/review-round3.md`.
- **AD-16:** "[PLANNED: v0.15.0, #542, #543]" → "[PLANNED: backlog, #542, #543]".
- **Capability → Architecture Map:** selection gains AD-22; ledgers gain AD-23; benchmarks gain AD-22 and
  AD-23.
- **Diagram updates:** none. The dependency-direction diagram does not change.

### 4.4 UX specification

- **EXPERIENCE.md:** UJ-6 "(planned, v0.14.0)" → "(planned, v0.16.0)", since the `superpowers` mode (#558)
  moves. UJ-9 "(planned, v0.15.0)" → "(planned, v0.16.0)", with per-point criteria and #377's labels.
- **DESIGN.md:** the drift line "(planned, v0.15.0, FR-50)" → "(planned, v0.17.0, #692, FR-50)".
- **Unchanged:** the mismatch line, the selection report, modes in Select and the headless session fact
  stay v0.14.0 with the control plane.

## 5. Implementation handoff

**Scope: major.** It is a replan across the PRD, the spine and every open issue's milestone.

**Recipients and responsibilities:**
- **Step 2 (this change):** the PRD, the spine, the UX specification and this proposal, through the update
  intents of `bmad-prd`, `bmad-architecture` and `bmad-ux`.
- **Step 3:**
  - file N1 to N20 through `bmad-create-epics-and-stories`, then `scripts/bmad_issue_sync.py new` followed
    by `reserve`;
  - append an amendment to this proposal that maps each of N1 to N20 to its BMad ID and issue;
  - map and label #428, #429, #482, #493, #509 to #512 and #745 to #751;
  - move every open issue to its milestone above.
  - Moving milestones is public, so the move list is shown before it runs.
- **N20, in v1.0.0:** updates `v1-release-plan.md` with the evaluation gate.

**Success criteria:**
- PRD §9, SM-2, FR-56 and FR-58 match the map, and superseded text is recorded.
- The spine carries AD-22, AD-23 and the amended AD-12 with status tags, and the spine linter is clean.
- `bmad-prd` validation and the spine review pass.
- After step 3, `bmad_issue_sync.py audit --live` is clean, and each milestone holds exactly its list above.

## Checklist record

Mode: batch.

- **1.1 Trigger:** [x] Done. #778 (AH-D012) and the 2026-09-24 cost-evaluation review.
- **1.2 Problem and type:** [x] Done. A new requirement from the maintainer, with a technical limitation
  in the evaluation.
- **1.3 Evidence:** [x] Done. Section 1.
- **2.1 Current epic:** [x] Done. #552 completes in v0.14.0 without the `superpowers` mode.
- **2.2 Epic-level changes:** [x] Done. #135 splits; #632 spans two milestones.
- **2.3 Remaining epics:** [x] Done. Section 2.
- **2.4 New or obsolete epics:** [x] Done. #745 becomes a v0.17.0 epic; none are obsolete.
- **2.5 Epic order:** [x] Done. Control plane, observation, evaluation, proof, then interop.
- **3.1 PRD conflicts:** [x] Done. §9, SM-2, FR-56, FR-58 and status lines.
- **3.2 Architecture conflicts:** [x] Done. AD-12, AD-16, AD-22, AD-23.
- **3.3 UX conflicts:** [x] Done. UJ-6, UJ-9, the drift line.
- **3.4 Other artifacts:** [x] Done for this PR, which ships AH-D013's own reservation in `issue-map.json`
  and the regenerated sprint status. [!] Action-needed for `epics.md`, the new stories' issue-map entries
  (step 3) and `v1-release-plan.md` (N20).
- **4.1 Direct adjustment:** [x] Viable.
- **4.2 Rollback:** [ ] Not viable. Nothing merged conflicts.
- **4.3 MVP review:** [x] Viable.
- **4.4 Path:** [x] Done. Hybrid of direct adjustment and an MVP review.
- **5.1 to 5.5 Proposal components:** [x] Done. Sections 1 to 5.
- **6.1 Checklist complete:** [x] Done.
- **6.2 Proposal accurate:** [x] Done.
- **6.3 Approval:** [x] Done. Approved in the maintainer's roadmap review of 2026-09-24, with all decisions
  accepted; this document is reviewed in its pull request.
- **6.4 Sprint status:** [x] Done for AH-D013, regenerated in this PR. [!] Action-needed for the new
  stories' entries, which come with their issue-map entries in step 3.
- **6.5 Handoff:** [x] Done. Section 5.

## Amendment, 2026-09-24: step 3 filings

Step 3 ran under #787 (AH-C074). Each new story carries its type label, parent epic and milestone, and a story
file seeded with its Story, Context and value and Acceptance criteria; Design, Tasks and Dev notes wait for
its delivery pull request.

**New stories:**
- N1 → AH-S232 → #788, v0.14.0
- N2 → AH-S233 → #789, v0.14.0
- N3 → AH-S234 → #790, v0.14.0
- N4 → AH-S235 → #791, v0.14.0
- N5 → AH-S236 → #792, v0.14.0
- N6 → AH-S237 → #793, v0.14.0
- N7 → AH-S238 → #794, v0.14.0
- N8 → AH-S239 → #795, v0.15.0
- N9 → AH-S240 → #796, v0.15.0
- N10 → AH-S241 → #797, v0.15.0
- N11 → AH-S242 → #798, v0.15.0
- N12 → AH-S243 → #799, v0.15.0
- N13 → AH-S244 → #800, v0.16.0
- N14 → AH-S245 → #801, v0.16.0
- N15 → AH-S246 → #802, v0.16.0
- N16 → AH-S247 → #803, v0.17.0
- N17 → AH-S248 → #804, v0.17.0
- N18 → AH-S249 → #805, v0.17.0
- N19 → AH-S250 → #806, v0.17.0
- N20 → AH-S251 → #807, v1.0.0
- C2 → AH-C075 → #808, with no milestone: re-derive the PRD's stale `unreleased` status lines.

**Reserved:**
- Under #632: #428 AH-S252, #429 AH-B095, #482 AH-S253, and #509 to #514 as AH-S254 to AH-S259.
- Under #633: #677 AH-B096 and #707 AH-B097.
- With no parent: #493 AH-S260, #715 AH-SP013, and #531 AH-B098, which is closed but counts as accepted.

**Deviations from the map in section 4.1:**
1. #559, #560 and #748 sit in v0.15.0 and #562 in v0.14.0, the earlier of the two milestones the map gives
   each; #802 (N15) absorbs the four-arm extension and #562's four-arm docs.
2. Epics #552 and #632 carry no milestone. Their windows, v0.14.0 to v0.16.0 and v0.14.0 to v0.17.0, are in
   `epics.md`, so v0.14.0 can empty when its stories close.
3. PR #529 closes unmerged and #530 as not planned, both superseded by #787, which reserves #529's issues on
   current `main`.
4. #785, filed into v0.14.0 after the map was drawn, stays there; its delivery pull request reserves its ID.
5. #780 keeps no milestone.
6. #745 to #751 are not reserved here. Pull request #752 is open and already reserves them as AH-E018,
   AH-C067, AH-SP010, AH-S227 to AH-S229 and AH-SP011, IDs `main` has skipped so far; section 5's mapping of
   #745 to #751 completes when it merges. Their milestone moves are made.

**Final milestones:** v0.14.0 holds 43 open issues, v0.15.0 18, v0.16.0 11, v0.17.0 22 and v1.0.0 12;
59 have none. v0.17.0 is milestone 20.
