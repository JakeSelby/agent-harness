# Trajectory — r1-1

Fetched 2026-09-21 via `gh api graphql` (GitHub GraphQL v4). Commit counts are
`defaultBranchRef.target.history(since:"2026-08-22T00:00:00Z").totalCount`. Maintainership is
derived from the author distribution of the last 100 commits on the default branch, not from
`/contributors` (see Not found). Stars are context only, never a ranking.

## Claims

- claim: rulesync shipped 1,092 commits in the 30 days to 2026-09-21 and 332 releases lifetime, the highest commit velocity in the set.
  source: graphql repository(dyoshikawa/rulesync) history(since:2026-08-22).totalCount, releases.totalCount
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: velocity
- claim: rulesync was created 2025-06-18, last pushed 2026-09-22, with 1,458 stars, 154 forks and 48 open issues.
  source: graphql repository(dyoshikawa/rulesync)
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: rulesync cut v17.0.0 (2026-09-21), v16.39.1 (2026-09-19) and v16.39.0 (2026-09-18) — three releases in four days, i.e. near-daily release cadence.
  source: graphql repository(dyoshikawa/rulesync) releases(first:3)
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: rulesync's roadmap is per-runtime feature parity across config kinds, not new abstractions — v16.39.0 states "With these, the `pool` target covers rules, MCP, subagents, skills, hooks and permissions (Refs #2945)."
  source: https://github.com/dyoshikawa/rulesync/releases/tag/v16.39.0
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: every one of rulesync's top-10 open issues by reactions has 0 reactions and is a maintainer-authored upstream-tracking ticket, e.g. "Follow up Zed upstream updates: untranslated MCP entries, unrecognized write/default permission keys, sandbox_permissions, global ignore, commands, Windows global path" — demand is chasing runtime drift, not user feature requests.
  source: graphql search(repo:dyoshikawa/rulesync is:issue is:open sort:reactions-desc)
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: rulesync is single-maintainer: dyoshikawa authored 93 of the last 100 commits (97 of 97 non-bot after dependabot's 3), with 3,136 lifetime contributions as the top contributor.
  source: graphql repository(dyoshikawa/rulesync) history(first:100).author; repos/dyoshikawa/rulesync/contributors
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: dyoshikawa has a GitHub Sponsors listing enabled and no company on profile.
  source: graphql repositoryOwner(login:"dyoshikawa").hasSponsorsListing
  publisher: dyoshikawa
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: funding
- claim: gsd-core shipped 548 commits in the 30 days to 2026-09-21, second-highest in the set, on a roughly weekly minor cadence (v1.14.0 2026-09-14, v1.13.0 2026-09-06, v1.12.0 2026-08-30) with 44 releases lifetime.
  source: graphql repository(open-gsd/gsd-core) history(since:2026-08-22), releases(first:3)
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: velocity
- claim: gsd-core was created 2026-05-22 — four months old — with 9,708 stars, 698 forks and 106 open issues.
  source: graphql repository(open-gsd/gsd-core)
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: gsd-core's named forward work is delivery-pipeline hardening in epics, e.g. "feat(#4593): add a macOS-specific conformance tier, final phase of epic #4589" and "feat(#3673): add dispatch.maxConcurrency axis and dispatch-capacity query".
  source: https://github.com/open-gsd/gsd-core/releases/tag/v1.14.0
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: gsd-core's top open issues by reactions all have 0 reactions and are maintainer-filed correctness bugs, including "bug(cli): phase uat-passed and verify.artifacts exit 0 while their JSON reports failure" — the project generates its own backlog rather than harvesting user demand.
  source: graphql search(repo:open-gsd/gsd-core is:issue is:open sort:reactions-desc)
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: gsd-core has a real but lead-dominated team: trek-e authored 77 of the last 100 commits with 8 other humans contributing (0xdhx 8, drungrin 4, TwistedRiCen 2, behruznassre 2, bshiggins 1, davdittrich 1, davesienkowski 1); trek-e has 3,696 lifetime contributions.
  source: graphql repository(open-gsd/gsd-core) history(first:100).author; repos/open-gsd/gsd-core/contributors
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: Open GSD is an organization with a product site at opengsd.net and a three-product lineup (GSD Core, GSD Pi, GSD Browser) plus a public roadmap page, but no funding, pricing or hiring signal was found.
  source: graphql repositoryOwner(login:"open-gsd"); https://opengsd.net/ ; https://opengsd.net/roadmap
  publisher: open-gsd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: funding
- claim: gstack has 133,872 stars and 19,947 forks but only 22 commits in the last 30 days and zero releases ever — huge attention, low and unversioned throughput.
  source: graphql repository(garrytan/gstack)
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: velocity
- claim: gstack carries 365 open issues and is the only project in the set with genuinely reacted-to user demand, led by "Add GitHub Copilot CLI as a supported host" (33 reactions), a Playwright pin bump (20), "Make individual skills available via skills.sh" (15), an OpenCode port (13) and non-OpenAI image providers (12).
  source: graphql search(repo:garrytan/gstack is:issue is:open sort:reactions-desc)
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: gstack is effectively a small team around one owner: garrytan authored 69 of the last 100 commits, with test22345 (17), 16francej (7), time-attack (6) and Sinabina (1).
  source: graphql repository(garrytan/gstack) history(first:100).author
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: gstack's owner lists Y Combinator as his company and has no GitHub Sponsors listing.
  source: graphql repositoryOwner(login:"garrytan")
  publisher: garrytan
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: funding
- claim: wshobson/agents has 39,857 stars and 4,249 forks but 22 commits in the last 30 days, zero releases and only 7 open issues.
  source: graphql repository(wshobson/agents)
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: velocity
- claim: wshobson/agents demand is near-zero by reactions — the top issue has 1: "[BUG] Same-named agents duplicated across plugins with divergent content (9 agents flagged by garden)".
  source: graphql search(repo:wshobson/agents is:issue is:open sort:reactions-desc)
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: wshobson/agents is one maintainer plus a long tail of drive-by PRs: wshobson authored 64 of the last 100 commits, dependabot 15, and 15 other people contributed 1–4 each.
  source: graphql repository(wshobson/agents) history(first:100).author
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: wshobson's profile names a company (UDT | Major 7 Apps, major7apps.com) and has GitHub Sponsors enabled.
  source: graphql repositoryOwner(login:"wshobson")
  publisher: wshobson
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: funding
- claim: planning-with-files shipped 120 commits in 30 days and 110 releases lifetime, with three patch releases in three days (v3.20.5 2026-09-21, v3.20.4 2026-09-19, v3.20.3 2026-09-19).
  source: graphql repository(OthmanAdi/planning-with-files) history(since:2026-08-22), releases(first:3)
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: planning-with-files' recent releases are almost entirely cross-runtime and cross-OS portability defects — OneDrive `ReparsePoint` breaking the PowerShell route, symlinked plan dirs, OpenCode session replay, Cursor hooks — evidence that multi-runtime projection cost is dominated by host-environment edge cases.
  source: https://github.com/OthmanAdi/planning-with-files/releases/tag/v3.20.5 and /v3.20.4 and /v3.20.3
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: planning-with-files' most-reacted open issues are usage questions, not features: "For multi-step / complex tasks, how should this skill be used properly?" (17 reactions) and "How to handle multiple long-running tasks?" (14) — at 27,047 stars, the gap is documented usage guidance.
  source: graphql search(repo:OthmanAdi/planning-with-files is:issue is:open sort:reactions-desc)
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: planning-with-files also carries a distribution complaint — "npm package @tomxprime/planning-with-files is stale at 1.1.0 — lags git v3.9.0 by 15+ releases" — and a "Partnership inquiry from MyClaw.ai".
  source: graphql search(repo:OthmanAdi/planning-with-files is:issue is:open sort:reactions-desc)
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: demand
- claim: planning-with-files is near-single-maintainer: OthmanAdi authored 81 of the last 100 commits, with kuei51307-hub (9), ShaunLinTW (6), TayfurYldz (3) and Dphoshoba (1).
  source: graphql repository(OthmanAdi/planning-with-files) history(first:100).author
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: OthmanAdi's profile names an unrelated employer (migRaven) and has GitHub Sponsors enabled; no company stands behind the repo.
  source: graphql repositoryOwner(login:"OthmanAdi")
  publisher: OthmanAdi
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: funding
- claim: ctxlint has 9 stars and 3 forks but 56 releases and 47 commits in 30 days (v0.27.2 2026-09-15, v0.27.1 2026-09-14, v0.27.0 2026-09-14) — release discipline far ahead of adoption.
  source: graphql repository(YawLabs/ctxlint)
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: ctxlint has zero open issues, so there is no reaction-ranked demand signal at all; its roadmap is self-directed rule correctness, e.g. "Glob-scoped `.ctxlintignore` rules show up in the \"Ignore rules\" report when they drop nothing."
  source: graphql repository(YawLabs/ctxlint).issues(states:OPEN); https://github.com/YawLabs/ctxlint/releases/tag/v0.27.0
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: ctxlint is single-maintainer: jeffyaw authored 87 of the last 100 commits and dependabot the other 13 — 100% of human commits — with 263 lifetime contributions.
  source: graphql repository(YawLabs/ctxlint) history(first:100).author; repos/YawLabs/ctxlint/contributors
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: ctxlint sits under a commercial-looking org, YawLabs, "makers of yaw terminal, yaw mcp & typed" at yaw.sh with <contact address in the source README>, but the org profile shows no funding or hiring signal.
  source: graphql repositoryOwner(login:"YawLabs")
  publisher: YawLabs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: funding
- claim: agnix shipped 76 commits in 30 days and 93 releases lifetime (v0.54.0 2026-09-16, v0.53.0 2026-09-14, v0.52.2 2026-09-05) at 421 stars and zero open issues.
  source: graphql repository(agent-sh/agnix)
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: agnix's release notes show its forward work is tracking upstream runtime versions as a treadmill: "Advance Claude Code to `v2.1.273`, Cursor to `3.20.21`, Gemini CLI to `v0.60.0`, and OpenCode to `v1.18.31` after reviewing their primary release notes" — a linter whose value is version-chasing, released roughly fortnightly.
  source: https://github.com/agent-sh/agnix/releases/tag/v0.54.0
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: agnix is single-maintainer: avifenesh authored 75 of the last 100 commits, dependabot 24 and github-actions 1 — 100% of human commits.
  source: graphql repository(agent-sh/agnix) history(first:100).author
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: agnix's org agent-sh describes itself as a "DX focused ecosystem for AI-powered research and development" with a GitHub Pages site and a personal gmail contact — no company, funding or hiring signal.
  source: graphql repositoryOwner(login:"agent-sh")
  publisher: agent-sh
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: funding
- claim: superpowers has 289,770 stars and 25,936 forks but only 1 commit in the 30 days to 2026-09-21 — by far the slowest in the set despite the largest audience.
  source: graphql repository(obra/superpowers) history(since:2026-08-22).totalCount
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: velocity
- claim: superpowers releases are roughly monthly and slipping (v6.4.1 2026-09-19, v6.3.0 2026-08-12, v6.2.0 2026-07-24), 13 releases lifetime, and v6.4.1's notes admit a pulled release: "v6.4.0 was never shipped. v6.4.1 is the first release with these changes. It holds back the new `proving-it-works-with-a-movie` skill".
  source: https://github.com/obra/superpowers/releases/tag/v6.4.1
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: cadence
- claim: superpowers' named direction is breadth of runtime support plus cheaper execution — v6.4.1 "adds support for three new harnesses: OpenCode 2.0, Muse, and Qwen Code" and rebuilds `executing-plans` as "Native execution, a cheaper alternative to subagent-driven development"; v6.3.0 added Devin CLI, Hermes and Grok Build CLI.
  source: https://github.com/obra/superpowers/releases/tag/v6.4.1 and /v6.3.0
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: superpowers holds the only large reacted demand in the set: "Support for Claude Code Agent Teams (TeammateTool, SendMessage, TaskList)" (115 reactions), "writing-plans: plans over-specify implementation, leaving no room for executor judgment" (37), "Im seeing slowness in responses since using the skill" (32), "Add Support for Kiro CLI as an AI Provider" (22), "Support OpenClaw platform" (20) — three of the top five are new-runtime requests, one is overhead, one is over-prescription.
  source: graphql search(repo:obra/superpowers is:issue is:open sort:reactions-desc)
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: demand
- claim: superpowers is effectively two people: obra authored 82 of the last 100 commits and arittr 12, with four others at 1–2; 136 open issues against that capacity.
  source: graphql repository(obra/superpowers) history(first:100).author
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: maintainership
- claim: obra's profile names a company (Prime Radiant) and has GitHub Sponsors enabled.
  source: graphql repositoryOwner(login:"obra")
  publisher: obra
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: funding

## Leads

- Runtime coverage is the demand axis everyone is graded on. Copilot CLI (gstack, 33), Kiro CLI and
  OpenClaw (superpowers, 22/20), OpenCode (gstack, 13) are the top reacted asks in the whole set.
  For 0.13, "which runtimes does it project into" beats "what does it project".
- Usage documentation is the second axis, and it is invisible in stars. planning-with-files at 27k
  stars has its two most-reacted issues both asking how to use the thing for multi-step work.
- Nobody in this set carries a user-driven feature backlog except gstack and superpowers. rulesync,
  gsd-core, ctxlint and agnix all generate their own issues. If agent-harness wants outside users,
  reaction-bearing issues are the leading indicator to watch, not stars.
- The portability tax is real and it is OS-level, not runtime-level: planning-with-files burned
  three consecutive releases on OneDrive reparse points, symlinked directories and null rows.
- agnix and rulesync both spend most of their throughput chasing upstream version drift. An
  0.13 that pins or declares which runtime versions it supports avoids that treadmill.

## Not found

- `/contributors` full first-page counts. The 8 REST calls were budgeted but the jq filter was
  overridden by a conflicting flag and re-running would have exceeded the 14-call cap. Only the
  top contributor's lifetime contribution count survived (dyoshikawa 3,136; trek-e 3,696;
  garrytan 357; wshobson 352; OthmanAdi 376; jeffyaw 263; avifenesh 1,013; obra 524).
  Maintainership claims above are derived from last-100-commit authorship instead, which is a
  better >90% test but does not give a total contributor count. Re-run to fill.
- CHANGELOG tops were not read separately; release notes carried the same content for all six
  projects that publish releases. gstack and wshobson/agents publish no releases at all, so their
  forward direction is unevidenced — a CHANGELOG or roadmap read is the gap.
- Funding: only one web search was spent (open-gsd). No funding, pricing or hiring page found for
  Open GSD. YawLabs (yaw.sh) and agent-sh were not searched; both are unresolved.
