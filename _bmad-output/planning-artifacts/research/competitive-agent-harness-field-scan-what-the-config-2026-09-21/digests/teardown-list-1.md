# Teardown — RyanAlberts/best-of-Agent-Harnesses

via: `list-RyanAlberts_best-of-Agent-Harnesses-readme-2026-09-21.md` · publisher: RyanAlberts · pub_date: 2026-09 · accessed: 2026-09-21

## Sections and counts (exact heading names)

- `## Coding harness configs and SDKs` — 17 entries (L208–L224)
- `## Personal agent runtimes` — 13 entries (L234–L246)
- `## Evaluation and benchmarking harnesses` — 19 entries (L354–L372)
- `## Observability and eval-ops` — 4 entries (L382–L385)
- `## Guide to rankings` — 7 ranking criteria (L138–L144)

## agent-harness presence

- claim: `grep -c 'JakeSelby/agent-harness'` returns 0 — agent-harness does not appear in this list.
  source: RyanAlberts/best-of-Agent-Harnesses:README#L0
  publisher: RyanAlberts · pub_date: 2026-09 · accessed: 2026-09-21 · confidence: high · class: listing
  via: list-RyanAlberts_best-of-Agent-Harnesses-readme-2026-09-21.md

## Guide to rankings (quoted verbatim)

> "⭐ **Stars** — GitHub star count, captured 2026-09-20; tables sort by stars descending." (L138)
> "⚖️ **Simplicity ↔ capability** — adoption surface, 4 tiers: **super simple** (a format, one concept) → **mostly simple** (thin layer) → **slightly complex** (real SDK) → **complex** (product suite)." (L139)
> "★ **Headless-ready** — designed for unattended runs, batches, and fleets (the top of the autonomy scale: step-gated → checkpoint-gated → bounded → headless)." (L140)
> "✱ **Durable** — persisted execution state survives restarts mid-task (the top of the recovery scale: none → retry → resumable → durable)." (L141)
> "✅ **Open source** — ✅ standard OSS license · ⚠️ source-available/restricted · ❓ no or unclear license." (L142)
> "🏷️ **Tags** — capability chips auto-derived from descriptions; full cross-reference in [TAGS.md](TAGS.md)." (L143)
> "🎯 **Examples** — one concrete "show me it in action" link per project, not a docs root." (L144)
> "Every project's full autonomy and recovery tier is plotted in the [grid above](#the-landscape-at-a-glance) and carried in [harnesses.json](harnesses.json) and [llms.txt](llms.txt); scores are editorial, from public docs — maintainer corrections via issue/PR are merged fast." (L146)

Section blurb, `## Coding harness configs and SDKs` (L204): "_Skill packs, slash-command libraries, meta-prompting frameworks, and official SDKs that give you the harness (the agent loop, planning, memory, hooks) without bundling a specific IDE or CLI shell._"

## Coding harness configs and SDKs (17)

- claim: superpowers — https://github.com/obra/superpowers — 289k ⭐ — "Performance-oriented harness pack for Claude Code and 13 other harnesses (Codex, Cursor, OpenCode, Gemini CLI, more): skills, instincts, memory, security, research-first workflows." — tags `memory · cli · ide` — "complex (multi-IDE skill stack — product suite)"
  source: RyanAlberts/best-of-Agent-Harnesses:README#L208 · class: capability
- claim: Anthropic Skills — https://github.com/anthropics/skills — 177k ⭐ — "Anthropic's official Agent Skills repository: SKILL.md-based folders (instructions, scripts, resources) Claude dynamically loads on Claude Code, Claude.ai, and the API." — "mostly simple (official skills format)" — ⚠️ Anthropic terms
  source: …#L209 · class: packaging
- claim: GStack — https://github.com/garrytan/gstack — 134k ⭐ — "Garry Tan's Claude Code skill stack: 23 slash-command modes (CEO/eng/design review, QA, ship, browse, retro, …) that structure one assistant as a virtual engineering team." — tags `typescript` — "slightly complex (multi-role slash-command harness)"
  source: …#L210 · class: preference-variants (modes)
