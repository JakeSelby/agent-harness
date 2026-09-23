---
title: 'competitive research: agent-harness field scan: what the config-compiler field does and where 0.13 should spend'
type: 'competitive'
topic: 'agent-harness field scan: what the config-compiler field does and where 0.13 should spend'
decision: 'Where should agent-harness 0.13 spend its effort to make the harness usable by people who are not its author?'
source: 'process+run'
status: complete
preset: 'standard'
validation: 'normal'
claims_verified: 20
claims_unverified: 0
sources: 32
created: '2026-09-21'
updated: '2026-09-21'
---

# competitive research: agent-harness field scan: what the config-compiler field does and where 0.13 should spend

**Decision this research serves:** Where should agent-harness 0.13 spend its effort to make the harness usable by people who are not its author?

## Executive summary

**What the evidence says to do.** Spend 0.13 on three things, in this order. First, the standalone instrument with a sixty-second path: the one time a *user* asked the wedge question in six issue trackers — "How do I know if Claude Code is using Superpowers? … I can't really know if it's doing anything different" [19] — nothing in the field could answer it, and every other silent-rule failure found was found by a maintainer reading code [20][21][22][23]. Second, install parity — a plugin manifest, a packaged install and an importer — because install friction and config drift are the third and fifth complaint clusters [25][26], every high-adoption neighbour ships a manifest [1][7][8][12], and rulesync's `import` is what makes the best compiler adoptable [5]. Third, a positioning that uses the field's own words ("rules", not "harness" [7]), makes the *bounded* uniqueness claim [15][28], and pairs a code-generated capability matrix with reproducible evidence — the combination no project has [31][32].

**The three findings that drive that answer.** Attention in this category is uncorrelated with engineering: the best-built compiler has 1,458 stars after 1,092 commits in thirty days, the largest project has 289,770 stars and one commit [18]; adoption follows audience and a sentence, not depth. Demand and defects come from different people: users ask for new runtimes (the largest reacted cluster; the single most-reacted ask in any tracker, 115 reactions, is for a new host surface rather than a new CLI) [25], while silent rule failures are filed only by maintainers because users cannot see them [20][21][22][23] — which is the case for an instrument that makes the invisible visible. The one evidence-positioned project reached 27,000 stars on it, and round 2 showed how thin the method under the hero number is and how much stronger its ongoing, self-incriminating benchmark is — so the bar is a published corpus, not a headline figure [9][31].

**The biggest caveat.** The sensor's own validity is unmeasured — no labelled corpus, per-variant rates observational, opted-out rules dark [15] — and the one prior attempt to sell measurement of *configuration* (ctxlint, 90 rules) has nine stars [10][18]. The bet that measuring *behaviour* converts where measuring files did not is a bet. Ship the instrument, publish the corpus, and count.

_Dimension sections follow in plan order._

## 1. Feature teardown — what the field actually ships

Processed from three imported dossiers (twenty repositories read via the GitHub API with file paths) and the four curated-list READMEs. Digests: `teardown-import-1..3`, `teardown-list-1..4`. Where this section quotes a source file verbatim, the wording is taken from the import dossier in `imports/`, which quotes the file; the digests paraphrase, and a fresh-context audit flagged the difference (see the memlog).

**The category, and who is in it.** The tools that hold agent configuration as one source and *generate* each runtime's native files form a category of roughly eight: rulesync, gsd-core, gstack, wshobson/agents, planning-with-files, LynxPrompt, caliber/ai-setup and agent-harness [1][5][6][7][8][9][13]. Three adjacent categories get conflated with it and are structurally different: skill packs shipped as-is (superpowers, addyosmani/agent-skills, anthropics/skills, pmstack) [1][12]; read-only linters of context files (ctxlint, agnix, agents-md-cookbook, Schliff, cc-audit) [2][10][11][14][29]; and governance planes that gate actions at runtime (ControlKeel, tdd-guard) [4][30].

