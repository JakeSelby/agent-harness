# Teardown — jamesmurdza/awesome-ai-devtools

via: `list-jamesmurdza_awesome-ai-devtools-readme-2026-09-21.md` · publisher: jamesmurdza · pub_date: 2026-09 · accessed: 2026-09-21

No star figures, tags, or simplicity↔capability labels are printed in this list.

## Section and count (exact heading name)

- `### Configuration & Context Management` — 29 entries (L359–L387), under parent `## Agent Infrastructure`
- Section blurb (L357): "Tools that manage and sync AI agent configurations, rules, and context across editors:"

## agent-harness presence

- claim: `grep -c 'JakeSelby/agent-harness'` returns 0 — agent-harness does not appear in this list.
  source: jamesmurdza/awesome-ai-devtools:README#L0
  publisher: jamesmurdza · pub_date: 2026-09 · accessed: 2026-09-21 · confidence: high · class: listing
  via: list-jamesmurdza_awesome-ai-devtools-readme-2026-09-21.md

## Entries (29)

Each: name — url — verbatim description (trimmed 200 chars) — class. `source:` is jamesmurdza/awesome-ai-devtools:README#L<line>; publisher jamesmurdza; pub_date 2026-09; accessed 2026-09-21; confidence high; via the import filename above.

- L359 Context7 — https://context7.com/ — "Documentation platform that provides up-to-date, version-specific documentation and code examples for any library directly into Cursor, Claude Code, Windsurf, and other AI coding tools." — class: capability
- L360 ctxlint — https://github.com/YawLabs/ctxlint — "Open-source linter for AI context files (CLAUDE.md, .cursorrules, copilot-instructions.md) that catches stale paths, wrong commands, and token waste by validating against the real codebase." — class: validation — flag: **linting instruction files**
- L361 Entroly — https://github.com/juyterman1000/entroly — "Open-source context optimization engine that cuts AI token costs by 70-95%. Uses submodular knapsack selection and PRISM reinforcement learning to provide the exact context needed to 65+ supported AI" — class: capability
- L362 lean-ctx — https://leanctx.com — "Open-source context runtime for AI coding agents. MCP server (optional shell hook) that compresses file reads, shell output, and codebase search to reduce token usage, often 60–99% on supported workfl" — class: capability
- L363 Caliber — https://github.com/rely-ai-org/caliber — "Open-source CLI that scans your codebase and generates AI agent configs (CLAUDE.md, .cursorrules, skills, MCPs) for Claude Code, Cursor, and Codex. Scores your setup 0-100 and recommends MCP servers." — class: validation — flags: **scoring instruction files**, **converting config between tools**
- L364 claude-snapshot — https://github.com/adhenawer/claude-snapshot — "Export your entire Claude Code setup (settings, plugins, hooks, CLAUDE.md, MCP configs) as a portable `.tar.gz`. Diff before applying, restore on another machine in under 2 minutes. No network, no dae" — class: packaging — flags: **importing config**, **plugin marketplace** (install line: `/plugin marketplace add adhenawer/claude-snapshot`)
- L365 claude-overlay — https://github.com/mzmmoazam/claude-overlay — "CLI for managing Claude Code project configs across custom providers (Databricks, Bedrock, OpenRouter, LiteLLM, Cloudflare). Handles overlay merge/remove, web search MCP setup, and multi-provider swit" — class: preference-variants — flag: **profiles/presets/modes** (overlay merge, provider switching)
- L366 LynxPrompt — https://github.com/GeiserX/LynxPrompt — "Self-hostable platform for managing AI IDE configuration files. Generates, syncs, and shares configs (.cursorrules, CLAUDE.md, copilot-instructions.md, etc.) across 30+ AI coding assistants via web UI" — class: packaging — flags: **converting config between tools**, **federated blueprint marketplace**
- L367 Conduit8 — https://github.com/conduit8/conduit8 — "CLI registry for discovering, installing, and managing Claude Code skills. Search 20+ curated skills by keyword or category, install directly to ~/.claude/skills/ with one command." — class: packaging — flag: **marketplace/registry**
- L368 TokRepo — https://github.com/henu-wang/tokrepo — "Cross-agent registry and CLI for discovering and installing 220+ AI assets including skills, prompts, MCP configs, and workflows." — class: packaging — flag: **marketplace/registry**
- L369 Domscribe — https://www.domscribe.com/ — "Pixel-to-code bridge that captures runtime context (props, state, source location) from running web apps and exposes it to AI coding agents via MCP." — class: capability
- L370 faf-cli — https://github.com/Wolfe-Jam/faf-cli — "Foundational AI-context format. Generates persistent project DNA (.faf files) that give any AI instant, structured context. IANA-registered (application/vnd.faf+yaml). Works with Claude, Gemini, Grok," — class: packaging — flag: **cross-tool config format**
- L371 ContextMCP — https://contextmcp.ai — "Self-hosted semantic search across documentation from various sources for AI agents." — class: capability
- L372 AgentsKB — https://agentskb.com — "Knowledge base with 39K+ researched technical Q&As accessible via MCP server, REST API, or web search. Integrates with Claude Code, Cursor, and Cline." — class: capability
- L373 Not Human Search — https://nothumansearch.ai — "Search engine for the agentic web. Indexes 2,000+ agent-ready sites ranked 0–100 on agentic readiness (llms.txt, OpenAPI, MCP, ai-plugin.json, structured API). Itself an MCP server with 8 tools" — class: validation — flag: **scoring**
- L374 CLIRank — https://clirank.dev — "Independent scorecard ranking 416+ APIs across 48 categories by how well they work with AI coding agents (Claude Code, Cursor, Codex, Cline, Aider). 8-signal rubric (SDK, env auth, headless, JSON, CLI" — class: validation — flag: **scoring**
- L375 Zenable — https://zenable.io/ — "AI guardrails that learn your team's standards and enforce them on coding agents." — class: capability
- L376 pi-steering-hooks — https://github.com/samfoy/pi-steering-hooks — "Deterministic before-tool-call guardrails for the pi coding agent. Enforces rules (no force push, conventional commits, etc.) via regex pattern matching on tool inputs — zero tokens, 100% reliable. Cu" — class: validation — flag: **observing agent behaviour** (before-tool-call inspection)
- L377 Spartan AI Toolkit — https://github.com/spartan-stratos/spartan-ai-toolkit — "Engineering discipline layer for AI coding agents. 67 slash commands with quality gates enforce TDD, code review, and atomic commits. Configurable rules for any stack. Works with Claude Code, Codex, Cu" — class: capability
- L378 Nex — https://github.com/nex-crm/nex-as-a-skill — "Organizational context and memory for AI agents. Connects email, Slack, CRM, and 100+ tools into one knowledge graph with a 60-tool MCP server and persistent memory across agent sessions." — class: capability
- L379 Agentify — https://github.com/koriyoshi2041/agentify — "CLI tool that transforms any OpenAPI spec into 9 agent interface formats (MCP server, AGENTS.md, CLAUDE.md, .cursorrules, Skills, llms.txt, GEMINI.md, A2A Card, CLI) with a single command. Tiered gener" — class: packaging — flag: **converting config between tools**
- L380 ContextKit — https://nova-labs.dev/contextkit/generate — "Free web-based generator for AI coding config files. Creates CLAUDE.md, .cursorrules, codex.md, and GEMINI.md from a single form with framework-specific rules. Client-side, no data sent to servers." — class: packaging — flag: **generating config across tools**
- L381 skill-optimizer — https://github.com/fastxyz/skill-optimizer — "CLI that benchmarks SDK, CLI, and MCP guidance docs (SKILL.md) against multiple LLMs and runs an iterative optimizer to rewrite them until every configured model meets a score floor." — class: validation — flags: **scoring instruction files**, **measuring agent behaviour**
- L382 KubeStellar Console kc-agent — https://github.com/kubestellar/console — "MCP server that bridges AI coding agents (Claude Code, Copilot, Codex) to multi-cluster Kubernetes APIs. Enables natural language queries across clusters, workload placement, policy enforcement, and re" — class: capability
- L383 SwarmVault — https://github.com/swarmclawai/swarmvault — "Local-first RAG knowledge vault and MCP server. Compiles raw sources (books, notes, transcripts, exports, datasets, slide decks, files, URLs, code) into a durable markdown wiki with a knowledge graph a" — class: capability
- L384 claude-code-pro-pack — https://github.com/sisyphusse1-ops/claude-code-pro-pack — "Drop-in 12-rule `CLAUDE.md` + `AGENTS.md` baseline that closes common agent-orchestration failures (token spirals, silent partial failures, two-pattern pollution). Includes PRD generator prompt, browse" — class: capability
- L385 cc-audit — https://github.com/sisyphusse1-ops/cc-audit — "Single-file Python linter that scores any `CLAUDE.md` / `AGENTS.md` against a 12-rule baseline. Flags leaked secrets (GitHub PATs, AWS keys, PayPal links), the 200-line compliance cliff, and missing pr" — class: validation — flags: **linting and scoring instruction files**
- L386 GAAI Framework — https://github.com/Fr-e-d/GAAI-framework — "Drop-in governance layer for AI coding tools. Backlog-first delivery, cross-session memory, decision tracking, QA gates, and autonomous delivery daemon. Works with Claude Code, Cursor, Codex CLI, Gemin" — class: capability
- L387 intelligence-sync — https://github.com/ainova-systems/intelligence-sync — "One source of truth for AI coding rules across every IDE. Author rules, agents, and skills once in plain markdown, and the engine routes them into each tool's native format (Claude Code, Cursor, Copilo" — class: packaging — flag: **converting config between tools**

## Flag roll-up

- Import/convert config between tools: L363, L364, L366, L370, L379, L380, L387 (7)
- Preference profiles, presets or modes: L365 (1) — the thinnest class in the section
- Lint or score instruction files: L360, L363, L373, L374, L381, L385 (6)
- Measure or observe agent behaviour: L376, L381 (2)
- Plugin manifest or marketplace: L364, L366, L367, L368 (4)
