# Users' voice — r1-1

Method: `gh api` issue listings for six trackers, most-reacted open + most-commented closed since 2026-06-23. Titles and first 300 chars only. 12 API calls, no web search.

Caveat on source quality: `open-gsd/gsd-core`, `dyoshikawa/rulesync` and (largely) `wshobson/agents` returned almost exclusively maintainer-authored engineering issues with 0 reactions and 0 comments — those are not user voice and are excluded from the sentiment clusters, though two are quoted below as evidence of silent-failure patterns. Real user voice concentrates in `obra/superpowers`, `garrytan/gstack` and `OthmanAdi/planning-with-files`.

## Claims

- claim: A user asks outright "How do I know if Claude Code is using Superpowers? I followed all the steps and I can't really know if it's doing anything different than standard plan mode." — 23 comments, the highest-discussion closed issue in the set.
  source: https://github.com/obra/superpowers/issues/446
  publisher: obra/superpowers
  pub_date: 2026-02
  accessed: 2026-09-21
  confidence: high
  class: rules-not-working

- claim: gstack skills generated for Codex "silently fail in Default mode" because the skill body references a tool Codex strips from frontmatter — the rule is present and simply does not fire.
  source: https://github.com/garrytan/gstack/issues/1066
  publisher: garrytan/gstack
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: rules-not-working

- claim: planning-with-files' PostToolUse nudge "is sent as systemMessage, so it reaches the user and never the model — unthrottled": the instruction the project relies on was never delivered to the agent at all.
  source: https://github.com/OthmanAdi/planning-with-files/issues/239
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: rules-not-working

- claim: rulesync's `antigravity-cli` permissions override "copies exactly four autonomy keys and silently drops" the persisted execution-mode key — authored config that vanishes on projection.
  source: https://github.com/dyoshikawa/rulesync/issues/2509
  publisher: dyoshikawa/rulesync
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: rules-not-working

- claim: gsd-core's regression gate "silently runs the full suite" because `REGRESSION_FILES` has no producer — the configured narrowing never takes effect and nothing reports it.
  source: https://github.com/open-gsd/gsd-core/issues/4915
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: rules-not-working

- claim: gsd-core's codebase-drift sanitizer "has no production caller", so unsanitized paths reach the warn message and the mapper prompt — a declared safety rule that is not wired up.
  source: https://github.com/open-gsd/gsd-core/issues/4923
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: rules-not-working

- claim: rulesync ships a `continue` target with no end-of-life note after Continue was acquired and archived, and "the `mcp` adapter sile[ntly]" mishandles it — projection to a dead runtime with no signal to the user.
  source: https://github.com/dyoshikawa/rulesync/issues/3078
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: rules-not-working