**Breadth is one project's.** rulesync compiles 52 targets, and the list is derived rather than hand-kept — one tuple per feature, unioned in `src/types/tool-targets.ts` ("no separately-maintained literal to drift") — with bidirectional `import`/`convert`, 461 test files and a hooks-only opt-in ownership lock [5]. gsd-core reaches 16 runtime families through an installer [6]; gstack 10 hosts through `SKILL.md.tmpl` generation [8]; wshobson 6 via `tools/generate.py` [7]; planning-with-files 11 IDE directories by copy with a `--verify` drift check [9]. agent-harness compiles two.

**Switchable behavioural preferences exist in three places, none of them general.** planning-with-files' `.mode` carries `legacy | autonomous | gated` with a precedence rule stronger than override — "Root `.mode` is a FLOOR, not a default that slug scope replaces" [9]. gsd-core's `MODEL_PROFILES` offer `quality | balanced | budget | adaptive` per agent, and `DepthTier` (`quick | standard | deep`) auto-downgrades past a file threshold [6]. LynxPrompt composes `--boundaries conservative|standard|permissive`, a plan-mode frequency enum and a verbosity level into generated config across ~38 platforms [13]. Nothing else in twenty repositories models a behavioural axis as named alternatives; the one dossier that said "nobody" is contradicted by LynxPrompt's file:line evidence and the bounded form is used here (`teardown-import-2`, contradiction recorded).

**Validation of the instruction set is a linter's job, and one linter does it well.** ctxlint ships 90 rules in four JSON catalogs with token thresholds (`error: 8000`, `tierAggregate: 4000`) and cross-file contradiction detection over eight tool-choice axes [10]. agnix adds an LSP and a GitHub Action [11]. Nothing in the compiler category lints its own output beyond drift checks.

**Six projects enforce an always-loaded size cap and no two numbers agree**: 200 lines (agnix, cc-audit), 150 (wshobson), 150 soft / 300 heavy plus a 32,768-byte hard cap (agents-md-cookbook), 400 lines and 2,000 tokens in its prompts against 5,000 tokens in its own scorer (caliber, internally inconsistent), 8,000 tokens with a 4,000-token tier aggregate (ctxlint), 200 (agent-harness) [7][10][11][14][29]. Only the 32 KiB figure cites a mechanism — "Codex truncates AGENTS.md at 32 KiB by default" [14]. Confidence on the pattern: high; on any individual number being *right*: none of them shows evidence.

**Measurement of whether a rule changed behaviour: the nearest neighbour runs the other way.** Burnd reads the same Claude Code JSONL transcripts, flags heavy skill firing when `Skill` is at least 5 calls and over 20 percent of tool calls ("Heavy skill firing usually means a skill description is too broad"), and attaches a `claudeMdPatch` — "the single CLAUDE.md line (or short block) that fixes this leak" — to every insight [15]. cc-cost reads the same files for six cost heuristics [16]. Neither binds a detector to a rule file, neither gates coverage, neither reports a per-rule rate. Langfuse, Opik and Phoenix score traces of an instrumented application and accept OTLP; none has a rule concept or a transcript reader [28].

**Licensing findings that constrain reuse.** anthropics/skills is not open source: no repository-level licence, and each skill's `LICENSE.txt` forbids extraction, reproduction and derivative works (the import quotes it: users may not "retain copies of these materials outside the Services") [17]. c0x12c/ai-toolkit ships no licence; ControlKeel is `NOASSERTION` [30].

**List membership.** `JakeSelby/agent-harness` appears in none of the four lists (`grep -c` = 0 in each) [1][2][3][4]. Preference profiles are the thinnest class in every list; transcript and session telemetry is the largest single class in the fourth [4].

## 2. Positioning and messaging — what each project says it is, and the gap to what it ships

Digests: `positioning-r1-1` (eight primary READMEs, 23 claims), `positioning-r2-1` (two lead documents, 17 claims). All eight repositories were pushed within 24 hours of the fetch, so every hero line is current.

**The vocabulary.** "Harness" is near-absent as self-description: of eight hero lines only wshobson/agents uses it, and there it names the *target runtimes* ("six target harnesses"), not the projecting tool [7]. The most common noun is "skill" (four of eight), then "config" or "configuration" (three), then "rules" (two); "context engineering" is gsd-core's alone [5][6][7][9][10][11][12]. A reader searching for what this category does is not typing "harness". Six of eight name no audience at all and describe only the artifact; gstack names founders, first-time users and staff engineers, ctxlint names a team scenario [8][10].

