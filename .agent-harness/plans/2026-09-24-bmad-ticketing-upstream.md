# BMad ticketing: GitHub-store fix and reconcile pitch upstream, gated adoption here

> **Verdict.** This plan ends at the pitch: one issue-first bug fix that makes GitHub publishing safe to rerun, plus a feature request for a tree-to-tracker reconcile check, all in upstream's own channels. Our side files an adoption epic whose gate follows upstream's roadmap; the spike and the reconcile build each get their own round once their gate opens.
> **Decided 2026-09-24.** Recommendations 2–5 taken · decision 1: a new session runs this, not the peer · one confirmation stop, all drafts batched, before any issue or PR is created.
> **Effort** ~1 agent-day · **Risk** low: two small texts and a ~12-line prose fix · **Blast radius** one preview skill's config upstream; one epic file here

## At a glance

- **Outcome** — upstream has a reproduced bug with a fix PR and a reconcile proposal awaiting a
  maintainer; agent-harness has an epic that says exactly when we switch.
- **Approach** — repro first; "v7 preview" bug issue, then a PR that fixes it; feature-request issue
  and a Discord intro for reconcile; our epic records the gate.
- **Touches** — fork `JakeSelby/BMAD-METHOD` (`config/gh-ticketing.toml` only); agent-harness
  `_bmad-output/` (1 epic); a private sandbox repo.
- **New deps** — None. gh CLI 2.94 or later locally (2.93.0 installed).
- **Not in scope** — building reconcile or branch-safe ids before a yes; the spike; porting
  `bmad_issue_sync.py`; migrating our 433 mapped issues.
- **Exit test** — bug issue and PR open on upstream with CI green; feature request open; the
  maintainer's reply, or the silence, recorded in our epic.
- **Open question** — none; all five decisions settled on 2026-09-24.

## System design

```text
sandbox repo ── repro ──▶ *bug issue ──▶ *PR 1 (fork → dev) ──▶ maintainer
ticket tree ── write ──▶ *create, content only ── number ──▶ tracker_id
                              └─▶ *parent · blocked-by, if missing
*feature request + Discord ┄┄ yes ┄┄▶ later round: tickets.py reconcile
agent-harness: issue-map + bmad_issue_sync.py ┄┄ gate ┄┄▶ *adoption epic
```

`*` = new or changed. Dotted links wait on someone else: the maintainer's yes, upstream's roadmap.

## Steps