- claim: "since installation my claude code has started to slow down quite a bit. Maybe the context of the superpower skill is eating up too much space." — 32 reactions, 26 comments, the second-most-reacted open issue in the set.
  source: https://github.com/obra/superpowers/issues/743
  publisher: obra/superpowers
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Superpowers is fantastic but it uses a lot of tokens and takes a long time to complete a task. A `Slim` version would be great."
  source: https://github.com/obra/superpowers/issues/2017
  publisher: obra/superpowers
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: A user reports 68M tokens for ~3000 LoC with a 1400-line plan and asks "Are thos[e normal]" — token cost framed as a plan-verbosity problem.
  source: https://github.com/obra/superpowers/issues/1194
  publisher: obra/superpowers
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Superpowers consume a lot of tokens in Opencode with Codex" — same complaint on a second runtime, 13 comments.
  source: https://github.com/obra/superpowers/issues/750
  publisher: obra/superpowers
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: The two-stage review loop "creates a compounding spiral on tasks that are simple and fully specified… burned significant tokens and time without improving output".
  source: https://github.com/obra/superpowers/issues/1120
  publisher: obra/superpowers
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "gstack ships ~30 skills, but most users only actively use a subset. The unused ones still load their descriptions into every Claude Code session, which costs tokens" — and deleting symlinks does not survive `gstack-upgrade`.
  source: https://github.com/garrytan/gstack/issues/1206
  publisher: garrytan/gstack
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: "plans over-specify implementation, leaving no room for executor judgment" — 37 reactions, 21 comments, the top non-runtime open complaint.
  source: https://github.com/obra/superpowers/issues/895
  publisher: obra/superpowers
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Add GitHub Copilot CLI as a supported host" — 33 reactions, the single most-reacted open issue on gstack.
  source: https://github.com/garrytan/gstack/issues/393
  publisher: garrytan/gstack
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: "setup for cursor is broken… Unknown --host value: cursor (expected claude, codex, kiro, factory, opencode, openclaw, hermes, gbrain, or auto)" — a user assumed a runtime was supported and the installer rejected it.
  source: https://github.com/garrytan/gstack/issues/1269
  publisher: garrytan/gstack
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "`playwright install` hangs on Node 24.16+" during `./setup` because of a stale pin — 20 reactions on a pure install-friction bug.
  source: https://github.com/garrytan/gstack/issues/1703
  publisher: garrytan/gstack
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Conductor gstack template fails on new project creation with build exit code 128" — 11 comments on first-run failure.
  source: https://github.com/garrytan/gstack/issues/1174
  publisher: garrytan/gstack
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Users without OpenAI billing hit a hard wall" in the `design` skill because the provider is hardcoded.
  source: https://github.com/garrytan/gstack/issues/990
  publisher: garrytan/gstack
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "superpowers:write-plan Error writing files in claude code" after brainstorming and worktree setup — install/first-run breakage, 12 comments.
  source: https://github.com/obra/superpowers/issues/408
  publisher: obra/superpowers
  pub_date: 2026-02
  accessed: 2026-09-21
  confidence: medium
  class: complaint

- claim: The superpowers issue template itself states "The Windows SessionStart hook alone has been reported 29 times" — install friction at a volume the maintainer had to template against.
  source: https://github.com/obra/superpowers/issues/1026
  publisher: obra/superpowers
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "the npm package `@tomxprime/planning-with-files` hasn't been republished since 2026-05-22 (`1.1.0`), while the repo has moved through ~15" releases — the installed artifact drifts from the source.
  source: https://github.com/OthmanAdi/planning-with-files/issues/213
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "The repository has 8 duplicate copies of the same `planning-with-files` skill" across client folders — config drift between runtimes as a maintenance complaint from a contributor.
  source: https://github.com/OthmanAdi/planning-with-files/issues/53
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-01
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "Any process that can write `task_plan.md` — a malicio[us one]" — a user asks for content-source attestation because plan text is injected straight into model context.
  source: https://github.com/OthmanAdi/planning-with-files/issues/150
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: "Codex v3.4.1 Windows hooks fail on JSON and Unicode… hook returned invalid user prompt submit JSON output" — hooks are the fragile surface.
  source: https://github.com/OthmanAdi/planning-with-files/issues/204
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "the context length has already reached 140K, nearing the automatic compression trigger… how should I proceed?" — 17 reactions, 24 comments, the top user question on planning-with-files.
  source: https://github.com/OthmanAdi/planning-with-files/issues/19
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-01
  accessed: 2026-09-21
  confidence: high
  class: complaint

- claim: "How to handle multiple long-running tasks?… one task is blocked waiting for external dependencies and I need to work on another" — no documented pattern exists.
  source: https://github.com/OthmanAdi/planning-with-files/issues/50
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-01
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: "Installing the whole workflow is great, but some people want only individual pieces/skills… `npx skills add garrytan/gstack --skill plan-ceo-review`. This also allows the skills to work on other c[lients]."
  source: https://github.com/garrytan/gstack/issues/113
  publisher: garrytan/gstack
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: request

- claim: "it turns planning, review, QA, design review, and release preparation into a much more industrialized AI workflow, instead of just a loose collection of prompts" — the clearest praise in the set, from a user requesting an OpenCode port.
  source: https://github.com/garrytan/gstack/issues/314
  publisher: garrytan/gstack
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: praise