**Where every project stretches: the projection claim.** wshobson's hero says its plugins are "consumed natively by … six target harnesses", while its own quickstart says Antigravity, OpenCode and Pi "install via clone + generate (the transformed trees are gitignored)" — three of six are a local build step [7]. rulesync's 50-row table has CodeBuddy Code at one of nine features and three end-of-life targets kept as "frozen-compatibility" [5]. planning-with-files' "60+ agents" is Agent Skills conformance; its own hook table shows depth on six [9]. gsd-core's "and more" is never enumerated in the README [6]. Superpowers is the inverse — sixteen runtime install sections and no breadth claim in the hero at all [12]. Confidence: high; every gap is the project's own README against itself.

**Exactly one project is positioned on evidence, and it is the 27,000-star one.** planning-with-files leads with "Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives `/clear`, and 3 out of 3 blind A/B wins to show it works" [9]. Round 2 read the method behind it [31]. The A/B claim is the weakest thing in the document and the document knows it: three LLM comparator agents scored with-skill against without-skill on three of five tasks, one run per cell, "blind" meaning randomised assignment with judges not told which arm was which; no human judged; the substrate is 30 file-existence and section-header assertions measuring conformance to the skill's own three-file format (29 of 30 with the skill against 2 of 30 without, per the README's benchmark block [9]), which the doc self-classifies as an "encoded preference skill (not capability uplift)" while disclosing a roughly 68 percent token and 17 percent time premium. **What is genuinely strong is that the measurement is ongoing** — five tests across three versions, most recently a seven-arm, 77-cell benchmark where "No LLM grades anything", which publishes a result *against itself* (the skill triggered unforced in 2 of 3 and 3 of 5 runs across two task groups, versus every run for always-loaded project rules), discloses a grader bug that had zeroed a competitor, and carries a verbatim "What this test does not measure" section. The task set and all 77 raw runs are untracked, so nobody can reproduce it [31]. Everyone else offers no behavioural evidence: agnix borrows Vercel's "skills invoke at 0% without correct syntax" for the *problem* and shows nothing for the fix [11]; ctxlint's "measures" is token counting [10]; gstack's "810×" measures the author's output, not the tool's effect on an agent [8].

**The honest compatibility surface has a model, and it is generated.** wshobson's `docs/harnesses.md` is 14 capability rows by six harnesses, produced from `tools/adapters/capabilities.py` via `make docs` — downstream of code, not maintained prose — with unsupported cells left as a bare dash and a second "Graceful degradation" table naming the exact rewrite per source pattern per harness [32]. It has no self-limits section and no evidence the generated artifacts run beyond discovery smoke tests [32]. Cross-dimension: **nobody in the field pairs a published capability matrix with reproducible evidence** — wshobson generates the matrix and proves nothing; planning-with-files measures seriously and publishes no corpus.

**Not found.** No project positions on being usable by someone other than its author — no onboarding time, no first-hour claim, no adoption metric in any hero line. No project claims portability evidence: that the same rule produced the same behaviour on two runtimes. No docs landing pages were compared against READMEs (budget went to the eight primaries), and nothing here is corroborated by a third party — every claim is the project speaking about itself.

## 3. Trajectory — cadence, maintainership, demand

Digest: `trajectory-r1-1` (40 claims, GitHub GraphQL, fetched 2026-09-21).

**Velocity and attention are uncorrelated.** In the 30 days to 2026-09-21: rulesync 1,092 commits and three releases in four days (v17.0.0, v16.39.1, v16.39.0) at 1,458 stars; gsd-core 548 commits on a weekly minor cadence at 9,708 stars, four months old; superpowers **one** commit at 289,770 stars, with releases slipping to roughly monthly and v6.4.1's notes admitting "v6.4.0 was never shipped" [18]. gstack and wshobson/agents have never cut a release [18].

