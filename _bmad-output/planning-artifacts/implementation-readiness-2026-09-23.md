---
title: Agent Harness implementation readiness
status: final
created: 2026-09-23
updated: 2026-09-23
verdict: concerns
supersedes: implementation-readiness.md
sources:
  - product-briefs/brief-agent-harness-2026-09-23/brief.md
  - prds/prd-agent-harness-2026-09-23/prd.md
  - ux-designs/ux-agent-harness-2026-09-23/DESIGN.md
  - ux-designs/ux-agent-harness-2026-09-23/EXPERIENCE.md
  - architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md
  - epics.md
  - ../implementation-artifacts/sprint-status.yaml
---

# Implementation readiness

## Verdict

**CONCERNS.**

Most open stories can be implemented as recorded:
- Every one of the 385 work items has a story file that passes the depth check.
- The sprint status lists all 89 open non-epic items as `ready-for-dev`.
- 67 of the 70 functional requirements trace to stories.

Three requirements have no open story, and five decisions are still open. The story files also record contradictions between issues and the PRD or the spine. A developer building any of the items named under [Concerns](#concerns) would have to invent a decision that nothing records. The rest can proceed.

## What planning exists

- **Brief:** `product-briefs/brief-agent-harness-2026-09-23/brief.md`.
- **PRD:** `prds/prd-agent-harness-2026-09-23/prd.md`.
  - FR-1 to FR-70: 43 implemented, 6 merged but unreleased, 14 partial and 7 planned.
  - It also has NFR-1 to NFR-16, SM-1 to SM-11, and the open questions Q1 to Q14.
- **UX:** `ux-designs/ux-agent-harness-2026-09-23/`. It holds the design contract and the experience contract for UJ-1 to UJ-9, with planned behaviour marked.
- **Architecture:** `architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md`. AD-1 to AD-21 each carry an adoption status.
- **Research:** five research runs under `research/`, with the source ledger.
- **Epics:** `epics.md`, with 17 epics and a requirement-coverage section. Completed work with no epic is listed by issue range.
- **Stories:** 385 story files under `../implementation-artifacts/`.
  - All are typed design records that pass the depth check.
  - 101 issues are open: 58 stories, 14 bugs, 6 chores, 5 spikes, 5 decisions, 1 task and 12 epics.
- **Tracking:** `../implementation-artifacts/sprint-status.yaml` is derived from the issue map by `scripts/bmad_issue_sync.py sprint-status`.
  - Items: 284 done, including 5 completed epics; 89 ready-for-dev; 0 backlog.
  - Epics: 12 in progress.

## Traceability

Traceability here means a citation: a story traces to a requirement when its story file names the requirement's ID.

**Forward, from requirement to story:**
- Every implemented or unreleased FR is cited by the closed stories that delivered it.
- Every partial or planned FR has an open story, except three:
  - **FR-34, Delegation that fires (partial).** No open story carries the remaining half.
  - **FR-46, Architecture-viewer integration (partial).** `epics.md` places it under AH-E002, but no open child story cites it.
  - **FR-50, Evidence-driven stance proposals (planned).** AH-E003 claims it, but no child issue covers it (recorded in AH-E003).
- FR-63 names a logged usefulness signal for every archive search. No story's acceptance criteria carry it, so #546's second reopen criterion has no delivering story (recorded in AH-D007 and AH-S191).

**Backward, from open item to requirement:**
- Every open story cites an FR, with three exceptions:
  - **AH-B068 (#538)** duplicates #606, and PR #615 fixed its defect. It should close rather than be built.
  - **AH-C053 (#640)** and **AH-C054 (#645)** are architecture-conformance chores under AH-E017. They trace to ADs rather than FRs, which is expected.

## Epics and stories

- Each epic states its goal, the requirements it covers, its children, its architecture slice, its sequencing and its exit criteria.
- The open epics carry value for a user or a maintainer. They are ordered by milestone, and no epic depends on a later one to be useful.
- Stories are independently completable, with two exceptions that depend on open decisions or spikes:
  - #558's `delegated` ceremony waits on FR-16's headless rule.
  - The close-the-loop stories under AH-E003 wait on their spikes.
- Their story files name these dependencies.

## Architecture and UX

- The decisions that stories rely on are recorded as AD-1 to AD-21. Each AD's status says whether it is adopted, partial or planned, and AH-E017 carries the conformance work for the partial ones.
- UX journeys that describe planned behaviour are marked planned. Story files point at them rather than restating them.

## Concerns

Each concern names where the gap lives and the BMad skill that fixes it.

1. **Three requirements with no open story.**
   - Where: FR-34, FR-46 and FR-50 above.
   - Fix: `bmad-create-epics-and-stories` adds the stories under AH-E002 and AH-E003.
2. **Five open decisions gate their dependents.** Each has options recorded; the story files name what they block.
   - AH-D002 (#276): how project and session stance selections reach a native client.
   - AH-D005 (#420): how map lifecycle stays current between merges.
   - AH-D006 (#421): grade-bash against the sync tool's unattended sub-issue delete.
   - AH-D007 (#546): semantic retrieval held until FTS misses.
   - AH-D008 (#582): whether qualification evidence is invalidated per case.
   - Fix: a decision recorded on each issue and its story file. Use `bmad-architecture` where the decision changes an AD.
3. **Stories that contradict the PRD or the spine.** A developer would have to choose a side. Fix: `bmad-correct-course` for the cross-cutting ones, then a story update.
   - #554 lets a project file set `rules`, but AD-2 and FR-2 allow only stances (AH-S197).
   - #558's `delegated` ceremony waits for approval, but FR-16 says a headless session proceeds (AH-S201).
   - #206 promises Codex CLI in v1 unconditionally, but FR-12 and PRD §9.1 make it conditional (AH-E005).
   - #334's smoke tier is advisory, but FR-52 says a failure stops the round (AH-S124).
   - #543 stores message bodies, but #128 forbids collecting them (AH-S045 and AH-S191).
   - #545 routes confined roles through `harness role run` from a script, but #540 found that a script has no shell (AH-S193).
4. **Stale release references in the v1 stories.**
   - #209 asked for the lifecycle baseline to be repinned to v0.10.0, but it still pins v0.9.0.
   - #207, #210 and #211 still name v0.10.0 as the previous release (AH-S090 and AH-S092).
   - Fix: `bmad-correct-course` against `v1-release-plan.md`.
5. **Duplicates and tracking gaps.**
   - #392, #433 and #537 describe one failure, and #433 has no BMad ID. #538 duplicates #606.
   - #369 is marked superseded by #560, but it is still open.
   - Fix: close or merge the duplicates, and reserve an ID for any issue that stays open.

## Safe to proceed

Every open story that is not named under Concerns can be built from its story file as written. That covers most of AH-E011, AH-E013 to AH-E017, and the bugs.

The build workflow's activation step reads the story file as the spec and writes the design back, so each change keeps this record current.

The 2026-09-19 readiness report, `implementation-readiness.md`, is superseded by this one.