- claim: "thank you for planning-with-files. It's a genuinely useful piece of work and we've been glad to have it in our harness."
  source: https://github.com/OthmanAdi/planning-with-files/issues/213
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: praise

- claim: "Same-named agents duplicated across plugins with divergent content (9 agents flagged by garden)" — the only substantive user-filed bug surfaced on wshobson/agents; config drift within one project.
  source: https://github.com/wshobson/agents/issues/643
  publisher: wshobson/agents
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: medium
  class: complaint

- claim: "How do I use superpowers in kilocode to enforce a workflow?" — 14 reactions, a user asking how to make rules bind on an unsupported runtime.
  source: https://github.com/obra/superpowers/issues/715
  publisher: obra/superpowers
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: request

## Clusters

**1. Missing runtime X — 9**
The single largest cluster by issue count and by reactions (33, 22, 20, 18, 18, 14, 13 on the top entries). Every project is asked to support a runtime it does not.
- https://github.com/garrytan/gstack/issues/393 (Copilot CLI, 33r)
- https://github.com/garrytan/gstack/issues/314 (OpenCode)
- https://github.com/garrytan/gstack/issues/648 (OpenCode, closed)
- https://github.com/obra/superpowers/issues/503 (Kiro CLI, 22r)
- https://github.com/obra/superpowers/issues/641 (OpenClaw, 20r)
- https://github.com/obra/superpowers/issues/776 (Trae IDE, 18r)
- https://github.com/obra/superpowers/issues/1581 (Hermes, 24 comments)
- https://github.com/obra/superpowers/issues/715 (kilocode)
- https://github.com/obra/superpowers/issues/429 (Agent Teams, 115r — new host surface, not a separate CLI)

**2. Cost / token bloat / too much output — 6**
- https://github.com/obra/superpowers/issues/743 (32r, 26c)
- https://github.com/obra/superpowers/issues/2017
- https://github.com/obra/superpowers/issues/1194
- https://github.com/obra/superpowers/issues/750
- https://github.com/obra/superpowers/issues/1120
- https://github.com/garrytan/gstack/issues/1206

**3. Install friction — 6**
- https://github.com/garrytan/gstack/issues/1703
- https://github.com/garrytan/gstack/issues/1269
- https://github.com/garrytan/gstack/issues/1174
- https://github.com/garrytan/gstack/issues/990
- https://github.com/obra/superpowers/issues/408
- https://github.com/obra/superpowers/issues/1026 (Windows SessionStart hook, 29 reports per the template)

**4. Rules not working / silently ignored — 7** (see §Wedge; spans every project except wshobson/agents)
- https://github.com/obra/superpowers/issues/446
- https://github.com/garrytan/gstack/issues/1066
- https://github.com/OthmanAdi/planning-with-files/issues/239
- https://github.com/dyoshikawa/rulesync/issues/2509
- https://github.com/dyoshikawa/rulesync/issues/3078
- https://github.com/open-gsd/gsd-core/issues/4915
- https://github.com/open-gsd/gsd-core/issues/4923

**5. Config drift between tools/copies — 4**
- https://github.com/OthmanAdi/planning-with-files/issues/53
- https://github.com/OthmanAdi/planning-with-files/issues/213
- https://github.com/wshobson/agents/issues/643
- https://github.com/garrytan/gstack/issues/113

**6. Hook fragility and hook security — 3**
- https://github.com/OthmanAdi/planning-with-files/issues/204
- https://github.com/OthmanAdi/planning-with-files/issues/150
- https://github.com/OthmanAdi/planning-with-files/issues/262

**7. Breaking changes on update — 2**
- https://github.com/garrytan/gstack/issues/1206 (customization lost on `gstack-upgrade`)
- https://github.com/OthmanAdi/planning-with-files/issues/213 (npm lags git by 15 releases)

