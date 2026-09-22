# Positioning & messaging — round 1, gatherer 1

Method: eight project READMEs read via `gh api repos/<o>/<r>/readme` on 2026-09-21. No web
searches used. `pub_date` is the repo's `pushed_at` month, i.e. the README text is current as of
that push. All eight repos were pushed within 24 hours of the fetch, so every hero line below is
current under the ≤3-month freshness rule.

## Claims

- claim: Rulesync's hero sells mechanical fan-out, not methodology — "A Node.js CLI tool that automatically generates configuration files for various AI development tools from unified AI rule files. Features selective generation, comprehensive import/export capabilities, and supports major AI development tools with rules, commands, MCP, ignore files, subagents and skills."
  source: dyoshikawa/rulesync:README.md
  publisher: dyoshikawa
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: Rulesync's breadth is a long tail — its AI-tools table carries 50 target rows across 9 feature columns, but CodeBuddy Code supports 1 of 9, and Replit and DeepSeek Harness 2 of 9; separate notes mark Continue, Roo Code and Tabnine CLI as end-of-life targets kept only as "frozen-compatibility" so "existing output keeps working — it just will not track anything new."
  source: dyoshikawa/rulesync:README.md (SUPPORTED_TOOLS_AI table, Deprecation notes)
  publisher: dyoshikawa
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: GSD Core leads with a named failure mode rather than a feature list — "A light-weight meta-prompting, context engineering, and spec-driven development system for Claude Code, OpenCode, Antigravity CLI, Kimi CLI, Kilo, Codex, Copilot, Cursor, Windsurf, and more." and "It solves context rot — the quality degradation that accumulates as an AI fills its context window."
  source: open-gsd/gsd-core:README.md
  publisher: open-gsd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: GSD Core's nine-runtime hero is installer-mediated projection and the README says so explicitly — "The installer prompts for your runtime ... The installer is required for cross-runtime compatibility — do not copy files from `agents/` or `commands/` directly." The trailing "and more" is never enumerated in the README; it defers to `docs/how-to/install-on-your-runtime.md`.
  source: open-gsd/gsd-core:README.md
  publisher: open-gsd
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: gstack is positioned on the author's identity and productivity numbers, not on the artifact — "I'm Garry Tan, President & CEO of Y Combinator ... gstack is my answer" and "It turns Claude Code into a virtual engineering team ... Twenty-three specialists and eight power tools, all slash commands, all Markdown, all free, MIT license."
  source: garrytan/gstack:README.md
  publisher: Garry Tan
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: gstack's headline evidence is self-measured and pre-defended, not behavioural — "my 2026 run rate is ~810× my 2013 pace (11,417 vs 14 logical lines/day) ... Measured across 40 public + private `garrytan/*` repos including Bookface, after excluding one demo repo", with a rebuttal doc `docs/ON_THE_LOC_CONTROVERSY.md` linked in the hero; it measures the author's output, never that gstack's roles changed an agent's behaviour.
  source: garrytan/gstack:README.md
  publisher: Garry Tan
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: wshobson/agents is the closest positional neighbour to a one-source-many-runtimes harness and says so in the hero — "Production-ready agentic workflow building blocks: 94 plugins, 202 agents, 183 skills, 105 commands — built for Claude Code and consumed natively by OpenAI Codex CLI, Cursor, OpenCode, the Antigravity CLI, GitHub Copilot, and Pi from a single Markdown source" and "One source-of-truth (`plugins/`), six target harnesses ... idiomatic, harness-native artifacts — not lowest-common-denominator translations."
  source: wshobson/agents:README.md
  publisher: wshobson
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: "consumed natively by ... six target harnesses" is half manifest and half build step — the same README's quickstart says only "Codex and Cursor install natively from the committed registries", while "Antigravity, OpenCode, and Pi install via clone + generate (the transformed trees are gitignored)", i.e. three of six require the user to run `make generate HARNESS=<x>` locally.
  source: wshobson/agents:README.md (Quick start)
  publisher: wshobson
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: planning-with-files is the only project in the set whose hero line is an evidence claim — "The planning skill your agent cannot ignore. Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives `/clear`, and 3 out of 3 blind A/B wins to show it works."
  source: OthmanAdi/planning-with-files:README.md
  publisher: OthmanAdi
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: evidence-positioning