- claim: addyosmani/agent-skills — https://github.com/addyosmani/agent-skills — 97.5k ⭐ — "Addy Osmani's production-grade skill pack: 24 engineering skills and 4 specialist agent personas that encode senior-dev workflows (spec through deploy) across 70+ coding agents…" — tags `workflow · ide` — "mostly simple (skills bundle, cross-agent)"
  source: …#L211 · class: capability
- claim: awesome-claude-code — https://github.com/hesreallyhim/awesome-claude-code — 54.3k ⭐ — "Large community-curated index of Claude Code skills, slash commands, status lines, and plugins—resources for extending the harness, not a harness itself…" — "super simple (curated resource index)"
  source: …#L212 · class: listing
- claim: wshobson/agents — https://github.com/wshobson/agents — 39.8k ⭐ — "Cross-harness marketplace of drop-in subagents and skills for Claude Code, Codex CLI, Cursor, OpenCode, and Copilot; specialized, production-ready agent definitions you install rather than hand-write." — tags `multi-agent · cli · ide` — "super simple (drop-in agent packs)"
  source: …#L213 · class: packaging (marketplace)
- claim: planning-with-files — https://github.com/OthmanAdi/planning-with-files — 27k ⭐ — "Skill for persistent, file-based planning across long-running coding-agent sessions: crash-proof markdown plans, session recovery after `/clear`/compaction, and a deterministic completion gate…" — tags `memory` — "mostly simple (skill, file-based state)"
  source: …#L214 · class: capability
- claim: SWE-agent ★ — https://github.com/SWE-agent/SWE-agent — 20.4k ⭐ — "LM-driven harness built for SWE-bench: edit state, command execution, and issue-focused loop…" — tags `memory · evals · python` — "slightly complex (SWE-bench pairing, stateful edits)"
  source: …#L215 · class: validation
- claim: get-shit-done — https://github.com/open-gsd/gsd-core — 9.7k ⭐ — "Goal-backward planning and wave-based execution over fresh context windows; avoids context rot by design." — tags `cli · python` — "mostly simple (meta-prompting, you own stack)"
  source: …#L216 · class: capability
- claim: Claude Agent SDK ★ — https://github.com/anthropics/claude-agent-sdk-python — 8.1k ⭐ — "Official Anthropic SDK (Python + TypeScript…): built-in tools, MCP, long-running coding agents with session bridging." — tags `mcp · memory · python · typescript` — "complex (full SDK)"
  source: …#L217 · class: capability
- claim: agents-cli — https://github.com/google/agents-cli — 6k ⭐ — "Google's official CLI and skill pack that layers agent-creation, evaluation, and deployment skills on top of whatever coding assistant you already run…" — tags `evals · cli` — "mostly simple (skills/CLI layer, no new runtime)"
  source: …#L218 · class: validation
- claim: skillhub — https://github.com/iflytek/skillhub — 5.1k ⭐ — "iFlytek's self-hosted registry for publishing, versioning, and governing agent skill packages—the harness config layer treated as an enterprise artifact store…" — tags `local · cli · ide` — "mostly simple (skill registry/governance)"
  source: …#L219 · class: packaging
- claim: Meta-Harness — https://github.com/stanford-iris-lab/meta-harness — 1.6k ⭐ — "Reference implementation from the Meta-Harness paper: an academic testbed for harness-engineering research, not a product…" — "slightly complex (research reference implementation)"
  source: …#L220 · class: validation
- claim: RepoMaster ★ — https://github.com/QuantaAlpha/RepoMaster — 553 ⭐ — "Repo-scoped research harness: builds function-call and module-dependency graphs to explore only what's needed; large relative gains on MLE-bench and GitTaskBench with lower token use." — tags `workflow · python` — "slightly complex (graph-based exploration)"
  source: …#L221 · class: capability