**Single-maintainer is the norm in the compiler and linter slots.** By authorship of the last 100 commits: rulesync (dyoshikawa 93), ctxlint (jeffyaw 87, remainder dependabot), agnix (avifenesh 75, remainder bots); near-single planning-with-files (OthmanAdi 81) and superpowers (obra 82 plus arittr 12, against 136 open issues) [18]. Teams exist at gsd-core (trek-e 77 plus eight humans), gstack (garrytan 69 plus four) and wshobson/agents (64 plus a long drive-by tail) [18]. Confidence: high for the counts; the `/contributors` totals were lost to a flag conflict so maintainership is inferred from authorship, not the contributors endpoint.

**Demand, where it exists, is for new runtimes.** The most-reacted open issues across the set: superpowers "Support for Claude Code Agent Teams" (115 reactions), gstack "Add GitHub Copilot CLI as a supported host" (33), superpowers Kiro CLI (22) and OpenClaw (20), gstack OpenCode (13) [18][25]. Second: usage guidance — planning-with-files' top two issues at 27k stars are "how should this skill be used properly?" (17) and "How to handle multiple long-running tasks?" (14) [26]. rulesync, gsd-core, ctxlint and agnix show **no** reacted user demand; their backlogs are maintainer-filed upstream-drift tickets — agnix's release notes are a treadmill of "Advance Claude Code to v2.1.273, Cursor to 3.20.21…" [18].

**Where the projection cost actually lands.** planning-with-files' recent patch releases are almost entirely host-environment edge cases — OneDrive reparse points breaking the PowerShell route, symlinked plan directories, OpenCode session replay, Cursor hooks [18]. Multi-runtime projection is dominated by per-host defects, not by the abstraction.

**Funding and companies.** GitHub Sponsors enabled for dyoshikawa, wshobson, OthmanAdi and obra; companies behind gstack (Y Combinator), superpowers (Prime Radiant, with a `sales@` line), wshobson (Major 7 Apps); Open GSD has a product site and three-product lineup with no pricing or hiring signal found [18]. Confidence: medium — one web search per project at most.

## 4. Users' voice — what people praise, complain about, and ask for

Digest: `users-voice-r1-1` (32 claims, six issue trackers). **Caveat that bounds this section:** gsd-core, rulesync and wshobson/agents returned almost entirely maintainer-authored issues with zero reactions; their user sentiment is *unmeasured*, not absent. Real user voice here is superpowers, gstack and planning-with-files.

**Clusters, by count and reactions.** Missing runtime X — nine issues and the largest reactions in the set [25]. Cost, token bloat and too much output — six, led by superpowers#743 ("since installation my claude code has started to slow down… the context of the superpower skill is eating up too much space", 32 reactions) and the request for "a `Slim` version" [24]. Install friction — six, including a template line stating "The Windows SessionStart hook alone has been reported 29 times" [25]. Config drift between copies — four, including "8 duplicate copies of the same `planning-with-files` skill" across client folders and an npm package fifteen releases behind git [26]. Users also want the unit of distribution smaller than the whole harness: "some people want only individual pieces/skills… `npx skills add garrytan/gstack --skill plan-ceo-review`" [27].

**The wedge question, asked once, verbatim.** obra/superpowers#446, from a self-described experienced Claude Code user, 23 comments: *"How do I know if Claude Code is using Superpowers? I followed all the steps and I can't really know if it's doing anything different than standard plan mode."* [19]. It is the only issue in six trackers where a *user* asks whether the rules are doing anything, and what they noticed was the absence of any signal.

**Silent rule failure is endemic, and only maintainers find it.** The digest's fourth cluster, "rules not working / silently ignored", holds seven issues across five projects; one is the user question above and six are maintainer-filed. gstack skills generated for Codex "silently fail in Default mode" because the body references a tool Codex strips from front matter [20]. planning-with-files' PostToolUse nudge "is sent as systemMessage, so it reaches the user and never the model" [21]. rulesync's permissions override "copies exactly four autonomy keys and silently drops" one, and it ships a `continue` target for an archived runtime that "the `mcp` adapter sile[ntly]" mishandles [22]. gsd-core's regression gate "silently runs the full suite" because `REGRESSION_FILES` has no producer, and its path sanitiser "has no production caller" [23]. All six were found by code reading, not by a user noticing. Confidence: high on each quote; the pattern is six instances across four projects, not a survey.