- claim: planning-with-files backs the hero with a disclosed method and its own limits — "Evaluated with Anthropic's skill-creator framework: skill v2.21.0, model `claude-sonnet-4-6`, 2026-03-06. 10 parallel subagents, 5 task types, 30 objectively verifiable assertions, 3 blind A/B comparisons", assertions 29/30 with the skill vs 2/30 without, recovery 5.0 turns vs 13.3, each carrying a caveat: "Treat it as the project's own measurement, not an independent comparison" and "historical evidence rather than a fresh measurement of the current default."
  source: OthmanAdi/planning-with-files:README.md (Benchmark Results)
  publisher: OthmanAdi
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: evidence-positioning

- claim: planning-with-files' "60+ agents" is a standard-conformance number, not 60 adapters — the README scopes it as "Installs across 60+ agents via the Agent Skills standard, with native plugins for Claude Code, Codex CLI, Pi, Hermes Agent, OpenCode and DeepSeek Harness", and its own hook table shows depth only on those six (Claude Code 6 hooks, Codex 7, Pi 8, Hermes 3, OpenCode 4, DeepSeek Harness 4).
  source: OthmanAdi/planning-with-files:README.md
  publisher: OthmanAdi
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: ctxlint positions on staleness with a concrete accusation — "Lint your AI agent context files, MCP server configs, and session data against your actual codebase ... 16 AI tools, 8 MCP clients, cross-project consistency, auto-fix" and "Your `CLAUDE.md` is lying to your agent. Your `.mcp.json` has a hardcoded API key. ctxlint catches both."
  source: YawLabs/ctxlint:README.md
  publisher: YawLabs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: ctxlint's "16 AI tools" checks out as a file-format count — its Supported Context Files table lists exactly 16 rows — but the claim is about parsing file paths, not tool integration, and its skill/agent linting is thin and flagged as such: "5 rules for auditing Claude Code skill (`SKILL.md`) and agent (`.md`) definitions ... (v1, experimental)."
  source: YawLabs/ctxlint:README.md (Supported Context Files; AGENT_SKILL_LINT_SPEC.md reference)
  publisher: YawLabs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: ctxlint's "measurement" is file scoring, not behaviour — "Token-aware — shows how much context window your files consume and flags redundant content"; nothing in the README claims a linted file produced a different agent outcome.
  source: YawLabs/ctxlint:README.md
  publisher: YawLabs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: agnix positions as a pre-flight linter — "Lint agent configurations before they break your workflow" — and builds its case entirely on third-party research about other people's failures: "Vercel's research found skills invoke at 0% without correct syntax. One wrong field and your skill is invisible" and "66% of developers cite ['almost right'] as their biggest AI frustration."
  source: agent-sh/agnix:README.md
  publisher: agent-sh
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: agnix borrows evidence for the problem but offers none for the fix — the cited Vercel and Stack Overflow figures establish that misconfiguration hurts; no claim in the README shows an agnix-clean config changing agent behaviour, and its rule coverage is heavily skewed (Claude Code 53 rules and Kiro 53 against Cline 4, Copilot 6, Gemini CLI 9 across 9 supported tools).
  source: agent-sh/agnix:README.md (Why agnix?; Supported Tools)
  publisher: agent-sh
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: Superpowers sells a methodology and never mentions multi-runtime breadth in its hero — "Superpowers is a complete software development methodology for your coding agents, built on top of a set of composable skills and some initial instructions that make sure your agent uses them."
  source: obra/superpowers:README.md
  publisher: obra (Jesse Vincent)
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

- claim: Superpowers understates rather than overstates — its hero claims no breadth, yet the table of contents ships install sections for 16 runtimes (Claude Code, Antigravity, Codex App, Codex CLI, Cursor, Devin CLI, Factory Droid, Gemini CLI, GitHub Copilot CLI, Grok Build CLI, Kimi Code, OpenCode, Pi, Qwen Code, Hermes Agent, Muse), making it the widest per-runtime install surface in the set; it is also the only project with a commercial motion — "If you're using Superpowers in enterprise and could benefit from commercial support, additional tooling, or managed spending, please don't hesitate to drop us a line at <contact address in the source README>."
  source: obra/superpowers:README.md (Table of Contents; Commercial Services)
  publisher: obra (Jesse Vincent)
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: "harness" is near-absent as self-description — of the eight hero lines, only wshobson/agents uses it ("six target harnesses", "harness-native artifacts"), and there it names the *target runtimes*, not the tool doing the projecting; every other project calls the targets "AI development tools", "runtimes", "agents", "hosts" or "AI coding tools".
  source: dyoshikawa/rulesync:README.md; open-gsd/gsd-core:README.md; wshobson/agents:README.md; OthmanAdi/planning-with-files:README.md; obra/superpowers:README.md
  publisher: multiple
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: vocabulary