- claim: AutoHarness — https://github.com/aiming-lab/AutoHarness — 378 ⭐ — "Lightweight governance harness: wraps any LLM client in ~2 lines for automated harness engineering—6–14 step pipeline, YAML constitution, risk-pattern matching, session persistence with cost tracking, multi-agent profiles." — tags `memory · multi-agent · provider-agnostic · python` — "super simple (2-line wrapper, YAML gov)"
  source: …#L222 · class: preference-variants (multi-agent profiles) + telemetry (cost tracking)
- claim: LoopTroop — https://github.com/looptroop-ai/LoopTroop — 150 ⭐ — "Config layer that chains LLM councils for planning, Ralph loops for iterative refinement, and OpenCode worktrees for shipping." — tags `typescript` — "mostly simple (config pipeline over OpenCode)"
  source: …#L223 · class: capability
- claim: pmstack — https://github.com/RyanAlberts/pmstack — 8 ⭐ — "Claude Code config for AI product managers: CLAUDE.md plus skills for competitive analysis, PRD-from-signal, metric frameworks, stakeholder briefs, and agent eval design. "GStack for PMs."" — tags `evals` — "super simple (skills bundle, PM-focused)"
  source: …#L224 · class: capability

## Personal agent runtimes (13)

Blurb (L230): "_Always-on, self-hosted agents you run as a daemon and talk to from chat apps…_"

- OpenClaw ★ — https://github.com/openclaw/openclaw — 390k ⭐ — "Self-hosted, always-on personal agent (formerly Clawdbot/Moltbot): a gateway + event-loop runtime that treats messages, heartbeats, crons, and webhooks as one input queue… 13,700+ community skills" — `typescript · multi-agent` — "complex (always-on runtime, channels, skill ecosystem)" — #L234 · class: capability
- Hermes ★ — https://github.com/NousResearch/hermes-agent — 247k ⭐ — "Nous Research's self-improving agent: a learning loop turns experience into reusable skills, builds a persistent user model across sessions, and checkpoints state to disk with rollback…" — `memory · python · provider-agnostic` — "slightly complex (lean runtime, learning loop, disk-first memory)" — #L235 · class: capability
- AnythingLLM ★ — https://github.com/Mintplex-Labs/anything-llm — 66.3k ⭐ — "Self-hosted "AI second brain" harness: chat with your documents, run built-in agent skills…" — `rag · typescript` — "complex (server + desktop + multi-user; product suite)" — #L236 · class: capability
- nanobot — https://github.com/HKUDS/nanobot — 48.4k ⭐ — "Ultra-lightweight, self-hosted personal agent framework…" — `mcp · memory · local · python` — "mostly simple (lightweight daemon, chat/MCP)" — #L237 · class: capability
- CowAgent — https://github.com/zhayujie/CowAgent — 47.1k ⭐ — "Self-hosted harness (formerly chatgpt-on-wechat) that plans tasks, runs tools/skills, and self-evolves via memory…" — `memory · python` — "slightly complex (multi-channel, self-evolving)" — #L238 · class: capability
- Khoj ★ — https://github.com/khoj-ai/khoj — 37.4k ⭐ — "Self-hostable "AI second brain": answers over your docs and the web, custom agents, scheduled automations…" — `python` — "complex (server + clients — product suite)" — #L239 · class: capability
- Eliza ★ — https://github.com/elizaOS/eliza — 19.4k ⭐ — "Open "agentic operating system" (elizaOS): persistent multi-agent runtime with character files, a plugin ecosystem, and social/platform integrations…" — `memory · multi-agent · typescript` — "complex (runtime + plugin ecosystem — product suite)" — #L240 · class: packaging (plugin ecosystem)
- Agent Zero — https://github.com/agent0ai/agent-zero — 19.2k ⭐ — "Organic, prompt-defined personal agent framework: hierarchical sub-agents, persistent memory, browser and code tools, and self-modifying behavior…" — `memory · multi-agent · browser · sandbox · python` — "slightly complex (prompt-defined, Docker + web UI)" — #L241 · class: capability
- OpenHarness (HKUDS) — https://github.com/HKUDS/OpenHarness — 15.8k ⭐ — "Open agent harness with a built-in personal agent ("Ohmo") that runs across Feishu, Slack, Telegram, and Discord; core tool-use, skills, memory, multi-agent coordination with auto-compaction…" — `memory · multi-agent` — "complex (personal agent + multi-channel — product suite)" — #L242 · class: capability
- QM ★✱ — https://github.com/yc-software/qm — 15.2k ⭐ — "Y Combinator's multiplayer agent harness for work…: every person and room gets scoped memory, files, credentials, permissions, crons, web apps, and a durable sandbox… Pi, OpenCode, Codex, or Claude Code can drive the same core." — #L243 · class: capability
- OpenJarvis ★ — https://github.com/open-jarvis/OpenJarvis — 10k ⭐ — "Stanford Hazy Research's local-first personal AI harness: on-device model inference… and evaluations that count energy, latency, and dollars alongside accuracy; a cloud model can tune the local configuration once…" — `memory · local · python` — #L244 · class: telemetry
- AIlice — https://github.com/myshell-ai/AIlice — 1.4k ⭐ — "Fully autonomous general-purpose agent; one binary, Docker-ready, for when you want "set goal and walk away" without a framework." — `sandbox · python` — "slightly complex (autonomous, one binary)" — #L245 · class: capability
- Talon ★ — https://github.com/dylanneve1/talon — 83 ⭐ — "Multi-platform personal agent living in Telegram, Discord, Teams, and the terminal. The harness is a pluggable-backend loop (Claude, Kilo, OpenCode, Codex, OpenAI Agents) with full MCP tool access and persistent background agents…" — `mcp · memory · cli · typescript` — #L246 · class: capability

