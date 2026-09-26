# Model Citizen rename, shipped as v0.14.0

> **Verdict.** Renames Agent Harness to Model Citizen wherever the name is living copy or a public address, and ships the repository side as v0.14.0. The brand, a new `citizen` command, the plugin ID and the repo slug change; on-disk names, `AH-` IDs and dated records keep `agent-harness`, `harness` stays as an alias, and GitHub plus a CloudFront 301 carry every old link.
> **Effort** ~3 working days, about 12 PRs in 5 repos · **Risk** med — plugin users must reinstall · **Blast radius** plugin installs, old links, slug-keyed checks
> **Changed this round.** Step 6 adds a site-wide "formerly agent-harness" banner · step 1 found a US podcast mark in class 9 and Jake chose to proceed · Decision 2 settled: the rename ships inside v0.14.0.

## At a glance

- **Outcome** — Every living surface says Model Citizen, `citizen` runs everything `harness` does, model-citizen.dev serves the site over HTTPS, old URLs redirect, and v0.14.0 ships under the new name.
- **Approach** — Change 209 living files and keep 666 dated or on-disk ones; rename on GitHub; delegate the domain to Route 53 and 301 the old host; outward text goes out only on Jake's go per item.
- **Touches** — This repo, its site, jakeselby-com, ruleprobe and its site; GitHub; GoDaddy and Route 53; outreach and the maintainer's own setup, tracked outside this repository.
- **New deps** — None. One Route 53 hosted zone for model-citizen.dev.
- **Not in scope** — Renaming on-disk paths, `~/repos/agent-harness`, `AH-` IDs, telemetry's `service.name` or dated records; publishing to PyPI or npm (nothing publishes today, and a placeholder is squatting); editing posts already published.
- **Exit test** — A new lint rule finds the old brand and slug only on its allowlist; old repo and site URLs 301; model-citizen.dev returns 200; the gate, `sync_about.py --check`, the drift check and the card check are green.
- **Open question** — None. Decision 2 is settled (inside v0.14.0); 1, 3, 4 and 5 stand as recommended.

## System design

```text
 PRs A-D ── *citizen, *plugin ID, *copy, *slugs ──▶ main ──▶ *v0.14.0
 GitHub agent-harness ── *rename; old URLs 301 ──▶ *model-citizen
 GoDaddy ── *NS delegation ──▶ *Route 53 zone model-citizen.dev
 *zone ── ACM cert, alias records ──▶ CloudFront site (same stack)
 agent-harness.jakeselby.com ── *301 by Host ──▶ model-citizen.dev
 product.json ── sync_about --apply ──▶ About: homepage, topics
 jakeselby.com card, ruleprobe ── *copy and links ──▶ new name
 outreach ┄┄ maintainer's go per item ┄┄▶ new name
 on-disk names, AH- IDs, telemetry, dated records ── kept ──▶ as is
```

`*` = new or changed. The site keeps its bucket, distribution and stack; only names, aliases and the certificate move.

## Steps