1. **[Reproduce the duplicate](#step-1--reproduce-the-duplicate)** — gh 2.94+ against a private sandbox repo; also test whether setup's `gh label create --force` wipes an existing label.
   *Exit:* issue exists, exit code ≠ 0, no URL printed; transcript saved; label result noted as a yes or no.
2. **[File the bug issue](#step-2--file-the-bug-issue)** — bug-report template, title starting "v7 preview:", repro and gh's source lines; exact text for your go.
   *Exit:* your go; issue open on `bmad-code-org/BMAD-METHOD`.
3. **[Fork and baseline](#step-3--fork-and-baseline)** — fork to `JakeSelby/BMAD-METHOD`, clone to `~/repos/BMAD-METHOD`, `upstream` push-disabled, worktree off `upstream/dev`.
   *Exit:* `uv run --frozen pre-commit run --all-files` green on untouched `dev`.
4. **[Make publishing rerun-safe](#step-4--make-publishing-rerun-safe)** — `[verbs].write` lines 50-56 only; the body rule #2944 rewrites stays untouched.
   *Exit:* gates green; forced relation failure, publish run twice: one issue per ticket in 3 of 3 runs, baseline duplicates.
5. **[Open PR 1](#step-5--open-pr-1)** — What/Why/How/Testing under 200 words, `Fixes #<bug>`, the independent build-out and harness link.
   *Exit:* your go on the text; PR open against `dev`; `quality` green on ubuntu and windows.
6. **[Pitch reconcile](#step-6--pitch-reconcile)** — feature-request issue (reconcile, with branch-safe ids as an offer) and a three-sentence Discord intro.
   *Exit:* your go on both; issue open; you post in Discord; nothing is built before a maintainer's yes.
7. **[File our adoption epic](#step-7--file-our-adoption-epic)** — `bmad_issue_sync.py new` then `reserve`; blockers and five gate conditions; PR merged, `/land`.
   *Exit:* epic mapped in `issue-map.json`; `bmad_issue_sync.py audit` clean; upstream links recorded.

## Decisions for the reviewer

> **1. Which session runs this?**
> *Recommend* the peer `bridge-cse-015hyoaxenpjgu8qqxkns4tj-33`, which was handed the same work; this one is past its context threshold.
> *Alternative* this session, which holds the reasoning, at a higher cost per turn from here on.

> **2. Bug issue plus a ~12-line PR, or the issue alone?**
> *Recommend* both: CONTRIBUTING routes bugs through issues and says a small fix can "Just open the PR", so he gets something to merge or copy.
> *Alternative* issue only: no outside ticketing PR has merged yet, and he writes most of this skill himself.

> **3. What goes in the pitch?**
> *Recommend* reconcile as the ask, branch-safe ids as a one-line offer: both are lessons our sync paid for.
> *Alternative* reconcile alone, for the narrowest ask; or add native issue types, which we'd be inventing rather than bringing.

> **4. Our side: epic and gate now, spike later?**
> *Recommend* yes: upstream says bmad-build and sprint-planning don't read the ticket tree yet, so a spike now tests nothing that runs.
> *Alternative* spike now on the preview as it stands, for an early read on IDs and acceptance criteria.

> **5. A private sandbox repo on your account?**
> *Recommend* `JakeSelby/bmad-ticketing-sandbox`, private, deleted once PR 1 closes.
> *Alternative* an org-owned repo, which would also allow native issue types later.

## Risks

- **#2944 merges first and rewrites `write`** — rebase PR 1; the change sits in lines #2944 leaves alone.
- **He fixes it in his own branch instead** — close PR 1 with thanks; the issue did its job.
- **Step 1 does not reproduce** — no bug issue or PR; the pitch leads with reconcile alone.

---

# Addendum

## What we can bring upstream (question 1)

Sources: upstream `dev` at `29372f4`, the open PRs #2944–#2949, gh v2.101.0 source, and the other
session's digests in `/tmp/carve-715/` (`bmad-ticketing.md`, `bmad-contrib.md`, `ours-mechanics.md`).
The store is prose: `config/gh-ticketing.toml` holds the `setup`, `write` and `query` verbs the agent
runs with `gh`; `tickets.py` handles the local tree only and never touches a tracker.

- **U1, rerun-safe publish: bug, in this plan.** gh `pkg/cmd/issue/create/create.go:482-495` creates the
  issue, then resolves and applies `--type`, `--parent` and `--blocked-by`; on an error it returns
  before `fmt.Fprintln(opts.IO.Out, newIssue.URL)`. Upstream puts both relations on the create call
  (`gh-ticketing.toml:51-52`) and mirrors `tracker_id` only after a successful write (`:61-62`); no
  lookup, marker or dedupe exists anywhere. Triggers: a stale parent number, GHES below 3.19, a
  secondary rate limit in an at-inception burst. Milestone creation has no existence check (`:58`).
  Our lessons: bare POST, then relations in separate calls (`create_issue:1594`,
  `apply_manifest:1189-1213`); a failure after filing names the filed issue (`:1608`); GitHub's list
  endpoint trails a POST (AH-B040, #392).
- **U2, reconcile: feature, pitched here, built in a later round.** Upstream compares one ticket at a time
  ("A body that differs from the file: show and ask", `board.md:25`) and adopts only children of a
  queried parent (`gh-ticketing.toml:73`); parentless outside issues and whole-tree drift are not
  addressed, and hooks are not integrated, so drift accumulates between runs. Ours: `live_findings:780`
  and triage-gated adoption (`accepted_for_delivery:760`).
- **U4, branch-safe ids: offered in one line.** "Cross-branch collisions: nothing in the skill addresses
  them"; `tickets.py` only detects duplicate ids after the fact (`tickets.py:216-217,266-267,326-329`).
  Our `survey_ids_elsewhere:1307` reads the map in every worktree and branch before allocating. This
  corrects round 1, which called the survey moot.
- **Candidate second bug, only if step 1 confirms it.** Setup runs `gh label create <name> --force` with
  no colour or description (`gh-ticketing.toml:44`), which may rewrite a repository's existing `bug`
  label. One fix per PR: it would be its own issue.
- **Not offered.** Native issue types (U3): upstream types by label and we have no lesson to bring, only
  a projection mode. Sub-issues and reparenting: already upstream, and `--add-sub-issue` passes
  `replaceParent: true` (`api/queries_issue.go:689`). PR closing links: bmad-build is mid-rewrite in
  #2944. The managed body block and sprint-status render: upstream's design removes the need.

## Why we can't adopt yet, and what changes here (question 2)

1. **Upstream says it isn't ready.** "While ticketing is in preview, `bmad-create-epics-and-stories` with
   `bmad-sprint-planning` remains the supported route"; its stories "are not read by
   `bmad-sprint-planning`, do not appear in `sprint-status.yaml`, and the current `bmad-build` does not
   move their status (YET)"; "Hooks are not integrated yet". No graduation procedure or stability promise.
2. **Not released.** Installs only through `npx skills add ... --skill bmad-preview-ticketing` and
   `bmad setup`; npm `latest` is 6.12.0; we pin `bmad-method` at 6.12.0 (`docs/bmad.md:15-19`).
3. **Mid-rewrite.** #2944 is part one of four on `feat/integrate-build-skills-with-ticketing`; the other
   parts move bmad-build, review and retrospective onto the tree and remove the sprint-status route.
4. **Missing guards.** U1 and U2; our required `issue-ownership` check and the daily live audit need both.
5. **Layout and identity.** All three checks read `issue-map.json` and flat `AH-*.md` files
   (`check_issue_ownership.py:13,60-72`, `ci.yml:64-65`, `bmad-traceability.yml:28`); v7 uses folders,
   per-epic integer ids and `tracker_id` frontmatter. The map holds 433 items.
6. **Fits with customisation.** Acceptance criteria can stay local by editing our copy of `write`
   ("edits survive skill updates", `store-setup.md:6`); `tracker_status` already outranks `status` for
   board state (`SKILL.md:97`).

The migration, when the gate opens, is its own plan: pin the release, convert the 433 items with AH IDs
kept as aliases, re-point the three checks, customise `write`, and retire the overlapping commands in
`bmad_issue_sync.py`.

## Step 1 — Reproduce the duplicate

```sh
brew upgrade gh && gh --version            # expect 2.94 or later
gh repo create JakeSelby/bmad-ticketing-sandbox --private --add-readme
S=JakeSelby/bmad-ticketing-sandbox
gh issue create -R $S --title "repro: relation after create" --body "x" --blocked-by 999999; echo "exit=$?"
sleep 10; gh issue list -R $S --state all --json number,title
gh label list -R $S --json name,color,description | grep -A2 '"bug"'
gh label create bug -R $S --force; gh label list -R $S --json name,color,description | grep -A2 '"bug"'
```

Expected: an error resolving `--blocked-by`, a non-zero exit, no URL, and the issue listed (list again
after 30 seconds before concluding otherwise). For the label: compare colour and description before and
after. Save everything to `/tmp/bmad-research/repro.txt`.

## Step 2 — File the bug issue

Search open and closed issues for "duplicate", "publish" and "tracker_id" first. Use the bug-report
template; fill its fields from this draft. No em dash; `grep -n $'—'` before showing Jake.

```markdown
Title: v7 preview: GitHub publish files a ticket twice when a relation fails

The GitHub store's `write` verb creates each issue with `--parent` and `--blocked-by` on `gh issue create`. gh makes the issue first and adds those relations afterwards (`pkg/cmd/issue/create/create.go`, `DeferredUpdateIssue`), and it prints the url only when both succeed. When the relation step fails, the issue exists but `tracker_id` is never written back, so the next publish creates the ticket again.

Steps to reproduce: with gh 2.94 or later, run `gh issue create --title test --body x --blocked-by 999999`. It exits non-zero and the issue is there anyway.

Expected: one issue, recorded in the ticket file. Actual: an orphan issue, and a second one on the next publish.

Environment: gh <version>, Claude Code with <model>, bmad-preview-ticketing at <sha>.
```

## Step 3 — Fork and baseline

```sh
gh repo fork bmad-code-org/BMAD-METHOD --clone=false
git clone https://github.com/JakeSelby/BMAD-METHOD.git ~/repos/BMAD-METHOD && cd ~/repos/BMAD-METHOD
git remote add upstream https://github.com/bmad-code-org/BMAD-METHOD.git
git remote set-url --push upstream no_push && git fetch upstream dev
harness worktree create ticketing-gh-publish-rerun ~/repos/BMAD-METHOD \
  --branch ticketing-gh-publish-rerun --base upstream/dev   # check --help for the repo argument
uv sync --frozen && uv run --frozen pre-commit run --all-files --show-diff-on-failure
```

Never commit to the fork's local `dev` or `main`. A red baseline is upstream's: record the hook and stop.

## Step 4 — Make publishing rerun-safe

Edit only `[verbs].write`, dev lines 50-56. Lines 57-64 stay: #2944 rewrites 59-60, and a touching edit
would conflict. Target wording, cut to fit the file's style:

```text
One issue per new ticket, created in tree and prerequisite order so every relation has a number to point at.
An initiative's milestone must exist first: look for it with `gh api repos/{owner}/{repo}/milestones?state=all`,
and create it only when missing.
Create with content only: `gh issue create --title <t> --body-file <b> --label <type>,<[tickets.status].<state>>
[,hitl,risk:<r>,P<n>] [--milestone <initiative>]`, and write tracker_id and remote from the url it prints
before anything else. Then `gh issue edit <n> --parent <n> --add-blocked-by <n,n>`, leaving out what
`gh issue view <n> --json parent,blockedBy` already shows. Relations stay off the create: gh adds them after
the issue exists, and when that fails it exits non-zero without printing the url, so a retry files the ticket twice.
A create that fails: before creating again, look for the ticket among the newest issues
(`gh issue list --state all --limit 20 --json number,title,body`, matching the body's id and parent lines),
twice a few seconds apart, since the list can trail a create.
```

The body keeps the frontmatter's `id` and `parent` lines (only five are stripped), so the lookup needs no
marker. Eval in `/tmp/bmad-sandbox-project` (`git init`, outside every repository): install the preview
per `docs/plan/help-test-v7-previews.md:29-32`, record the SHA, `bmad setup` with the GitHub starter and
`repo = "JakeSelby/bmad-ticketing-sandbox"`. Tree: one epic, two stories, story 2 `after` story 1; force
the failure by setting the epic's `tracker_id` to 999999. A trial is two identical headless Claude Code
runs asked to publish the epic; count issues per ticket, then `gh issue delete` them. Three trials with
the current verb, three with the patched one in `_bmad/custom/ticketing-store-config.toml`. Record the
model and gh version.

## Step 5 — Open PR 1

Commit `fix(ticketing): make GitHub publishing safe to rerun` with the Co-Authored-By trailer; run the gate
on `HEAD`. Show Jake the body with real numbers; flag the first-person lines; no em dash.

```markdown
## What
Publishing to GitHub can now be rerun without filing a ticket twice. The issue is created with content only, its number goes into the ticket file straight away, and parent, blocked-by and milestone are added afterwards when missing.

## Why
Fixes #<bug>. `gh issue create` applies `--parent` and `--blocked-by` after the issue exists, and when that step fails it exits non-zero without printing the url, so `tracker_id` is never written and the next publish creates the issue again.

## How
- `write` creates with title, body, labels and milestone, then mirrors `tracker_id` and `remote`.
- Relations go on with `gh issue edit`, skipping any that `gh issue view` already shows.
- A failed create is looked up among the newest issues, twice, before any retry.

## Testing
With a forced relation failure, publishing one epic twice left <n> issues per ticket before this change and one after, in three runs each (gh <version>, <model>).

I found this comparing the preview with a BMad-to-GitHub sync I built independently for my agent harness (https://github.com/JakeSelby/agent-harness), which tracks 433 issues.
```

After the go: `git push -u origin ticketing-gh-publish-rerun`; `gh pr create --repo
bmad-code-org/BMAD-METHOD --base dev --head JakeSelby:ticketing-gh-publish-rerun --title "<subject>"
--body-file <approved body>`. CodeRabbit and Greptile will comment: check each against the code, then
draft a reply or a fix for Jake's go.

## Step 6 — Pitch reconcile

Feature-request template (Describe your idea / Why is this needed? / How should it work? / PR /
Additional context). Draft:

```markdown
Title: v7 preview: reconcile the ticket tree with the tracker

Describe your idea: a read-only check that compares the ticket tree with the tracker and lists what drifted.

Why is this needed? `query` reads one ticket, a container's children or a word search. Nothing shows a tracker item that is missing, closed on one side only, reparented, blocked by something `after` no longer names, filed twice, or filed outside BMad with no parent. With hooks not integrated yet, that drift builds up between runs.

How should it work? `tickets.py reconcile <folder> --tracker <listing>`. Each store's `query` verb gains a sentence on producing the listing (number, state, parent, blocked-by, labels, and the id and parent lines from the body), and `tickets.py` compares it with the tree and prints JSON grouped by kind of drift. Fixing stays with `write` and the user.

PR: under 400 lines with tests, once the shape suits you.

Additional context: I run an independent BMad-to-GitHub sync in my agent harness (https://github.com/JakeSelby/agent-harness) that makes this check daily across 433 issues. It also taught me that ids handed out on two branches at once collide, so it surveys every branch before allocating one; I can propose that separately.
```

Discord intro for Jake to post at https://discord.gg/gk8jAdXWmj:

```markdown
Hi, I'm Jake. I run BMad against GitHub Issues through a sync I built independently for my agent harness (https://github.com/JakeSelby/agent-harness), and I'd rather put what it taught me into the ticketing preview than keep a parallel tool. I filed #<bug> with a small fix in #<pr>, and #<feature> proposes a reconcile check between the tree and the tracker: would that shape work for you before I write it?
```

Record the date and the gist of any reply in our epic. A yes starts a new plan round for the build: on
`dev` after #2944 merges, six drift classes (missing on the tracker, unknown to the tree, filed twice,
open/closed disagreement, parent disagreement, blocked-by against `after`), one fixture each in
`scripts/tests/test_tickets.py`, 400 lines at most.

## Step 7 — File our adoption epic

In a worktree cut from a freshly fetched `origin/main`: `harness worktree create bmad-ticketing-adoption
--base origin/main`. File with `scripts/bmad_issue_sync.py new`; it reports "filed but not reserved" on
list lag every time, so run `reserve --issue N --kind epic` at once. Label `type::epic`; no release
milestone. The body carries the six points of question 2 and the gate:

1. bmad-build and sprint planning read the ticket tree (#2944's four parts merged).
2. A tagged BMad release ships the ticketing skill through npm.
3. U1, or an equivalent, is in that release.
4. A reconcile check is in it, or we keep `bmad_issue_sync.py audit --live` beside it.
5. A spike, planned when 1 to 4 hold, re-points our three checks and keeps AH IDs findable.

The PR carrying the epic file closes nothing (the epic stays open), so it needs its own chore issue:
file it the same way and put `Closes #<chore>` in the body. If `main` re-derives the epic under
another ID, take `main`'s and re-run the audit.

## Working rules for the implementing agent

- **Coordination:** a new session owns this work. Before creating anything, check for a fork, a sandbox
  repo, or issues and PRs by JakeSelby upstream. Earlier research is in `/tmp/carve-715/`.
- **Stops:** one, before the first issue or PR is created, showing every draft at once (bug issue, PR 1
  body, feature issue, Discord intro, our epic and chore issues, our PR body) with `#<n>` placeholders
  filled in as items are created. Stop otherwise only for a decision, a failed gate you cannot fix, or a
  `trust_check` at L1 or L2.
- **Skills, in order:** `upstream-contribution` (steps 2-6), `worktree-per-agent` (steps 3 and 7), a
  `builder` agent for step 4 (gate and local commit, never a push), `land` after our PR merges,
  `handoff` at the end.
- **Governance:** `trust_check` before `gh repo create`, `gh repo fork`, each `gh issue create`, commit, push
  and `gh pr create`, and `bmad_issue_sync.py new`; `action_log` after each.
- **Outward-facing:** every issue, PR body, Discord line and bot reply is exact text with Jake's go per
  item, no em dash, first-person lines flagged.
- **Upstream gate:** `uv sync --frozen && uv run --frozen pre-commit run --all-files
  --show-diff-on-failure`; CI adds windows-latest. **Our gate:** `python3 bin/harness lint && python3 -m
  unittest discover -s tests`, read by exit code.

## Evidence and verification

- **Read directly:** upstream `config/gh-ticketing.toml`, `SKILL.md`, `references/board.md`,
  `references/store-setup.md`, `assets/story-template.md`, `CONTRIBUTING.md:32-95`, the PR template,
  the pre-commit hook ids; gh v2.101.0 `create.go:455-545`, `queries_issue.go:538-562,677-689`,
  `edit.go:265-274`; gh 2.94.0 release notes; npm dist-tags; `issue-map.json` counts.
- **From gatherers and the other session's digests, not re-read line by line:** our sync's line
  references, #2944's store hunks, #666 and #1668 quotes, the merge history of outside PRs, the
  preview's stated limitations.
- **Merge reality:** no outside ticketing PR has merged; five from one contributor opened on 09-24, none
  yet reviewed by a person; outside merges to date took a median of about ten days.
- **Not verified yet:** the duplicate on a live repo and the label rewrite (step 1); whether
  `--add-blocked-by` errors on an existing relation; whether `tickets.py find` can resolve an alias.

## Deferred, and why

- **Building reconcile or branch-safe ids:** waits for a maintainer's yes; then its own plan round.
- **The spike and the migration:** wait for gate conditions 1 to 4.
- **Porting `bmad_issue_sync.py` or shipping it as a module:** fails the 800-line rule, reads our v6
  layout, competes with the maintainer's store; a community module, `bmad-issue-tracking`, exists.