## Evaluation and benchmarking harnesses (19)

Blurb (L350): "_Agentic eval systems, reasoning benchmarks, and open agent benchmarks._" All entries class: validation unless noted.

- Agent Lightning ★ — https://github.com/microsoft/agent-lightning — 18.4k ⭐ — "Microsoft's training-oriented harness: optimization loops for agent behavior—when you need to improve policies over rollouts, not only score a fixed prompt." — `evals · training · python` — "complex (agent training, Microsoft stack — product suite)" — #L354 · also class: telemetry (measuring agent behaviour)
- SWE-bench ★ — https://github.com/SWE-bench/SWE-bench — 5.9k ⭐ — "LMs resolve real GitHub issues; Docker harness, instance IDs; standard for code-agent evals." — `evals · sandbox · python` — #L355
- AgentBench ★ — https://github.com/THUDM/AgentBench — 3.7k ⭐ — "ICLR'24 benchmark: agents across AlfWorld, DB, knowledge graphs, OS, webshop; Docker Compose, function-calling interface." — #L356
- inspect_ai ★ — https://github.com/UKGovernmentBEIS/inspect_ai — 2.8k ⭐ — "Inspect AI core: composable eval tasks, sandboxes, scorers, and multi-model runs…" — #L357
- WebArena ★ — https://github.com/web-arena-x/webarena — 1.6k ⭐ — "Realistic web env (e.g. e-commerce, CMS, dev tools); 812 tasks; measures end-to-end web agent success." — #L358
- WebVoyager ★ — https://github.com/MinorJerry/WebVoyager — 1.1k ⭐ — "End-to-end web agent with LMMs: screenshots + actions on real sites; benchmark on 15 sites, GPT-4V for automatic eval." — #L359
- agent-qa ★ — https://github.com/vostride/agent-qa — 887 ⭐ — "Self-improving QA harness for web and mobile apps: natural-language tests, memory-backed self-healing, dashboard/CLI, MCP and skills support, plus sandboxed hooks for production regression checks." — ⚠️ FSL-1.1-ALv2 — #L360
- ClawBench ★ — https://github.com/TIGER-AI-Lab/ClawBench — 801 ⭐ — "Open web-agent evaluation harness: runs selectable agents in isolated Docker containers across 153 live-site tasks…, and records video, screenshots, HTTP traffic, actions, and agent messages for replayable scoring." — #L361 · also class: telemetry
- swe-smith ★ — https://github.com/SWE-bench/SWE-smith — 775 ⭐ — "Data generation for SWE agents; 50k+ instances across 128 repos; used for SWE-agent-LM training." — #L362
- SWE-Gym ★ — https://github.com/SWE-Gym/SWE-Gym — 742 ⭐ — "Training and evaluation for SWE agents and verifiers (ICML 2025)." — #L363
- ARC-AGI-2 — https://github.com/arcprize/ARC-AGI-2 — 738 ⭐ — "ARC Prize task set: grid-based abstraction/reasoning; public and private splits for generalization." — "super simple (task set)" — #L364
- Terminal-Bench ★ — https://github.com/harbor-framework/terminal-bench — 738 ⭐ — "The terminal-task benchmark coding agents now cite next to SWE-bench: hard, containerized terminal tasks scored end to end." — #L365
- inspect_evals ★ — https://github.com/UKGovernmentBEIS/inspect_evals — 675 ⭐ — "UK AISI and partner organisations: GAIA and other evals in Inspect AI; level 1–3, sandboxed, tool-calling solvers." — #L366
- arc-agi-benchmarking ★ — https://github.com/arcprize/arc-agi-benchmarking — 362 ⭐ — "Runner for ARC-AGI: multi-provider…, rate limits, retries, and scoring." — #L367
- VitaBench ★ — https://github.com/meituan-longcat/vitabench — 177 ⭐ — "ICLR'26: 66 tools, real-world apps (delivery, travel, retail); 100 cross-scenario + 300 single-scenario tasks; adopted by Qwen/Seed." — #L368
- AgencyBench ★ — https://github.com/GAIR-NLP/AgencyBench — 100 ⭐ — "Long-horizon agent benchmark: 32 scenarios, 138 tasks, ~1M tokens and ~90 tool calls; Docker sandbox and rubric-based + LLM judges." — #L369
- letta-evals ★ — https://github.com/letta-ai/letta-evals — 82 ⭐ — "Eval harness for stateful Letta agents; configurable suites and grading (LLM or rule-based) so you can measure what you ship." — #L370
- SUPER ★ — https://github.com/allenai/super-benchmark — 58 ⭐ — "Agents that set up and run ML/NLP from GitHub repos; 45 expert problems, 152 masked tasks, 602 AutoGen tasks; Docker-based." — #L371
- TRAIL — https://github.com/patronus-ai/trail-benchmark — 24 ⭐ — "Trace reasoning and agentic issue localization; 148 long-context traces, 841 errors, 20+ error types; Hugging Face dataset." — #L372 · also class: telemetry