- claim: "skill" is the most common noun across the eight hero lines, appearing in four (rulesync "subagents and skills", wshobson "183 skills", planning-with-files "The planning skill your agent cannot ignore", superpowers "composable skills"); "config/configuration" appears in three (rulesync "configuration files", ctxlint "MCP server configs", agnix "agent configurations"); "rules" appears in two (rulesync "unified AI rule files", ctxlint "context files ... `.cursorrules`" in body only).
  source: all eight README hero lines (see per-project claims above)
  publisher: multiple
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: vocabulary

- claim: "context engineering" is a live but minority term — GSD Core uses it twice in its hero block ("a light-weight meta-prompting, context engineering, and spec-driven development system", "GSD Core is a context-engineering and spec-driven development framework") and ctxlint uses the adjacent "context linting"; no other project in the set uses the phrase in its hero.
  source: open-gsd/gsd-core:README.md; YawLabs/ctxlint:README.md
  publisher: open-gsd; YawLabs
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: vocabulary

- claim: Stated audiences split three ways — gstack names its reader explicitly ("Founders and CEOs ... First-time Claude Code users ... Tech leads and staff engineers"), ctxlint names a team scenario ("a team with 5 context files, 3 MCP configs, and 2 people who touched the build system last week"), and the other six name no audience at all, describing only the artifact.
  source: garrytan/gstack:README.md; YawLabs/ctxlint:README.md; and the six other READMEs
  publisher: multiple
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: positioning

- claim: Attention in this field is uncorrelated with projection breadth — star counts on 2026-09-21 run obra/superpowers 289,770, garrytan/gstack 133,872, wshobson/agents 39,857, OthmanAdi/planning-with-files 27,047, open-gsd/gsd-core 9,708, dyoshikawa/rulesync 1,458, agent-sh/agnix 421, YawLabs/ctxlint 9; the two linters sit at the bottom and the two methodology projects at the top.
  source: GitHub REST API `repos/<o>/<r>` for all eight repositories
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: positioning

## Leads

- `docs/harnesses.md` in wshobson/agents is described as "the capability matrix" — the per-runtime
  honesty artifact this field seems to be converging on. Worth reading for what a projection tool
  owes its user when adapters differ in depth. Not read this run.
- `docs/evals.md` in OthmanAdi/planning-with-files holds the full method, arms and disclosed limits
  behind the only evidence-based hero in the set. The single best model for an evidence claim that
  survives scrutiny. Not read this run.
- `docs/ON_THE_LOC_CONTROVERSY.md` in garrytan/gstack is a pre-emptive rebuttal doc. Evidence of
  what happens when a config project leads with a productivity multiple. Not read this run.
- rulesync's `https://rulesync.dyoshikawa.com/reference/supported-tools` is the "full mode
  breakdown (project / global / simulated / MCP tool config)" — the README concedes a ✅ means
  "supported in at least one mode", so the real depth-of-support picture lives there. Not read.
- `open-gsd/gsd-core:docs/how-to/install-on-your-runtime.md` should resolve the unenumerated
  "and more" in its nine-runtime hero. Not read this run.
- GSD Core ships hero lines in five languages (pt-BR, zh-CN, ja-JP, ko-KR). Whether the positioning
  survives translation is a signal about how concrete it is. Not checked.

## Not found

- No project docs landing pages were fetched; every claim here comes from a README. rulesync,
  agnix and GSD Core all maintain separate docs sites whose hero lines may differ from the README's
  and were not compared. Both budgets favoured reading all eight primary sources over two of them.
- No web searches were run, so no third-party or dated commentary corroborates any positioning
  claim; everything is the project speaking about itself.
- No pub_date better than the repo's last-push month was established. GitHub's README endpoint
  returns no per-file history, so a hero line unchanged for a year and one rewritten yesterday both
  read as 2026-09 here.
- Nothing in the set positions on *portability evidence* — no project claims that the same rule
  produced the same agent behaviour across two runtimes. planning-with-files measures a single
  skill against a no-skill baseline, which is the nearest thing and still not a cross-runtime claim.
- No project in the set positions on being usable by someone other than its author: no onboarding
  time, no "first hour" claim, no adoption metric anywhere in the eight hero lines.