**8. Unclear which rule caused a behaviour — 1**
- https://github.com/obra/superpowers/issues/446 (the only one, and it is phrased as "is it running at all", not "which rule fired")

## Wedge — every rules-not-working instance, quoted

1. obra/superpowers#446, 2026-02, 23 comments, 3 reactions: *"Silly question from experienced Claude Code user here: How do I know if Claude Code is using Superpowers? I followed all the steps and I can't really know if it's doing anything different than standard plan mode."* — This is the wedge question asked verbatim, by a self-described experienced user, and it drew the most comments of any closed issue in the set. It is one person's question with heavy engagement, not a repeated filing.
2. garrytan/gstack#1066, 2026-04: *"Codex skills that call AskUserQuestion silently fail in Default mode"* — *"gstack skills generated for Codex CLI still reference `AskUserQuestion` in their prompt bodies even though Codex strips that tool from the frontmatter."* A projection-layer failure: the rule is emitted, the target runtime drops it, nobody is told.
3. OthmanAdi/planning-with-files#239, 2026-09: *"PostToolUse nudge is sent as systemMessage, so it reaches the user and never the model — unthrottled, and Bash is in the matcher."* The enforcement mechanism was addressed to Claude and delivered to the human.
4. dyoshikawa/rulesync#2509, 2026-07: the permissions override *"copies exactly four autonomy keys and silently drops an[other]"*. Authored config lost in projection, silently.
5. dyoshikawa/rulesync#3078, 2026-09: rulesync added the `continue` target *"without any end-of-life note, and the `mcp` adapter sile[ntly]"* mishandles it — users project rules to a dead runtime.
6. open-gsd/gsd-core#4915, 2026-09: *"regression gate silently runs the full suite"* — *"`REGRESSION_FILES` has no producer."*
7. open-gsd/gsd-core#4923, 2026-09: *"sanitizePaths has no production caller, so affected_paths reaches the warn message and the auto-remap mapper prompt unsanitized."*

Pattern read: items 2–7 are all maintainer-authored, found by code reading, not by a user noticing. Item 1 is the only *user* who noticed, and what he noticed was absence of any signal, not a wrong behaviour. The honest conclusion is that silent rule failure is endemic and users cannot detect it — which is precisely why only maintainers file it.

## Leads

- superpowers#429 (Agent Teams, 115 reactions) is the highest-demand item across all six trackers by a wide margin. Multi-agent host support outranks every other ask.
- superpowers#895 ("plans over-specify implementation, leaving no room for executor judgment", 37r/21c) plus #1120 (review spiral on simple tasks) are one argument: users want the ceremony to scale down with task size.
- gstack#113 asks for per-skill distribution via skills.sh explicitly so "the skills work on other clients" — i.e. users want the *unit of projection* to be smaller than the whole harness.
- gstack#1206 is the clearest statement of the customization-survives-upgrade problem: deleting symlinks does not survive `gstack-upgrade`.
- planning-with-files#150 wants content-source attestation on injected plan text; the only user-side security ask in the set.

## Not found

- No 1–3 star reviews of any kind: none of these projects has a review surface reachable from the issue trackers, and no web search was in budget.
- No issue anywhere asking "which rule caused this behaviour" or requesting rule-level provenance/telemetry. The closest is superpowers#446 ("is it running at all"). **Nothing in the set ships or is asked for a way to see which instruction fired.**
- No issue asking for a linter that validates rules against a runtime's actual capabilities before projection — the gstack#1066 and rulesync#2509 failures are exactly what such a linter would catch, and no user requested one.
- No issue asking for a dry-run / diff preview of what a config change would project into each runtime.
- `open-gsd/gsd-core` and `wshobson/agents` returned no closed issues in the last 90 days matching the query, and gsd-core's open issues carry zero reactions and zero-to-one comments throughout — no usable user sentiment from either. Treat the absence as unmeasured, not as satisfaction.
- No cross-project measurement of how often a rule is actually obeyed; nobody is counting.