## Observability and eval-ops (4)

Blurb (L378): "_Tracing, monitoring, and production evaluation for live agent runs: capture every step, tool call, and token, then score and debug in the loop._" All class: telemetry.

- Langfuse — https://github.com/langfuse/langfuse — 34.9k ⭐ — "Open-source LLM engineering platform: full-trace observability, online and offline evals, prompt management, and cost metrics for agent runs in production—the monitoring layer most harnesses lack out of the box." — `evals · typescript` — "slightly complex (tracing + evals platform)" — #L382
- MLflow — https://github.com/mlflow/mlflow — 28.1k ⭐ — "Mature ML platform now covering GenAI: MLflow Tracing captures every agent step, tool call, and token, with built-in LLM evals and prompt versioning…" — `evals · python` — "complex (full ML + GenAI platform)" — #L383
- Opik — https://github.com/comet-ml/opik — 22.2k ⭐ — "Comet's open-source agent observability and evaluation platform: tracing, scoring, and experiment comparison with the whole core feature set free to self-host under Apache-2.0." — "slightly complex (tracing + evals platform)" — #L384
- Arize Phoenix — https://github.com/Arize-ai/phoenix — 11.5k ⭐ — "Arize's source-available, local-first tracing and eval layer: run it on your laptop or your own infra, and graduate to the managed Arize AX platform only when you need it." — ⚠️ Elastic-2.0 — #L385
