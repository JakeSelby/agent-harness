---
title: "Sprint change proposal: the Model Citizen rename"
date: 2026-09-25
delivery_issue: 876
bmad_id: AH-C078
mode: batch
scope: moderate
path: direct adjustment
approval: the maintainer approved the rename plan on 2026-09-25, with all decisions settled; this document is reviewed in its pull request
---

# Sprint change proposal: the Model Citizen rename

**Verdict.** Rename the product from Agent Harness to Model Citizen wherever the name is living copy or a
public address, inside the v0.14.0 milestone and with no re-scope. A new epic and five stories carry it. The
brand, a new `citizen` command, the plugin ID and the repository slug change; on-disk names, `AH-` IDs,
telemetry's `service.name` and dated records keep `agent-harness`, and `harness` stays a supported alias.

**Artifacts this proposal changes:**
- `_bmad-output/planning-artifacts/architecture-spines/architecture-agent-harness-2026-09-23/ARCHITECTURE-SPINE.md`
  and its `.memlog.md`: AD-24.
- `_bmad-output/planning-artifacts/epics.md`: the new epic, its stories and two coverage rows.
- `_bmad-output/issue-map.json`, the six new story files and the regenerated
  `_bmad-output/implementation-artifacts/sprint-status.yaml`.
- **Later, each in the pull request that makes it stale:** the UX specification in S1, and the PRD and the
  product brief in S3.

S0 to S4 are this proposal's working labels. Section 5 maps each one to its BMad ID and issue.

## 1. Issue summary

**The trigger.** "Agent harness" is becoming a category noun: other vendors and frameworks use it for any
harness around a model. A product named for its category cannot be searched for or defended as a name. After
several naming rounds the maintainer chose Model Citizen on 2026-09-25, registered model-citizen.dev, and
approved a rename plan the same day.

**Issue type:** a strategic change from the maintainer. No story revealed it; it is a product decision.

**Evidence, as checked on 2026-09-25:**
- **The command.** No Homebrew, PyPI or npm package installs a `citizen` binary. `harness` collides with
  another vendor's CLI.
- **The name.** PyPI `model-citizen`, npm `modelcitizen` and the GitHub slug `JakeSelby/model-citizen` are
  free. A live US mark for MODEL CITIZEN covers podcasts in classes 9 and 41; the EU is clear and the UK
  register is unchecked. The maintainer chose to proceed.
- **The compatibility policy.** Its SemVer promise starts at v1.0.0. Documented `harness` commands are
  stable, a minor may add a backward-compatible command, and removing one needs a notice, the next major and
  90 days. Human-readable wording is not stable. The plugin ID and repository slug are not listed.
- **The blast radius,** from `git grep` over tracked files: 209 living files change and 666 in dated or kept
  areas stay (section 2).

## 2. Impact analysis