1. **[Re-screen the name and run the EU and UK knockouts](#step-1--re-screen-the-name)** — registries, TSDR, TMview, UKIPO; read-only.
   *Exit:* every name is still free and no live identical mark sits in class 9 or 42, or the plan stops here.
2. **[Delegate model-citizen.dev to Route 53](#step-2--delegate-the-domain)** — zone-only deploy in agent-harness-site (G1); nameservers at GoDaddy by Jake (G2).
   *Exit:* `dig +short NS model-citizen.dev @8.8.8.8` returns the four `awsdns` servers.
3. **[File the rename's issues and amend the corpus](#step-3--issues-and-corpus)** — `bmad-correct-course`, one epic and five stories on the v0.14.0 milestone.
   *Exit:* `python3 scripts/bmad_issue_sync.py audit` is clean and each story's issue sits on the v0.14.0 milestone.
4. **[PR A: `citizen` with `harness` as an alias. PR B: plugin ID](#step-4--pr-a-and-pr-b)** — `bin/`, `lib/`, `policy/hooks/`, `.claude-plugin/`, doctor, tests.
   *Exit:* `bin/citizen doctor` and `bin/harness doctor` agree, doctor recognizes both plugin IDs, and the gate is green.
5. **[PR C: living copy](#step-5--pr-c-living-copy)** — README, docs, product.json, AGENTS.md, primitives and their projections, the BMad amendments.
   *Exit:* `git grep -n 'Agent Harness'` outside the allowlist prints only the "Formerly" lines; `bin/harness generate --check` passes.
6. **[Serve the site at model-citizen.dev](#step-6--site-and-brand)** — certificate, aliases, a Host-based 301, Astro `site`, a "formerly agent-harness" banner on every page, the OG card and a wordmark (G3, G22).
   *Exit:* the apex returns 200; the old host and www return 301 to the same path on the apex; the smoke check finds the banner on every page.
7. **[Rename on GitHub, fix slugs, release v0.14.0](#step-7--switch-and-release)** — G4, PR D with the retired-name lint rule, About (G7), tag (G8), site repin and card (G9).
   *Exit:* old URLs 301, `sync_about.py --check` and `advance_stable.py --check` pass, and the site serves v0.14.0.
8. **[Outreach](#step-8--outreach)** — public listings and announcements, tracked outside this repository.
   *Exit:* every public listing shows the new name and link.

## Decisions for the reviewer

> **1. Command: make `citizen` the command and keep `harness` as a permanent alias?**
> *Recommend* yes — no Homebrew, PyPI or npm package installs a `citizen` binary, `harness` collides with Harness Inc.'s CLI, and adding a command is a minor; removing `harness` would need a major plus 90 days' notice, so announce no deprecation.
> *Alternative* keep `harness` alone — zero churn, but the brand and the command never match.

> **2. Version and timing: ship the rename inside the full v0.14.0 milestone, as a minor?**
> *Recommend* yes — v0.14.0 is the roadmap's Switchable milestone and v0.15.0 its Measured one, so moving issues out would collide with it; the repo, site and filings still switch before 2026-09-30, and only the tag and announcement wait.
> *Alternative* cut v0.14.0 around the rename as soon as its PRs merge, and renumber the roadmap's milestones up by one.
> *Decided* inside v0.14.0 (Jake, 2026-09-25).

> **3. Domains: serve the site at the apex model-citizen.dev, and skip a backorder on modelcitizen.dev?**
> *Recommend* yes — the hyphenated slug is the name everywhere, www and the old host 301 to the apex, and a backorder pays only if the owner lets it lapse (it expires 2026-10-28 at Dynadot).
> *Alternative* serve at docs.model-citizen.dev to keep the apex for a later landing page, and backorder as cheap insurance against a typo squatter.

> **4. Discovery and launch: keep the `agent-harness` topic, and announce the rename once with v0.14.0 on X and LinkedIn, folding in the unposted v0.13 thread?**
> *Recommend* yes — "agent harness" is the category people search, so swap `coding-agent` (a near-duplicate of `ai-coding-agent`) for `model-citizen`; one launch beats a thread under a name retired a week later.
> *Alternative* drop the old topic for a clean break, and post the v0.13 thread renamed now with a separate rename post.

> **5. Trademark: run the EU and UK knockouts in step 1 and file nothing yet?**
> *Recommend* yes — the US screen is clear in classes 9 and 42, and clearance and filing cost real money before there are users to protect.
> *Alternative* an attorney's clearance and a US intent-to-use filing in 9 and 42 now, which locks a priority date before another agent tool takes the name.

## Risks

- **Claude Code keeps existing installs on the old plugin ID** — doctor recognizes both IDs and warns when both are enabled, and the release notes carry the reinstall steps.
- **Nameserver delegation or certificate validation stalls** — the certificate deploys only once `dig NS` shows Route 53, and the old host keeps serving until then.
- **A check keyed on the old slug goes quiet** (site drift, card check) — each is changed before the rename and re-run after it in step 7.

---

# Addendum

Everything the implementing agent needs and the reviewer does not. Nothing above the rule is
repeated here. G-numbers are the gated outward items in [Gated outward steps](#gated-outward-steps).

## Working rules for the build

- Each G item needs Jake's go for that item alone. Approving this plan approves none of them. Show
  the exact text or command, then wait. He also asked to be checked with before any list
  submission is filed, even inside an approved plan.
- Deploys are gated per instance, always. A tag, a release and `sync_about.py --apply` keep their
  own approvals.
- Consequential actions (commit, push, merge, deploy) go through the trust check and are logged,
  per the global rules. No agent graduates trust.
- Copy in the maintainer's name, including PR and issue bodies, carries no em dash.
- Delivery follows `docs/bmad-governance.md`: one issue per PR, reserved in
  `_bmad-output/issue-map.json`, `Closes #N` in the body, CodeRabbit worked through per AGENTS.md.
- Never create a repository named `agent-harness` after G4; it would break every redirect.

## Step 1 — Re-screen the name

The screen is a day old and agent tools claim names monthly, so re-run it before anything public.

- Registries, expected codes: `curl -s -o /dev/null -w '%{http_code}\n' <url>` for
  `https://pypi.org/pypi/model-citizen/json` (404), `https://registry.npmjs.org/modelcitizen` (404),
  `https://github.com/JakeSelby/model-citizen` (404). npm `model-citizen` is taken and stays out of
  scope.
- US: re-run the knockout in `.agent-harness/diagrams/brand/naming-trademark-screen.md` (main
  checkout, untracked). `https://tsdr.uspto.gov/statusview/sn<serial>` works with curl where
  uspto.report and Justia return 403. Known: 90977894 MODEL CITIZEN is dead (class 41);
  88899582 MODEL CITIZENS is live in class 35 (a car club), outside 9 and 42.
- EU and UK: TMview (`tmdn.org/tmview`) word search "MODEL CITIZEN", classes 9 and 42, live marks
  across EUIPO and the national offices; UKIPO "search for a trade mark" by word. Both are
  script-heavy; drive them with Playwright (Chromium is installed) or hand Jake the two searches.
- Record results in the screen file. Stop rule: a live identical or confusingly similar mark in
  class 9 or 42 in the US, EU or UK halts the plan and goes to Jake with the record.
- **Result, 2026-09-25:** US 99552170 MODEL CITIZEN is live in classes 9 and 41 for podcasts; the
  EU is clear; the UK register is unchecked (CAPTCHA). Jake chose to proceed, and the manual UK
  search is optional.

## Step 2 — Delegate the domain

- In agent-harness-site, `infra/lib/agent-harness-site-stack.ts`, add a
  `route53.PublicHostedZone` for `model-citizen.dev` and a `CfnOutput` of its name servers. Keep
  the stack name `AgentHarnessSite` and every existing construct ID: a changed ID replaces the
  bucket or the distribution.
- G1 deploys the zone alone. G2 is Jake's nameserver change. Delegation can take up to 48 hours,
  so start both on day one, in parallel with step 3.
- Today the domain sits on GoDaddy's default nameservers with a parking page; HTTPS fails, and
  .dev is HSTS-preloaded, so nothing serves until step 6.

## Step 3 — Issues and corpus

- Run `bmad-correct-course` on the v0.14.0 sprint. The proposal records the rename, the keep list
  in [Inventory](#inventory) and the re-scope from Decision 2.
- Then `bmad-create-epics-and-stories`, and file each with
  `python3 scripts/bmad_issue_sync.py new`. `new` reports "filed but not reserved" on list lag;
  follow it with `reserve --issue N`. Reserve one at a time: two in-flight reservations conflict
  in `issue-map.json`, and the fix is to re-apply the entry in the tool's JSON format and run
  `audit`. Link each story to the epic as a sub-issue by API before merging.
- The epic, "Rename the product to Model Citizen", and five stories, each one PR with a `type::*`
  label and the v0.14.0 milestone:
  - **S0, chore** — record the sprint change and reserve the stories. A filing-only PR fails
    `issue-ownership` without its own chore issue.
  - **S1, feature** — add the `citizen` command and keep `harness` as an alias (PR A).
  - **S2, feature** — rename the plugin to `model-citizen` and keep recognizing the old ID (PR B).
  - **S3, docs** — rename the product copy to Model Citizen (PR C).
  - **S4, chore** — point hardcoded links at the new repo and domain, and add the retired-name
    lint rule (PR D, after G4).
- Amendments, each through the matching skill's update intent with a memlog entry, in the PR that
  makes the document stale: the product brief (name, and the positioning line once Jake picks
  one) and the PRD (product name, and FR text naming the command) in PR C; the UX spec (command
  name in output) in PR A; the architecture spine gains an AD in S0: the brand is Model Citizen,
  while on-disk names, `AH-` IDs, telemetry's `service.name` and dated records keep
  `agent-harness`. Directory names such as `prd-agent-harness-2026-09-23/` stay, since hundreds
  of anchors point into them.
- G6 is dropped: Decision 2 keeps the rename inside the full v0.14.0 milestone.

## Step 4 — PR A and PR B

**PR A (S1).**
- `bin/citizen` is a relative symlink to `harness`. `bin/harness` stays the real file, because the
  hooks and the installer find the checkout by that path (policy/hooks/harness-session.py
  :65,100,153,251; policy/hooks/decisions.py:297; policy/hooks/usage-log.py:169;
  scripts/install.sh:66,80), and lifecycle refusals print its absolute path
  (lib/harness_core/lifecycle.py:180-183).
- `prog` comes from the basename of `argv[0]`, `citizen` or `harness`, else `citizen`
  (bin/harness:4844); the usage docstring (:10-29) leads with `citizen`.
- The banner `agent-harness {VERSION}` becomes `model-citizen {VERSION}` at bin/harness
  :4845,1818,1243,2834,2913,3220; update tests/test_harness.py:542.
- Messages in `bin/`, `lib/` and `policy/hooks/` that name the product or suggest a command move
  to Model Citizen and `citizen`. Every path in the keep list stays.
- Tests (Python 3.9-safe): `bin/citizen --help` prints `usage: citizen` and `bin/harness --help`
  prints `usage: harness`; both `--version` print `model-citizen <VERSION>`; checkout detection
  works through either name.
- Fragment `changelog.d/<issue>.added.md`: "Added the `citizen` command; `harness` remains a
  supported alias." The body carries `Landing copy: command examples move to citizen in the copy
  PR, #<S3>`.

**PR B (S2).**
- `.claude-plugin/plugin.json` and `marketplace.json`: plugin `name` and marketplace `name`
  `model-citizen`, displayName `Model Citizen`, descriptions. URLs change in PR D, after G4.
- Doctor (bin/harness:1600-1640) accepts `agent-harness@agent-harness` and
  `model-citizen@model-citizen` as the enabled key and either marketplace name, and warns when both
  are enabled, since the skills would load twice.
- docs/runtime-installation.md:97-104 gets the install and migration steps from
  [Migration](#migration-for-existing-installs).
- tests/test_plugin_manifests.py: old ID only, new ID only, and both enabled.
- Before merging, on a scratch profile (signed-in empty profile, cwd outside `$HOME`, scrubbed env),
  install from the v0.13.1 marketplace, update to this branch, and record whether Claude Code keeps
  the old ID. The result goes in the release notes.
- Fragment `changed`: "The plugin is now `model-citizen@model-citizen`; reinstall it."

## Step 5 — PR C, living copy

- Brand text becomes Model Citizen in README.md, CONTRIBUTING.md, the AGENTS.md title, living
  docs/ pages (not docs/plans/), product.json `hero.subtitle`, primitives/instructions.md:3 (then
  `bin/harness generate` for claude/CLAUDE.md:3), codex/config.toml.example:1, the
  docs/assets/brand/mark.svg `aria-label`, and the release title in .github/workflows/release.yml:31.
- Command examples become `citizen <subcommand>` in README, docs/, product.json (:9,71,167,172,
  204,233), primitives/ and templates/. The AGENTS.md Gate block and CI keep `bin/harness`, so the
  two stay identical.
- The lower-case category noun ("an agent harness", "the harness") stays.
- primitives/skills/harness-authoring/SKILL.md:23,80 writes `<owner>/model-citizen`; the lint
  forbids the maintainer name there.
- Re-capture docs/assets/sync-dry-run.svg as `bin/citizen sync --dry-run`, the method AH-S116 used.
- One "Formerly Agent Harness" line in README and the docs index, so searches land.
- Fragment `changed`: "Renamed the product to Model Citizen."

## Step 6 — Site and brand

- `infra/lib/agent-harness-site-stack.ts`: the domain (:16) becomes `model-citizen.dev`. The
  certificate (:42-44) covers `model-citizen.dev`, `www.model-citizen.dev` and
  `agent-harness.jakeselby.com`, validated with `CertificateValidation.fromDnsMultiZone`: the new
  zone for the first two, the jakeselby.com zone (:37-39) for the third. Aliases (:81) add the new
  names and keep the old. Add A and AAAA alias records for the apex and www in the new zone; keep
  the old host's record (:116-120).
- The 301 goes into the existing viewer-request `RoutingFunction` (:59-91), since a distribution
  takes one function per event type: when `host` is not `model-citizen.dev`, return 301 to
  `https://model-citizen.dev` plus the URI and query string.
- `astro.config.mjs:17` sets `site` to `https://model-citizen.dev`.
- The banner: a slim site-wide `<aside aria-label="Name change">` above the header in
  `src/layouts/Layout.astro`, on every page, with no dismiss control and no script. Text (G22):
  "Model Citizen was formerly agent-harness: same project, new name.", linking to the repository.
  `scripts/smoke.mjs` fails any built page without it, and it passes the design loop's contrast
  gate. It ships with the site's own rename in this step, not before, because until then every
  page still says Agent Harness. It stays until Jake removes it.
- The wordmark and OG card go through `design-loop` (designer, then design-judge): a Model Citizen
  wordmark beside the amber dial and a 1200x630 `og.png`. Run `licensing-review` on the typeface
  before any outlined glyphs ship. The dial favicon stays.
- G3 deploys once delegation resolves. Exit commands:
  `curl -sI https://model-citizen.dev/` (200),
  `curl -sI https://agent-harness.jakeselby.com/docs/` and `curl -sI https://www.model-citizen.dev/`
  (301, `location: https://model-citizen.dev/docs/` and `/`).

## Step 7 — Switch and release

In order, in one sitting:

1. G4 renames the repo. Then check the redirects:
   `gh api repos/JakeSelby/agent-harness -q .full_name` prints `JakeSelby/model-citizen`, and
   `git ls-remote https://github.com/JakeSelby/agent-harness.git refs/heads/main` matches the new
   repo. G5 (optional) renames the site repo the same way.
2. PR D (S4) changes the slug at scripts/release_notes.py:29, scripts/bmad_issue_sync.py:1618,
   scripts/install.sh:8,21, .github/ISSUE_TEMPLATE/config.yml:4,7, README.md:5,9,148,160,
   CONTRIBUTING.md:40,42,56, docs/runtime-installation.md:97, tests/test_plugin_manifests.py:63,108,
   and the plugin and marketplace `homepage` and `repository`. It changes the site URL at
   README.md:8, docs/releasing.md:8 and plugin.json:8. product.json gains
   `"homepage": "https://model-citizen.dev"` (supported at scripts/sync_about.py:55-57) and swaps
   `coding-agent` for `model-citizen` in topics (the cap is 20); tests/fixtures/gh/repo-view.json
   follows. `_bmad-output/issue-map.json:3` keeps the old slug: `planning_block` writes it into
   every issue body (scripts/bmad_issue_sync.py:649-663,719), so changing it rewrites 160 issues.
   The `retired-name` lint rule fails on "Agent Harness", the old slug and the old host outside an
   allowlist (the dated areas, the on-disk names and the "Formerly" lines), with its test. PR D is
   the first PR after the rename, so confirm CodeRabbit still posts a pass.
3. G7 applies About, then `python3 scripts/sync_about.py --check`.
4. Release v0.14.0 through `docs/releasing.md` and the five surfaces in AGENTS.md: fresh native
   evidence for every required client, the catalog, the changelog fold, release notes whose
   actions and recovery hold the migration steps, preflight in a fresh clone of the new URL, the
   tag (G8), the release workflow, and `scripts/advance_stable.py --check`.
5. Release surfaces. Site: repin to
   v0.14.0, point `scripts/drift.mjs:11,84` and `.gitmodules:3` at the new slug, then
   `git submodule sync`. Card, in jakeselby-com: `src/data/agent-harness.ts` (name and links;
   the file name stays), `src/pages/index.astro:83,224`, `src/pages/projects/index.astro:81`, the
   `/agent-harness` 301 (infra stack :78-84) now to `https://model-citizen.dev` plus a
   `/model-citizen` path, and `scripts/harness-card-check.mjs:16`; G9 deploys it.
6. ruleprobe README.md:756 and the two ruleprobe-site lines, each a small PR under that repo's own
   rules.

## Step 8 — Outreach

Outreach (the open list filings, the announcement, profile links) and the maintainer's own setup are
tracked outside this repository. Each outward item is G10 to G19 below, on its own go.

## Gated outward steps

Each needs Jake's go for that item alone. Human-only items are his to perform, with the text below.

- **G1, deploy the zone** — `cd ~/repos/agent-harness-site/infra && npx cdk diff AgentHarnessSite && npx cdk deploy AgentHarnessSite`, with the diff showing only the new zone and output.
- **G2, nameservers (Jake, GoDaddy)** — model-citizen.dev → DNS → Nameservers → Change → "I'll use my own nameservers", then the four values from `aws route53 get-hosted-zone --id <zone-id> --query DelegationSet.NameServers`.
- **G3, deploy the certificate, aliases and 301** — the G1 command, after `dig +short NS model-citizen.dev @8.8.8.8` returns those four.
- **G4, rename the repo** — `gh repo rename model-citizen -R JakeSelby/agent-harness --yes`.
- **G5, rename the site repo (optional, recommended)** — `gh repo rename model-citizen-site -R JakeSelby/agent-harness-site --yes`.
- **G6, re-scope the milestone** — dropped; Decision 2 keeps the full v0.14.0.
- **G7, About** — `python3 scripts/sync_about.py --apply`.
- **G8, tag** — the annotated `v0.14.0` tag and push from `docs/releasing.md`, after preflight in a fresh clone.
- **G9, deploy the card** — `cd ~/repos/jakeselby-com && npm run deploy`.
- **G10 to G19, outreach** — the open list filings, the plugin directory, one email reply, the announcement and
  profile links; tracked outside this repository, each on the maintainer's go.
- **G20, backorder modelcitizen.dev** — only if Decision 3 goes to the alternative.
- **G21, trademark clearance and filing** — only if Decision 5 goes to the alternative.
- **G22, the site banner text** — "Model Citizen was formerly agent-harness: same project, new name.", linking to the repository; on the maintainer's go before it ships.

## Inventory

Tracked files at main `a9968d9`, as matching lines and files from `git grep`:

- **"Agent Harness", 59 lines in 34 files** — change the 14 living lines (README, docs, product.json, `.claude-plugin/`); keep 45 in `_bmad-output/`, which are dated records.
- **"agent harness" in lower case, 17 in 9** — keep: the category noun still describes the product.
- **`JakeSelby/agent-harness`, 4,117 in 585** — change about 70 living lines in PR D; keep 4,045 in `_bmad-output/` and the issue map, which GitHub redirects.
- **`agent-harness.jakeselby.com`, 6 in 5** — change to `https://model-citizen.dev`.
- **`agent-harness@agent-harness`, 7 lines** — change to `model-citizen@model-citizen`; doctor accepts both.
- **The banner `agent-harness {VERSION}`, 6 places in bin/harness** — change.
- **`harness <subcommand>` text, 1,344 in 371** — change in about 156 living files (docs 27, primitives 19, policy 12, claude 11, lib 9, templates 5, root 5, scripts 4, others); keep the 607 lines in `_bmad-output/`, the 123 in sha256-pinned compatibility evidence, and test invocations.
- **`bin/harness`, 684 in 257** — keep: it is the alias path and the real file.
- **`~/.config/agent-harness` (44 in 23), `.agent-harness/` (163 in 74), `~/.local/state/agent-harness/`** — keep: a rename needs an automatic reversible migration or a major plus 90 days' notice.
- **launchd `com.agent-harness.*`, `# harness:` markers, the `# agent-harness` PATH and ignore blocks, CODEX_BANNER, `~/.claude/{rules,hooks}/harness`** — keep: install, uninstall and reconcile find them by exact text (remote_control.py:160,183; bin/harness:1126-1155,1470; reconcile.py:98; lifecycle.py:625).
- **Telemetry `service.name="agent-harness"`** (policy/hooks/telemetry.py:41) — keep, so existing dashboards still match.
- **BMad `project_name`, the `AH-` IDs, `prd-agent-harness-…` and `architecture-agent-harness-…` paths** — keep: IDs and hundreds of anchors depend on them.
- **`agent_harness` and `AGENT_HARNESS_*`** — none; the env vars are `HARNESS_*` and stay.
- **Totals** — 209 living files change; 666 files in dated or kept areas stay.
- **agent-harness-site** — 9 brand, 14 slug and 17 site-URL lines, 111 with paths: domain, certificate, aliases, Astro `site`, drift slug and submodule URL change; the stack, construct IDs and file names stay.
- **jakeselby-com** — 12 brand, 4 slug and 3 site-URL lines: the card, both placements, the `/agent-harness` 301 and the card check change.
- **ruleprobe** — 27 slug lines, mostly `_bmad-output/`: README.md:756 changes; the rest redirects. **ruleprobe-site** — 2 lines in tests and CLAUDE.md change.
- **GitHub** — the About homepage and the `agent-harness` topic (Decision 4); no custom social preview, so GitHub's generated card follows the rename; 151 of 160 open issues mention the name, almost all through the BMad planning block, and stay; the one v0.14.0 title naming it (#825) stays.
- **Outreach and the maintainer's own setup** — tracked outside this repository.

## Sequencing against v0.14 and the deadlines

- **Before the tag:** steps 1 to 6, then G4, PR D and G7. PR order: S0 first, then A, B and C (C after A, so its examples run), then D after G4. Site: the zone (step 2) on day one; the certificate and 301 (step 6) once delegation resolves.
- **The tag:** after PR D and G7, through the release PR in `docs/releasing.md`.
- **After the tag:** the site repin and card (G9), ruleprobe, and outreach (G10 to G19).
- **Targets, from approval on Friday 2026-09-25:** G1 and G2 on day one, since delegation is the long pole; PRs A to C and step 6 by 2026-09-29; G4, PR D, G7 and the tag on 2026-09-29 or 2026-09-30; outreach edits right after G4.
- **The deadlines:** awesome-claude-code is gated on G4 and step 6, not on a date, so whenever Jake files it, it goes in under the new name. The v0.13 thread is not posted before G18. With Decision 2 as recommended, the repo, site and filings still switch on this schedule, and only G8, G9 and G18 wait for the milestone.

## Migration for existing installs

- **Checkout installs** — nothing to do. `git pull` follows the redirect; `bin` is already on
  `PATH` through the `# agent-harness` block, so `citizen` appears; config, state and markers are
  unchanged. `git remote set-url origin https://github.com/JakeSelby/model-citizen.git` is optional.
- **Plugin installs** — `/plugin marketplace add JakeSelby/model-citizen`,
  `/plugin install model-citizen@model-citizen`, `/plugin uninstall agent-harness@agent-harness`,
  `/plugin marketplace remove agent-harness`. Skills move from `/agent-harness:<skill>` to
  `/model-citizen:<skill>`. Doctor warns while both are enabled.
- **Release notes** carry these as actions. Recovery: the checkout install is unaffected by the
  plugin change.

## Context and background

"Agent harness" is becoming a category noun, used generically by Anthropic, LangChain, OpenAI and
others. After seven naming rounds Jake chose Model Citizen on 2026-09-25 and bought
model-citizen.dev at GoDaddy the same day. The positioning, in his words: "We want agents to become
autonomous, but to make them so we have to be able to measure their behavior and ensure that they
are model citizens." Candidate lines, none approved: "Autonomy, earned."; "Agents you can count
on."; "Find out whether your models are model citizens."; "Proof your agents kept the rules."
`citizen` and "Agents you can count on" came from the assistant, not from Jake.

The first rename session's blast-radius review recommended renaming the brand and plugin ID,
keeping the on-disk names and `~/repos/agent-harness` (renaming it breaks 46 symlinks and 37
project folders and orphans the memory directory), adding a new command beside `harness`, and
finishing before the awesome-claude-code filing and the v0.13 thread. This plan checks each of
those against the code and `docs/compatibility-policy.md`. The policy's SemVer promise starts at
v1.0.0 (:10). Documented `harness` commands are stable (:12), and a minor may add
backward-compatible commands (:37). Removing one needs a notice, the next major and 90 days
(:49-55). Human-readable wording is not stable (:22). The plugin ID and repo slug are not listed.

## Evidence and verification

- **Checked on 2026-09-25:**
  - Local main equals origin at `a9968d9`. Counts are `git grep` over tracked files.
  - No Homebrew formula or cask, PyPI package or npm package installs a `citizen` binary. npm
    `citizen` 1.0.2 is a library with no bin.
  - PyPI `model-citizen` and npm `modelcitizen` return 404; npm `model-citizen` is taken;
    `JakeSelby/model-citizen` returns 404.
  - model-citizen.dev: GoDaddy nameservers and a parking page, HTTPS failing; created 2026-09-25,
    expires 2027-09-25, per RDAP. modelcitizen.dev: Dynadot, expires 2026-10-28.
  - agent-harness.jakeselby.com is CloudFront behind the Route 53 jakeselby.com zone.
  - Milestone v0.14.0 (#18): 39 open, 32 closed, no due date. The latest release is v0.13.1.
    About has no custom social preview.
  - The five filings are open with no comments.
- **Unverified:**
  - Claude Code's behaviour when a plugin or marketplace is renamed; step 4 tests it.
  - The EU and UK registers; step 1 checks them.

## Deferred, and why

- **Package registries** — nothing publishes today: there is no pyproject.toml or package.json,
  and release.yml only creates the GitHub release. A placeholder on PyPI is name squatting under
  PEP 541, so `model-citizen` on PyPI and `modelcitizen` on npm wait for the first real package.
- **On-disk names, the local checkout path, `AH-` IDs and the issue-map slug** — kept, for the
  reasons in [Inventory](#inventory).
- **The plugin and marketplace `version` fields, stuck at 0.11.1** — nothing checks them against
  VERSION; file a follow-up to add them to the release's version step.
- **A trademark filing** — per Decision 5.