**Not found, and it matters.** No issue anywhere asks which rule caused a behaviour, requests rule-level provenance, asks for a linter that checks rules against a runtime's real capabilities, or asks for a dry-run diff of what a change would project. Nobody is counting whether rules are obeyed — and nobody has asked to. The demand is latent: #446 is one person with heavy engagement, not a pattern of filings.

## 5. Cross-dimension insights

- **Attention is uncorrelated with engineering, so the compiler is not the lever.** rulesync: 52 targets, 1,092 commits in thirty days, three releases in four days, 1,458 stars [5][18]. superpowers: one commit in thirty days, 289,770 stars [18]. ctxlint: 90 rules, 56 releases, nine stars [10][18]. Adoption follows an author's audience or one idea a reader can repeat; depth without a sentence is invisible. For 0.13 this means a standalone tool with a sentence outranks a third runtime adapter.
- **Demand and defects come from different people.** Users file requests for runtimes [25] and complaints about cost and install [24][25]; maintainers file the silent-rule failures [20][21][22][23], because a user cannot see a rule that never fired — #446 is a user noticing only the *absence* of signal [19]. An instrument that turns a maintainer-only finding into a user-visible one is addressing a real defect class with latent, not loud, demand.
- **Evidence positioning works and gets discounted in the same document.** planning-with-files leads with "3 out of 3 blind A/B wins" [9]; the method is three LLM judges, one run per cell, over file-existence assertions [31]. Its ongoing 77-cell benchmark — no LLM grading, a result against itself, a disclosed grader bug — is the credible artifact, and its task set is untracked [31]. The bar for an evidence claim in this field is therefore a published corpus with a limits section, which is exactly what agent-harness lacks (#455) and what the positioning story depends on.
- **The honest compatibility matrix exists and is paired with no evidence anywhere.** wshobson generates its matrix from `capabilities.py` and proves nothing runs [32]; planning-with-files measures and publishes no matrix; agent-harness has detectors and two compatibility authorities that disagree (`catalog.json` versus `capabilities.json`). Combining a generated matrix with measured behaviour is an open slot no one occupies.
- **Multi-runtime cost lands in host edge cases, not in the abstraction.** planning-with-files' patch stream is OneDrive reparse points, symlinked plan directories, PowerShell routes, Codex Windows hooks [18][26]; the Windows SessionStart hook alone was "reported 29 times" on superpowers [25]. Each runtime added shallow buys a stream of per-host defects and a hit on the depth claim. Breadth belongs in 0.15 with equal depth, or not at all.

## 6. Contrary evidence

- **"Nobody measures whether rules fire" is false in its unbounded form.** Burnd measures skill firing over the same transcripts and attaches a CLAUDE.md patch to every insight [15]; cc-cost reads the same files for cost [16]. The claim survives only as: the only project known to bind a detector to each rule *file*, fail lint on an unmeasured rule, and report hit rate by repository *and by preference variant* — and the per-variant link is the one no comparator can copy without first having variants [15].
- **"Nobody ships switchable behavioural preferences" is false.** planning-with-files, gsd-core and LynxPrompt each ship one to three axes [6][9][13]. agent-harness generalises to nine user-extensible axes, of which three bind to enforcement; the generalisation is real and modest.
- **The loud demand is for runtimes, not for measurement.** 115, 33, 22 and 20 reactions on new-host requests [25]; one user question about whether rules work, ever [19]. Building for latent demand is a bet the field's own numbers do not yet support.
- **Measuring configuration has not sold.** ctxlint is the best instruction-file linter in the set and has nine stars [10][18]. The distinction between measuring a file and measuring behaviour is the whole argument, and it is unproven.
- **The wedge tool's sixty seconds is unproven.** A stranger with their own rules needs declarative detectors to get anything; without them the tool reports six generic patterns, which is Burnd's territory with fewer detectors [15].

## 7. Recommendations

Each is bound to the decision and to the artifact that consumes it. Confidence names the evidence basis.

1. **Lead public copy with the bounded uniqueness sentence, then complementarity.** "The only project we know of that binds a detector to each rule file, fails lint on an unmeasured rule, and reports per-rule hit rate by repository and by preference variant — and exports OTLP to the observability stack you already run." Never the unbounded negative. → `product.json` (#458), `docs/field-scan.md` (#459). *High* [15][28].
2. **Use the field's words.** "Rules" in the headline and topics; "harness" stays as the name, not the pitch; add `claude-code`, `codex`, `agents-md`, `cursor-rules`-class topics. → #458. *High* [7].
3. **Ship the instrument standalone, with declarative detectors and a published corpus.** The sixty-second test is the acceptance bar; the labelled corpus and a tracked task set are what make any evidence claim survive the scrutiny planning-with-files' A/B did not. → #451, #452, #453, #455. *High* on need [19][31]; *medium* on the sixty-second test passing first time.
4. **Close install parity: manifest, packaged path, importer.** Credit rulesync's `import` by name. → #446, #447, #448. *High* [5][25][26][27].
5. **Generate the compatibility matrix from `capabilities.json`, reconcile it with `catalog.json`, and add a graceful-degradation table.** The wshobson model, plus the evidence it lacks. → #460, and the compatibility docs. *High* [32].
6. **Do not add runtimes in 0.13.** State the demand honestly in the field scan; schedule Cursor and Copilot CLI for 0.15 at equal depth. → `roadmap-arc-2026-09-21.md`. *Medium* [5][18][25].
7. **Credit by name.** rulesync (breadth, derived target list, import), ctxlint (lint, contradiction detection), planning-with-files (evidence positioning, floor semantics, the self-incriminating benchmark), wshobson (generated matrix, degradation table), Burnd (nearest neighbour), agents-md-cookbook (the only sourced size cap), superpowers (widest install surface, no breadth claim). → #459. *High*.
8. **Write up #429 and #324 as the worked example**, in the field scan's honest-gaps section rather than as marketing: the instrument caught two of this repository's own shipped features doing nothing. → #461. *High* (this repository's own issues).

## 8. Open questions

- **Does measuring behaviour convert where measuring configuration did not?** Unanswerable from the field; answered only by shipping #453 and counting installs and returning users over a quarter.
- **Are rulesync, gsd-core and wshobson users satisfied, or silent?** Their trackers hold no user voice [18]. A different surface — Discord, Reddit, Discussions — would answer it; not in this run's budget.
- **Do docs landing pages tell a different story from READMEs?** Not compared; rulesync, agnix and gsd-core all have separate docs sites [positioning digest, not found].
- **Detector validity.** Until #455 lands, every hit rate in `harness usage --rules` may be measuring the detector. This is the question the field scan must state about itself.
- **Portability evidence.** No project, including this one, has shown the same rule producing the same behaviour on two runtimes. That would be a first and is not scheduled.

## 9. Source appendix

| [n] | Supports | Publisher | Pub | Accessed | Confidence |
|---|---|---|---|---|---|
| [1] | List membership; category entries; ranking method | [RyanAlberts/best-of-Agent-Harnesses README](https://github.com/RyanAlberts/best-of-Agent-Harnesses) | 2026-09 | 2026-09-21 | high |
| [2] | Configuration and Linting entries | [hesreallyhim/awesome-claude-code README](https://github.com/hesreallyhim/awesome-claude-code) | 2026-09 | 2026-09-21 | high |
| [3] | Configuration & Context Management entries | [jamesmurdza/awesome-ai-devtools README](https://github.com/jamesmurdza/awesome-ai-devtools) | 2026-09 | 2026-09-21 | high |
| [4] | Developer Productivity entries; telemetry class size | [ai-for-developers/awesome-ai-coding-tools README](https://github.com/ai-for-developers/awesome-ai-coding-tools) | 2026-09 | 2026-09-21 | high |
| [5] | 52 derived targets; import/convert; hero line; long-tail table | [dyoshikawa/rulesync](https://github.com/dyoshikawa/rulesync) `src/types/tool-targets.ts`, `tool-target-tuples.ts`, README | 2026-09 | 2026-09-21 | high |
| [6] | MODEL_PROFILES; DepthTier; hero line | [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core) `src/model-profiles.cts`, `src/code-review-depth.cts`, README | 2026-09 | 2026-09-21 | high |
| [7] | Capability matrix as data; generate.py; hero and quickstart gap; vocabulary | [wshobson/agents](https://github.com/wshobson/agents) `tools/adapters/capabilities.py`, README | 2026-09 | 2026-09-21 | high |
| [8] | Developer profile scalars; hosts; hero line; 810× claim | [garrytan/gstack](https://github.com/garrytan/gstack) `bin/gstack-developer-profile`, `hosts/index.ts`, README | 2026-09 | 2026-09-21 | high |
| [9] | `.mode` floor precedence; 3/3 A/B hero; 60+ agents scope | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) `scripts/inject-plan.sh`, README | 2026-09 | 2026-09-21 | high |
| [10] | 90 rules; token thresholds; contradiction axes; hero line | [YawLabs/ctxlint](https://github.com/YawLabs/ctxlint) `context-lint-rules.json`, `src/core/checks/`, README | 2026-09 | 2026-09-21 | high |
| [11] | 200-line cap; Vercel borrowing; rule skew | [agent-sh/agnix](https://github.com/agent-sh/agnix) `rules/claude_md.rs`, README | 2026-09 | 2026-09-21 | high |
| [12] | Manifest-only projection; 16 install sections; commercial line | [obra/superpowers](https://github.com/obra/superpowers) README, repo tree | 2026-09 | 2026-09-21 | high |
| [13] | --boundaries, plan-mode frequency, verbosity presets | [GeiserX/LynxPrompt](https://github.com/GeiserX/LynxPrompt) `cli/src/index.ts`, `packages/shared/src/wizard/ai-behavior.ts` | 2026-09 | 2026-09-21 | high |
| [14] | 32 KiB Codex cap with mechanism; 150/300 line limits | [Taiizor/agents-md-cookbook](https://github.com/Taiizor/agents-md-cookbook) `rules/byte-cap.ts`, `rules/line-budget.ts` | 2026-08 | 2026-09-21 | high |
| [15] | Skill-firing detector; claudeMdPatch; uniqueness chain; sensor gaps | [garvitsurana271/burnd](https://github.com/garvitsurana271/burnd) `detectors/skill-firing.ts`; eval claim-check import | 2026-09 | 2026-09-21 | high |
| [16] | Six cost heuristics, none tied to CLAUDE.md | [lob-labs/cc-cost](https://github.com/lob-labs/cc-cost) | 2026-09 | 2026-09-21 | high |
| [17] | Not open source; per-skill LICENSE.txt | [anthropics/skills](https://github.com/anthropics/skills) `skills/*/LICENSE.txt` | 2026-09 | 2026-09-21 | high |
| [18] | Stars, commits/30d, releases, authorship, sponsors | GitHub REST and GraphQL `repos/<o>/<r>` for eight repositories | 2026-09 | 2026-09-21 | high |
| [19] | The user-asked wedge question | [obra/superpowers#446](https://github.com/obra/superpowers/issues/446) | 2026-02 | 2026-09-21 | high |
| [20] | Codex skills silently fail | [garrytan/gstack#1066](https://github.com/garrytan/gstack/issues/1066) | 2026-04 | 2026-09-21 | high |
| [21] | Nudge reaches user, not model | [OthmanAdi/planning-with-files#239](https://github.com/OthmanAdi/planning-with-files/issues/239) | 2026-09 | 2026-09-21 | high |
| [22] | Silently dropped key; dead-runtime target | [dyoshikawa/rulesync#2509](https://github.com/dyoshikawa/rulesync/issues/2509), [#3078](https://github.com/dyoshikawa/rulesync/issues/3078) | 2026-07 | 2026-09-21 | medium |
| [23] | Gate with no producer; sanitiser with no caller | [open-gsd/gsd-core#4915](https://github.com/open-gsd/gsd-core/issues/4915), [#4923](https://github.com/open-gsd/gsd-core/issues/4923) | 2026-09 | 2026-09-21 | medium |
| [24] | Cost and token-bloat cluster | [obra/superpowers#743](https://github.com/obra/superpowers/issues/743), #2017, #1194, #750, #1120; [garrytan/gstack#1206](https://github.com/garrytan/gstack/issues/1206) | 2026-03 | 2026-09-21 | high |
| [25] | Runtime-demand and install-friction clusters | [garrytan/gstack#393](https://github.com/garrytan/gstack/issues/393), #1703, #1269; [obra/superpowers#429](https://github.com/obra/superpowers/issues/429), #503, #641, #1026 | 2026-03 | 2026-09-21 | high |
| [26] | Usage-guidance demand; npm lag; duplicate copies | [OthmanAdi/planning-with-files#19](https://github.com/OthmanAdi/planning-with-files/issues/19), #50, #213, #53 | 2026-01 | 2026-09-21 | high |
| [27] | Per-skill distribution request | [garrytan/gstack#113](https://github.com/garrytan/gstack/issues/113) | 2026-03 | 2026-09-21 | high |
| [28] | SDK ingestion; OTLP acceptance; no rule concept | [langfuse/langfuse](https://github.com/langfuse/langfuse), [comet-ml/opik](https://github.com/comet-ml/opik), [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) READMEs | 2026-09 | 2026-09-21 | medium |
| [29] | Cap figures 200/150/400/2000 | [Zandereins/schliff](https://github.com/Zandereins/schliff), [sisyphusse1-ops/cc-audit](https://github.com/sisyphusse1-ops/cc-audit), [caliber-ai-org/ai-setup](https://github.com/caliber-ai-org/ai-setup) | 2026-09 | 2026-09-21 | high |
| [30] | NOASSERTION and missing licences | [aryaminus/controlkeel](https://github.com/aryaminus/controlkeel), [c0x12c/ai-toolkit](https://github.com/c0x12c/ai-toolkit) | 2026-09 | 2026-09-21 | high |
| [31] | A/B method and limits; 77-cell benchmark; untracked corpus | [OthmanAdi/planning-with-files docs/evals.md](https://github.com/OthmanAdi/planning-with-files/blob/main/docs/evals.md) | 2026-09 | 2026-09-21 | high |
| [32] | Generated 14×6 matrix; degradation table; no evidence | [wshobson/agents docs/harnesses.md](https://github.com/wshobson/agents/blob/main/docs/harnesses.md) | 2026-09 | 2026-09-21 | medium |

## 10. Staleness map

Computed by `recon_kit.py staleness` from the claim ledger on 2026-09-21, with the competitive pack's bars: features, positioning, validation, licensing and listing claims three months; trajectory and demand six months.

- **Already past their bar, re-verify before any public use:** [19] the superpowers#446 quote (published 2026-02) and [20] gstack#1066 (2026-04). Both were classed as capability claims and given the three-month bar; as sentiment they would carry twelve. The quotes were fetched live this run, so the *text* is current; what may have moved is whether either issue has since been closed or answered.
- **2026-12-01:** every capability, packaging, validation, preference-variant, licensing, positioning and telemetry claim — the whole of sections 1 and 2. Release cadence in this field is daily to weekly, so this is the honest window for "what they ship" [18].
- **2027-02-01 to 2027-03-01:** the trajectory and demand figures — commit counts, authorship, reacted issues, npm lag.

**Earliest re-check: now, for the two issue quotes; otherwise 2026-12-01.** That date is this document's expiry for the field-scan page derived from it; a Refresh run on the same folder is the work order.

## Amendment, 2026-09-23: two projects that measure rule compliance

Added after the original run; the findings above are unchanged and dated 2026-09-21. A scan for
ruleprobe's own planning on 2026-09-23 found two projects that the 2026-09-21 run did not cover,
both measuring per-rule compliance from Claude Code transcripts. Each was read from its primary
source on that date; digests are beside this file.

- **claude-md-doctor**: the model writes per-rule matchers at each checkup, a deterministic script
  replays them, and the model sample-verifies fires; per-rule opportunities, compliance and verdict.
  MIT. [digest](digests/claude-md-doctor-2026-09-23.md)
- **RuleReceipt**: deterministic checks over git commands and file operations, UNCLEAR otherwise
  unless an opt-in model grader runs; source-available licence.
  [digest](digests/rulereceipt-2026-09-23.md)

Consequence: the §6 uniqueness claim in `docs/field-scan.md` is narrowed to the lint gate, the
labelled corpus with a CI floor, per-variant grouping and the second runtime.

