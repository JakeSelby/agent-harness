# Teardown — hesreallyhim/awesome-claude-code

via: `list-hesreallyhim_awesome-claude-code-readme-2026-09-21.md` · publisher: hesreallyhim · pub_date: 2026-09 · accessed: 2026-09-21

No star figures are printed as numbers; each entry carries shields.io badges (created-at, last-commit, license, stars) rendered as images, so no numeric star count is extractable. No tags or simplicity↔capability labels in this list.

## Sections and counts (exact heading names)

- `## Configuration` — 3 entries (L667, L670, L673)
- `## Linting` — 6 entries (L686, L689, L692, L695, L698, L701)

## agent-harness presence

- claim: `grep -c 'JakeSelby/agent-harness'` returns 0 — agent-harness does not appear in this list.
  source: hesreallyhim/awesome-claude-code:README#L0
  publisher: hesreallyhim · pub_date: 2026-09 · accessed: 2026-09-21 · confidence: high · class: listing
  via: list-hesreallyhim_awesome-claude-code-readme-2026-09-21.md

## Configuration (3)

- claim: Fixing Opus 5 — https://github.com/disler/fixing-smartass-opus-5 — by disler — "A single appendable system prompt that retunes Opus 5's communication channel — cutting verbal tics, heading theater, and output-token bloat — passed via `--append-system-prompt-file` with no build s"
  source: hesreallyhim/awesome-claude-code:README#L667 · class: capability
- claim: Rulesync — https://github.com/dyoshikawa/rulesync — by dyoshikawa — "A Node.js CLI tool that automatically generates configs (rules, ignore files, MCP servers, commands, and subagents) for various AI coding agents. Rulesync can convert configs between Claude Code and o"
  source: …#L670 · class: packaging — matched flag: **importing or converting config between tools**
- claim: tweakcc — https://github.com/Piebald-AI/tweakcc — by Piebald-AI — "Command-line tool to customize your Claude Code installation: themes, thinking verbs, spinners, and input-box styling, plus deeper tweaks like custom toolsets, system-prompt edits, input pattern highli"
  source: …#L673 · class: capability

## Linting (6)

- claim: agents-md-cookbook — https://github.com/Taiizor/agents-md-cookbook — by Taiizor — "The tested, tool-agnostic AGENTS.md kit — verified templates, a CI linter, and migrators from .cursorrules/CLAUDE.md/Copilot/Windsurf/Cline/Aider."
  source: …#L686 · class: validation — matched flags: **linting instruction files**, **converting config between tools**
- claim: agnix — https://github.com/agent-sh/agnix — by agent-sh — "The linter and LSP for AI coding assistants — validates CLAUDE.md, AGENTS.md, SKILL.md, hooks, and MCP config, with autofixes and IDE plugins."
  source: …#L689 · class: validation — matched flag: **linting instruction files**
- claim: BlockWatch — https://github.com/mennanov/blockwatch — by mennanov — "A language-agnostic linter (Rust) that keeps co-dependent code, docs, and config in sync, with a Claude Code plugin skill."
  source: …#L692 · class: validation — matched flags: **linting**, **plugin**
- claim: Ctxlint — https://github.com/ctxlint/Ctxlint — by ctxlint — "A CLI linter for AI agent context files that catches stale references, dead commands, and hardcoded secrets, with a modular tested rule set."
  source: …#L695 · class: validation — matched flag: **linting instruction files**
- claim: Schliff — https://github.com/Zandereins/schliff — by Zandereins — "Deterministic quality scorer for AI agent instruction files — 8-dimension scoring with security, multi-format (SKILL.md, CLAUDE.md, .cursorrules, AGENTS.md), anti-gaming detection, zero dependencies"
  source: …#L698 · class: validation — matched flag: **scoring instruction files**
- claim: Upkeep — https://github.com/wei18/Upkeep — by wei18 — "Upkeep — an AI audit crew for your repo. Catches docs/spec/asset drift with evidence; output-only. Claude Code plugin/skill + reusable CI workflow."
  source: …#L701 · class: validation — matched flag: **plugin**

## Flag roll-up

- Importing/converting config between tools: Rulesync (L670), agents-md-cookbook (L686)
- Linting or scoring instruction files: all six Linting entries (L686–L701)
- Preference profiles/presets/modes: none
- Measuring or observing agent behaviour: none in these two sections
- Plugin manifest or marketplace: BlockWatch (L692), Upkeep (L701) — both "Claude Code plugin/skill", neither a marketplace
