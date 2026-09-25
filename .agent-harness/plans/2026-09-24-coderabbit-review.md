# CodeRabbit review for agent-harness, with bot threads cleared before merge

> **Verdict.** Adds a `.coderabbit.yaml` so CodeRabbit reviews every PR into `main` quietly and for free, and gives `/build` a step that answers the bot's threads before a PR goes up for approval. `/land` then stops on an open thread by name, because `main-review` already blocks that merge and today `land` only learns it when `gh` refuses.
> **Effort** about half an agent-day · **Risk** low: one config file and two workflow texts · **Blast radius** `/build` and `/land` in every repo the harness serves

> **Changed this round.** Fixes happen in `/build`, in one PR (settled) · `CONTRIBUTING.md` tells outside contributors how to work with the bot · the re-review decision now answers for contributors.

## At a glance

- **Outcome** — every PR into `main` gets one CodeRabbit review, its threads are fixed or answered before you approve, and `/land` never meets a thread block by surprise
- **Approach** — a schema-validated `.coderabbit.yaml` (chill, one review per PR, prose linters off, path instructions), plus `/build` step 6 and a thread check in `/land` step 1
- **Touches** — agent-harness only: the config, `primitives/workflows/{build,land}.md` and their generated copies, a `CONTRIBUTING.md` paragraph, a changelog fragment, the story and issue map; about 9 files
- **New deps** — the CodeRabbit GitHub App, a hosted service free for public repos; nothing vendored
- **Not in scope** — Greptile, any change to the `main-review` ruleset, CodeRabbit as a required check, landing copy
- **Exit test** — gate green, the four required checks green on the PR, and CodeRabbit reviews it once you install the app
- **Open question** — whether pushes get an automatic re-review; see decision 1

## System design

```text
/build ── PR ──▶ GitHub ── PR opened ──▶ *CodeRabbit (.coderabbit.yaml)
                                               │
                                        review threads
                                               ▼
*/build step 6 ◀┄┄ waits up to 10 min ┄┄ unresolved threads
     │ fix and push, or reply; then resolve
     ▼
you approve ──▶ */land step 1: no open thread ──▶ squash merge
```

`*` = new or changed. The `main-review` rule that threads must be resolved stays as it is.

## Steps

1. **Validate the config against CodeRabbit's live schema** — `/tmp/review-bots-research/coderabbit.yaml`, done while planning.
   *Exit:* 0 schema errors and 0 unknown keys; both negative controls were caught.