**Epic impact:**
- **A new epic, AH-E020 (#875),** on v0.14.0, holding S0 to S4.
- **No existing epic changes scope.** The v0.14.0 milestone keeps every issue it holds; the rename adds five.
- **No epic becomes obsolete, and none is resequenced.** The rename's stories run beside the control-plane
  work; S3 follows S1 so its command examples run, and S4 follows the GitHub rename.

**Story impact:**
- **Five new stories,** S0 to S4, each one pull request.
- **Open issue titles stay.** 151 of 160 open issues mention the old name, almost all through the planning
  block the sync tool writes, and that block keeps the old slug (the keep list below).

**What changes:**
- **The brand, "Agent Harness", 59 lines in 34 files:** the 14 living lines change (README, docs,
  `product.json`, `.claude-plugin/`); 45 in `_bmad-output/` are dated records and stay.
- **`JakeSelby/agent-harness`, 4,117 lines in 585 files:** about 70 living lines change after the GitHub
  rename; the rest stay, since GitHub redirects them.
- **`agent-harness.jakeselby.com`, 6 lines in 5 files:** change to `https://model-citizen.dev`.
- **`agent-harness@agent-harness`, 7 lines:** change to `model-citizen@model-citizen`; doctor accepts both.
- **The version banner `agent-harness {VERSION}`, 6 places in `bin/harness`:** change.
- **`harness <subcommand>` text, 1,344 lines in 371 files:** change in about 156 living files; the lines in
  `_bmad-output/`, the sha256-pinned compatibility evidence and test invocations stay.

**The keep list,** with why each stays:
- **The lower-case category noun "agent harness"** still describes the product.
- **`bin/harness`** is the alias path and the real file: hooks and the installer find the checkout by it.
- **`~/.config/agent-harness`, `.agent-harness/` and `~/.local/state/agent-harness/`:** renaming them needs an
  automatic, reversible migration or a major with 90 days' notice.
- **launchd `com.agent-harness.*` labels, `# harness:` markers, the `# agent-harness` PATH and ignore blocks,
  the Codex banner and the `harness` rule and hook link names:** install, uninstall and reconcile find them by
  exact text.
- **Telemetry's `service.name="agent-harness"`,** so existing dashboards still match.
- **BMad's `project_name`, the `AH-` IDs, and the `prd-agent-harness-…` and `architecture-agent-harness-…`
  directory names:** IDs and hundreds of anchors depend on them.
- **The issue map's slug:** the sync tool writes it into every mapped issue's planning block, so changing it
  would rewrite about 160 issues. GitHub redirects the old URLs.
- **Dated records:** changelog entries, compatibility evidence, `docs/plans/` and dated planning artifacts.
- **Environment variables** are `HARNESS_*` and stay; there are no `agent_harness` or `AGENT_HARNESS_*` names.

**Artifact conflicts:**
- **PRD:** the product name, and FR text naming the command. The FRs do not change meaning.
- **Product brief:** the name. Its positioning line waits on a line the maintainer has not chosen.
- **Architecture spine:** nothing conflicts; the stable-identifier boundary was implicit and becomes AD-24.
- **UX specification:** command names in output.

**Technical impact:** none in this change, which edits planning documents only. S1 adds a command, S2
renames the plugin with a reinstall for plugin users, S3 edits copy, and S4 changes links and adds a lint
rule. The site, the GitHub rename, the About metadata and the release run outside these stories, under their
own approvals.

## 3. Recommended approach

**Path: direct adjustment. Scope: moderate.** A new epic and five stories join the v0.14.0 milestone; no
existing story moves, and no completed work is reverted.

**Rationale.** A minor may add a command, so `citizen` beside a permanent `harness` alias fits the
compatibility policy with no deprecation. Keeping the stable identifiers avoids a migration no user asked
for, and GitHub's redirects carry every old link the rename does not touch.

**Decision 2 is settled: the rename ships inside the full v0.14.0 milestone, with no re-scope.** v0.14.0 is
the roadmap's Switchable milestone and v0.15.0 its Measured one, so cutting v0.14.0 around the rename would
collide with the next milestone. The repository, site and filings still switch before 2026-09-30; only the
tag and the announcement wait for the milestone.

**Rejected:**
- **Keep `harness` as the only command:** zero churn, but the brand and the command never match.
- **Cut v0.14.0 around the rename and renumber the roadmap's milestones:** rejected by the maintainer.
- **Rename the on-disk names too:** needs a migration or a major with notice, for no user-visible gain.
- **Rollback:** not applicable; nothing merged conflicts.

**Effort, risk and timeline:**
- **Effort:** about three working days across five pull requests here, plus the site and personal work.
- **Risk: medium.** Plugin users must reinstall; doctor recognizes both plugin IDs and warns when both are
  enabled, and the release notes carry the steps. A check keyed on the old slug could go quiet after the
  GitHub rename; S4 and the release re-run each one.
- **Timeline:** S1 to S3 by 2026-09-29; the GitHub rename, S4 and the tag on 2026-09-29 or 2026-09-30.

## 4. Detailed change proposals

### 4.1 Stories

All five are new, on v0.14.0, under AH-E020:
- **S0, chore:** record this sprint change, add AD-24 and reserve the stories. This change.
- **S1, story:** add the `citizen` command and keep `harness` as an alias. Usage names the invoked command,
  both print `model-citizen <VERSION>`, and messages that suggest a command say `citizen`.
- **S2, story:** rename the plugin and marketplace to `model-citizen`; doctor accepts either ID and warns
  when both are enabled; the install doc carries the migration steps.
- **S3, story:** move the living copy to Model Citizen and command examples to `citizen`, with one "Formerly
  Agent Harness" line in the README and the docs index. The Gate block and CI keep `bin/harness`.
- **S4, chore:** after the GitHub rename, point hardcoded links at the new slug and site, set the About
  homepage and topic in `product.json`, and add a `retired-name` lint rule with an allowlist.

### 4.2 PRD, in S3

- **The product name** becomes Model Citizen, with a note that it was formerly Agent Harness.
- **FR text that names the command** reads `citizen`, noting `harness` as the alias. No requirement changes
  meaning, so no FR is superseded.
- **The directory `prd-agent-harness-2026-09-23/` stays.**
- Through `bmad-prd`'s update intent, with a memlog entry.

### 4.3 Product brief, in S3

- **The name** becomes Model Citizen.
- **The positioning line** changes only once the maintainer picks one; until then it stays.
- Through `bmad-product-brief`'s update intent, with a memlog entry.

### 4.4 Architecture spine, in this change

- **AD-24, The brand is Model Citizen; stable identifiers keep agent-harness** [PLANNED: v0.14.0, #875]:
  - the brand and slug are Model Citizen and `model-citizen`;
  - `citizen` is the command and `harness` a supported alias with no deprecation, `bin/harness` staying the
    real file;
  - the plugin ID is `model-citizen@model-citizen`, and doctor recognizes the old one;
  - on-disk names, the `AH-` IDs, the issue map's slug, planning directory names, telemetry's
    `service.name` and dated records keep `agent-harness`.
- **Capability map:** distribution gains AD-24.
- **Diagram updates:** none.
- **Not changed:** the spine's own title and `name`, which S3 handles with the rest of the copy.

### 4.5 UX specification, in S1

- **Command names in output** become `citizen`, through `bmad-ux`'s update intent with a memlog entry.

## 5. Implementation handoff

**Scope: moderate.** New backlog items on the current milestone, with one architecture decision.

**Mapping:**
- Epic → AH-E020 → #875, v0.14.0
- S0 → AH-C078 → #876, v0.14.0
- S1 → AH-S267 → #877, v0.14.0
- S2 → AH-S268 → #878, v0.14.0
- S3 → AH-S269 → #879, v0.14.0
- S4 → AH-C079 → #880, v0.14.0

AH-S266 was skipped with `--advance`, because a sibling branch already holds it.

**Order:** S0 first; then S1, S2 and S3, with S3 after S1 so its examples run; then S4 after the GitHub
rename. Each story's design is in its story file, distilled from the approved plan.

**Recipients:**
- **Developer agent:** S1 to S4, one pull request each, each amending the document it makes stale.
- **Maintainer:** the GitHub rename, the About update, the tag, the site and every outward post, each on its
  own approval.

**Success criteria:**
- `git grep -n 'Agent Harness'` outside the allowlist prints only the "Formerly" lines.
- `bin/citizen doctor` and `bin/harness doctor` agree, and doctor recognizes both plugin IDs.
- The `retired-name` lint rule finds the old brand, slug and host only on its allowlist.
- `bmad_issue_sync.py audit` is clean after each story merges.

## Checklist record

Mode: batch.

- **1.1 Trigger:** [x] Done. The maintainer's rename decision of 2026-09-25; no story revealed it.
- **1.2 Problem and type:** [x] Done. A strategic change: the name is becoming a category noun.
- **1.3 Evidence:** [x] Done. Section 1.
- **2.1 Current epic:** [N/A] No existing epic contains the change.
- **2.2 Epic-level changes:** [x] Done. A new epic, AH-E020.
- **2.3 Remaining epics:** [x] Done. None changes scope.
- **2.4 New or obsolete epics:** [x] Done. One new; none obsolete.
- **2.5 Epic order:** [x] Done. Unchanged; S0 to S4 sequenced in section 5.
- **3.1 PRD conflicts:** [!] Action-needed in S3: the name and FR text naming the command.
- **3.2 Architecture conflicts:** [x] Done. AD-24 in this change.
- **3.3 UX conflicts:** [!] Action-needed in S1: command names in output.
- **3.4 Other artifacts:** [x] Done for the issue map, story files, `epics.md` and sprint status. [!]
  Action-needed outside this repository's planning: the site, the GitHub rename and About, under their own
  approvals.
- **4.1 Direct adjustment:** [x] Viable.
- **4.2 Rollback:** [ ] Not viable. Nothing merged conflicts.
- **4.3 MVP review:** [ ] Not needed. Decision 2 keeps the milestone whole.
- **4.4 Path:** [x] Done. Direct adjustment.
- **5.1 to 5.5 Proposal components:** [x] Done. Sections 1 to 5.
- **6.1 Checklist complete:** [x] Done.
- **6.2 Proposal accurate:** [x] Done.
- **6.3 Approval:** [x] Done. The maintainer approved the rename plan on 2026-09-25; this document is
  reviewed in its pull request.
- **6.4 Sprint status:** [x] Done. Regenerated by the sync tool in this change.
- **6.5 Handoff:** [x] Done. Section 5.

## Open items

- **The UX specification's brand lines** (two in `DESIGN.md`, one in `EXPERIENCE.md`) and the architecture
  spine's own title and `name`, which the plan does not place, go to S3 (#879) with the PRD and the brief as
  living copy. S1 changes only the UX specification's command names.
- **The positioning line** for the product brief and the announcement is the maintainer's to choose.