2. **[File the delivery issue](#step-2--file-the-delivery-issue)** — a managed worktree, then `bmad_issue_sync.py new`, milestone v0.14.0.
   *Exit:* the issue carries `type::story`, and its ID and story skeleton exist in the worktree.
3. **[Build](#step-3--build)** — the `builder` agent adds the config, `/build` step 6, the `/land` check and the contributor paragraph, regenerates, writes the fragment and story, and makes one commit.
   *Exit:* `bin/harness generate --check` is clean in the worktree.
4. **Run the gate myself** — lint, unit tests and `generate --check` in the worktree.
   *Exit:* `lint: 0 finding(s)`, `OK` with no skips, generate clean.
5. **Review with `bmad-code-review`** — findings and how each was resolved go into the story.
   *Exit:* no unresolved high-severity finding.
6. **[Push and open the PR](#step-6--push-and-open-the-pr)** — `feat/coderabbit-review` into `main`, `Closes #N`, a `Landing copy:` line.
   *Exit:* lint, test, issue-ownership and landing-copy are green on the head.
7. **You install the CodeRabbit app** on JakeSelby/agent-harness only; it is the one step I cannot do.
   *Exit:* CodeRabbit reviews the PR; comment `@coderabbitai review` if the PR predates the install.

## Decisions for the reviewer

> **1. Should CodeRabbit re-review automatically after a fix is pushed?**
> *Recommend* no, as BMad has it — a contributor still gets a full review when the PR opens, asks for another with `@coderabbitai review`, and uses their own rate budget.
> *Alternative* yes — contributors see each fix confirmed unasked, and your ~35 PRs a day roughly double in review volume.

## Risks

- **The open-source rate limit throttles reviews at this volume** — reviews are skipped, never blocking; if it happens often, narrow `auto_review` or weigh Essentials at $24 a month.
- **A finding is wrong, or prose gets nitpicked** — `/build` replies with the reason and resolves it; two rounds at most; tune `path_instructions` from whatever recurs.
- **The bot never posts (outage or throttle)** — step 6 waits ten minutes, then says so and moves on.

---

# Addendum

## Step 2 — File the delivery issue

`trust_check` rates `coding.shell_exec`, `coding.git_commit` and `coding.git_push` at L2 for this repository, so approving this plan approves exactly the commands below and in Step 6, and nothing else. Run the first line from the shared checkout, and the rest in the worktree it prints.

```sh
bin/harness worktree create coderabbit-review --branch feat/coderabbit-review
python3 scripts/bmad_issue_sync.py new --kind story --milestone 18 \
  --title "Adopt CodeRabbit review and clear review-bot threads before merge" \
  --body-file /tmp/review-bots-research/issue-body.md
# The reservation usually lags behind the issue list; when it does:
python3 scripts/bmad_issue_sync.py reserve --issue <N> --kind story
```

The issue body is `/tmp/review-bots-research/issue-body.md`, as written. Milestone 18 is v0.14.0.

## Step 3 — Build

Spawn `builder` with this plan's absolute path, the worktree from Step 2 (it works there and creates no other), base `main`, and the Co-Authored-By trailer the tool supplies.

Allowed to touch:

- **`.coderabbit.yaml`** — copy `/tmp/review-bots-research/coderabbit.yaml` verbatim.
- **`primitives/workflows/build.md`** — add step 6, below, and add "the bot threads answered and any still open" to the report line.
- **`primitives/workflows/land.md`** — extend step 1, below.
- **`CONTRIBUTING.md`** — add the paragraph below to the end of `## Review`, as written.
- **`claude/commands/build.md`, `claude/commands/land.md`** — only through `bin/harness generate`, never by hand.
- **`changelog.d/<N>.changed.md`** — one line, following `changelog.d/README.md`.
- **`_bmad-output/implementation-artifacts/<ID>.md`** — fill every section of the story from this plan: design and decisions from the card, dev notes from this addendum.
- **`_bmad-output/issue-map.json`** — only as the sync tool writes it.
- **`.agent-harness/plans/2026-09-24-coderabbit-review.md`** — copy this plan into the worktree.

Must not touch: `product.json`, any other workflow, the rulesets, `templates/`.

New `/build` step 6, after "Push the branch and open the pull request":

> 6. **Answer the review bot**, where the repository runs one: a `.coderabbit.yaml`, a `greptile.json`, or a bot that reviewed earlier pull requests. Wait up to ten minutes for its first review of this pull request. Then take each unresolved bot thread as a finding: fix it in the worktree, rerun the gate and push, or reply with the reason it does not apply. Then resolve the thread (GraphQL `reviewThreads`, then `resolveReviewThread`). Two rounds at most; report whatever remains. A human's thread is never yours to resolve.

Addition to `/land` step 1, after "A pending, failing or stale check stops the workflow, named.":

> So does an unresolved review thread: name it and stop. A fix belongs to `/build`, before approval, and a human's thread is theirs to resolve.

The paragraph for the end of `CONTRIBUTING.md`'s `## Review` section:

> CodeRabbit also reviews every PR into `main`, forks included, once when it opens. Treat its comments as you would a reviewer's: push a fix, or reply with why one doesn't apply, then resolve the thread, because `main` won't merge while a review thread is open. Comment `@coderabbitai review` for another pass after you push. Its comments are advice, and where you disagree with it, the maintainer decides.

The commit is `feat(workflows): adopt CodeRabbit review and clear bot threads before merge`. Its body has three bullets (the config, `/build` step 6, the `/land` check), then `Closes #<N>`, then the trailer. It uses no em dashes, because it is published under Jake's name.

## Step 6 — Push and open the PR

Before pushing, run the `trust_check` for `coding.git_push`.

```sh
git push -u origin feat/coderabbit-review
gh pr create --base main --head feat/coderabbit-review \
  --title "feat(workflows): adopt CodeRabbit review and clear bot threads before merge" \
  --body-file <body file outside the worktree>
```

The body follows `.github/PULL_REQUEST_TEMPLATE.md`:

- **What and why** — the issue's three scope bullets.
- **Where it lands** — the files.
- **Checklist** — ticked honestly.
- `Closes #<N>`.
- `Landing copy: none; /build and /land gain a step, not a new capability.`
- The generated-with line.

No em dashes.

## Evidence and verification

- **Config:** 0 errors against `https://coderabbit.ai/integrations/schema.v2.json` (jsonschema in a temp venv), and 0 keys missing from the schema. The schema allows extra properties, so the key walk is the check that bites. Its control flagged `reviews.not_a_key`, and the enum control flagged `profile: loud`. `mode: "off"` is quoted because YAML 1.1 reads a bare `off` as false.
- **Generated projections:** `claude/agents/`, `claude/commands/` and `claude/CLAUDE.md` are generated (`lib/harness_core/catalog.py`, near line 420). `claude/rules`, `claude/skills` and `claude/stances` are symlinks into `primitives/`. That is why the path filters drop the first three and review `primitives/`.
- **Ruleset:** `main-review` sets `required_review_thread_resolution: true` and requires 0 approvals, with bypass for admins only. `/land` merges with a plain `gh pr merge --squash --delete-branch`, which refuses a blocked merge unless given `--admin`.
- **Pricing, eligibility and the BMAD-METHOD#2957 evidence:** `/tmp/review-bots-research/digest.md`.

## Revision history

- **Round 1, 2026-09-24:**
  - Settled: bot findings are fixed in `/build` before approval, and config and workflows ship as one PR.
  - Jake asked how the bot works for outside contributors. The answer:
    - CodeRabbit reviews fork PRs; it reviewed Jake's own fork PR, BMAD-METHOD#2957.
    - A PR's author can resolve its conversations.
    - Rate limits count per developer identity.
    - BMad's own config also sets `auto_incremental_review: false`.
  - Added the `CONTRIBUTING.md` paragraph so contributors know the loop.

## Deferred, and why

- **Greptile:** free only through its open-source programme, which requires attesting the repo is not part of a commercial product. That is Jake's call, and one bot is enough to start.
- **A `.coderabbit.yaml` in `templates/repo/`:** wait until this one has run for a couple of weeks.
- **Codex automatic review as a second reviewer from a different model family:** reconsider after measuring CodeRabbit's hit rate.
