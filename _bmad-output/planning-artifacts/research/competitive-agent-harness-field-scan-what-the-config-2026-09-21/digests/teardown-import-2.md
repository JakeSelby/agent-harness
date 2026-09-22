# Teardown — dossier-second-ring-2026-09-21.md

- claim: agnix is a Rust Cargo workspace shipping a CLI, an LSP, an MCP server, a WASM build, editor plugins for VS Code/JetBrains/Neovim/Zed, a GitHub Action, a pre-commit hook, and npm and PyPI wrappers.
  source: agent-sh/agnix:crates/, editors/, action.yml, .pre-commit-hooks.yaml, npm/, pypi/
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: agnix's target list is 13 known tools at `schema.rs:98-112`, with a narrower legacy `TargetTool` enum and `target` deprecated in favour of `tools`.
  source: agent-sh/agnix:crates/agnix-core/src/config/schema.rs:98-112
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: agnix has no switchable preference variants; its only axes are severity threshold, per-rule enable/disable and path-scoped `[[overrides]]` in `.agnix.toml`.
  source: agent-sh/agnix:.agnix.toml
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: agnix enforces `MAX_RECOMMENDED_LINES: usize = 200` for CLAUDE.md (rule CC-MEM-014).
  source: agent-sh/agnix:crates/agnix-core/src/rules/claude_md.rs:285
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: agnix enforces a second cap of ~1500 tokens (~6000 chars, estimated as char_count/4) for CLAUDE.md as rule CC-MEM-009.
  source: agent-sh/agnix:crates/agnix-core/src/schemas/claude_md.rs:111-116
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
  contradicts: caliber's prompts require CLAUDE.md under
- claim: agnix's telemetry is opt-in by default, storing an `installation_id` and a `consent_timestamp`, with a stub module for builds compiled without it.
  source: agent-sh/agnix:crates/agnix-cli/src/telemetry/config.rs:18
  publisher: agent-sh/agnix
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: dossier-second-ring-2026-09-21.md
- claim: agnix is dual-licensed Apache-2.0 and MIT and runs 15 GitHub workflows including `spec-drift.yml`, `fuzz.yml`, `tool-release-watch.yml` and `mcp-release-watch.yml`.
  source: https://api.github.com/repos/agent-sh/agnix
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: licensing
  via: dossier-second-ring-2026-09-21.md
- claim: `rely-ai-org/caliber` now redirects to `caliber-ai-org/ai-setup`, and `spartan-stratos/spartan-ai-toolkit` to `c0x12c/ai-toolkit`.
  source: https://api.github.com/repos/rely-ai-org/caliber
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-second-ring-2026-09-21.md
- claim: caliber uses an LLM to generate agent config, with provider modules for Anthropic, Vertex, OpenAI-compatible, Claude CLI, Cursor ACP, OpenCode, MiniMax and AtlasCloud.
  source: caliber-ai-org/ai-setup:src/ai/, src/llm/
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: caliber targets five providers (`claude | cursor | codex | opencode | github-copilot`), with Codex and OpenCode sharing an `agentsStyleAdapter`.
  source: caliber-ai-org/ai-setup:src/sync/types.ts:12, src/sync/adapters.ts:353-354
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: caliber has zero preference axes: a full grep of `src/` for profile|preset|variant|persona|stance|posture|strictness|autonomy returns only `PERSONAL_*` constants and a `--personal` learning-scope flag.
  source: caliber-ai-org/ai-setup:src/cli.ts:379
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: caliber derives generated config from a detected codebase fingerprint rather than from stated working preferences.
  source: caliber-ai-org/ai-setup:src/fingerprint/, src/ai/prompts.ts
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: caliber's prompts require CLAUDE.md/AGENTS.md to be under 400 lines (aim 200-350), skill content max 150 lines, and total tokens across all config files under 2000 for full points.
  source: caliber-ai-org/ai-setup:src/ai/prompts.ts:109,131,138
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: caliber's scorer awards full points at up to 5000 tokens (`TOKEN_BUDGET_THRESHOLDS`), disagreeing with its own prompt's under-2000-token requirement.
  source: caliber-ai-org/ai-setup:src/scoring/constants.ts:76
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
  contradicts: caliber's prompts require CLAUDE.md under
- claim: caliber ships PostHog telemetry with the project key hardcoded in source at `src/telemetry/index.ts:12`, opt-out rather than opt-in.
  source: caliber-ai-org/ai-setup:src/telemetry/index.ts:12
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: dossier-second-ring-2026-09-21.md
  contradicts: agnix's telemetry is opt-in by
- claim: caliber installs hooks into user repos and ships its own freshness/sync hooks plus a `.cursor/hooks.json`.
  source: caliber-ai-org/ai-setup:src/lib/hooks.ts, .claude/hooks/caliber-check-sync.sh
  publisher: caliber-ai-org/ai-setup
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt is a self-hosted Next.js web app with Prisma/Postgres, Docker, a Helm chart and a snap package, plus a CLI and a GitHub Action.
  source: GeiserX/LynxPrompt:charts/, cli/, action/action.yml
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt declares a single source of truth for ~38 AI IDE platform ids in `src/lib/platforms.ts`, the widest target list in the second ring.
  source: GeiserX/LynxPrompt:src/lib/platforms.ts
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt is the only project in the second ring with named switchable preference variants composed into generated config.
  source: dossier-second-ring-2026-09-21.md (synthesis)
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
  contradicts: across the ten primary-ring projects
- claim: LynxPrompt exposes autonomy as a three-value boundary preset — conservative, standard, permissive — defined as always/askFirst/never lists and composed into the generated file.
  source: GeiserX/LynxPrompt:cli/src/index.ts:46, cli/src/utils/generator.ts:298-345,1156-1207
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt exposes plan ceremony as a six-value named axis `PLAN_MODE_FREQUENCY` (always, complex_tasks, multi_file, new_features, on_request, never) defaulting to complex_tasks.
  source: GeiserX/LynxPrompt:packages/shared/src/wizard/ai-behavior.ts:22-28
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt exposes verbosity as a three-value axis (concise, balanced, detailed) defaulting to balanced and rendered into generated prose.
  source: GeiserX/LynxPrompt:cli/src/commands/wizard.ts:3039-3051, src/lib/file-generator.ts:635
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt does not model test strictness as a posture (it is a multi-select of levels), and models neither delegation depth nor cost posture at all.
  source: GeiserX/LynxPrompt:packages/shared/src/wizard/testing.ts:6
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt imposes no line, byte or token cap on generated files anywhere in its generators.
  source: GeiserX/LynxPrompt:src/lib/file-generator.ts, cli/src/utils/generator.ts
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: LynxPrompt treats federation between self-hosted instances as a first-class feature.
  source: GeiserX/LynxPrompt:src/lib/federation.ts
  publisher: GeiserX/LynxPrompt
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: agents-md-cookbook ships two npm packages — a linter and a migrate tool with converters from aider, claude, cline, copilot, cursor and windsurf — plus a GitHub Action and 16 stack templates.
  source: Taiizor/agents-md-cookbook:packages/linter/, packages/migrate/src/converters/
  publisher: Taiizor/agents-md-cookbook
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: agents-md-cookbook's linter delegates to agnix via `packages/linter/src/engine-agnix.ts`, one linter composing another.
  source: Taiizor/agents-md-cookbook:packages/linter/src/engine-agnix.ts
  publisher: Taiizor/agents-md-cookbook
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: agents-md-cookbook is the only project citing a mechanism for its byte cap: `CODEX_BYTE_CAP = 32768` because "Codex truncates AGENTS.md at 32 KiB by default", severity error, configurable via `{ maxBytes }`.
  source: Taiizor/agents-md-cookbook:packages/linter/src/rules/byte-cap.ts:3-5
  publisher: Taiizor/agents-md-cookbook
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: agents-md-cookbook warns with `SOFT_LINE_LIMIT = 150` and `HEAVY_LINE_LIMIT = 300`, messaging "Beyond ~300 lines correctness gains reverse".
  source: Taiizor/agents-md-cookbook:packages/linter/src/rules/line-budget.ts:3-6
  publisher: Taiizor/agents-md-cookbook
  pub_date: 2026-08
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
  contradicts: agnix enforces MAX_RECOMMENDED_LINES usize = 200
- claim: agents-md-cookbook records in `COMPATIBILITY.md` (last verified 2026-06-14) that Claude Code is not native to AGENTS.md and requires the adapter `ln -s AGENTS.md CLAUDE.md`.
  source: Taiizor/agents-md-cookbook:COMPATIBILITY.md
  publisher: Taiizor/agents-md-cookbook
  pub_date: 2026-06
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: cc-audit is a 240-line dependency-free Python file plus a composite GitHub Action, scanning `./CLAUDE.md` and `./AGENTS.md` by filename with twelve hardcoded keyword-signal rules.
  source: sisyphusse1-ops/cc-audit:cc_audit.py:34-61
  publisher: sisyphusse1-ops/cc-audit
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: cc-audit hardcodes `COMPLIANCE_CLIFF = 200` lines ("past this, agent compliance drops sharply") and `IDEAL_MAX = 150` with no citation for the 200 figure anywhere in the repo.
  source: sisyphusse1-ops/cc-audit:cc_audit.py:72-73
  publisher: sisyphusse1-ops/cc-audit
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
  contradicts: agents-md-cookbook is the only project
- claim: cc-audit has 0 stars, was created and last pushed on 2026-05-10, and has no test directory.
  source: https://api.github.com/repos/sisyphusse1-ops/cc-audit
  publisher: GitHub
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-second-ring-2026-09-21.md
- claim: claude-code-pro-pack's product is a 39-line CLAUDE.md of 12 rules plus an AGENTS.md duplicate whose rules 5-12 are shortened, so the two copies have already drifted by 8 lines.
  source: sisyphusse1-ops/claude-code-pro-pack:CLAUDE.md, AGENTS.md
  publisher: sisyphusse1-ops/claude-code-pro-pack
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: claude-code-pro-pack states its size cap as prose only — "Keep it short — past ~200 lines compliance drops sharply" — with no enforcing mechanism in the repo.
  source: sisyphusse1-ops/claude-code-pro-pack:CLAUDE.md:3
  publisher: sisyphusse1-ops/claude-code-pro-pack
  pub_date: 2026-05
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: schliff is a zero-runtime-dependency Python package plus Claude skill, distributed via a `schliff` console script, an `install.sh` and a GitHub Action with a `minimum-score` input.
  source: Zandereins/schliff:pyproject.toml:31, action.yml
  publisher: Zandereins/schliff
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: schliff's weight profiles are keyed by file format (skill.md, CLAUDE.md, .cursorrules, AGENTS.md, system prompt), not by user preference.
  source: Zandereins/schliff:skills/schliff/scripts/scoring/registry.py:1,48
  publisher: Zandereins/schliff
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: schliff has two named autonomy modes for its own auto-fix loop — autonomous (documented default) and advisor (opt-in via flag, per-step human confirmation) — but they are never composed into any generated config.
  source: Zandereins/schliff:docs/adr/0004-both-modes-ship-judge-advisory.md
  publisher: Zandereins/schliff
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: schliff deliberately rejects a hard size cap, scoring conciseness as a +5 bonus under 300 lines and commenting "The denominator is deliberately NOT capped. Capping it at 1500 words removed a real defect".
  source: Zandereins/schliff:skills/schliff/scripts/scoring/efficiency.py:167-168,201-203
  publisher: Zandereins/schliff
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
  contradicts: agnix enforces MAX_RECOMMENDED_LINES usize = 200
- claim: schliff keeps its auto-loop gate deterministic — a 15-point regression guard — with the LLM judge explicitly advisory.
  source: Zandereins/schliff:docs/adr/0004-both-modes-ship-judge-advisory.md
  publisher: Zandereins/schliff
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: c0x12c/ai-toolkit has no LICENSE file in its tree (`license: null` from the GitHub API), leaving it unresolved under a permissive-commercial stance.
  source: https://api.github.com/repos/c0x12c/ai-toolkit
  publisher: GitHub
  pub_date: 2026-06
  accessed: 2026-09-21
  confidence: high
  class: licensing
  via: dossier-second-ring-2026-09-21.md
- claim: c0x12c/ai-toolkit assembles CLAUDE.md from numbered markdown fragments (00-header … 90-footer) and targets five tools with an `--format=agents-md` cross-tool export.
  source: c0x12c/ai-toolkit:toolkit/claude-md/, toolkit/bin/cli.js:114,119,173-180
  publisher: c0x12c/ai-toolkit
  pub_date: 2026-06
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: c0x12c/ai-toolkit's "profiles" are tech-stack profiles (go-standard, java-spring, python-django …) whose review dimension is seven independently `enabled: true` stages, a toggle set rather than named alternatives.
  source: c0x12c/ai-toolkit:toolkit/profiles/go-standard.yaml
  publisher: c0x12c/ai-toolkit
  pub_date: 2026-06
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: c0x12c/ai-toolkit's token budget is reporting-only: `gen-codex-skills.js` prints a per-skill token table computed as length/4 and enforces nothing.
  source: c0x12c/ai-toolkit:toolkit/scripts/gen-codex-skills.js:184-200
  publisher: c0x12c/ai-toolkit
  pub_date: 2026-06
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: controlkeel is licensed NOASSERTION — a license file present but not SPDX-recognised — so it needs a read of the license text before use.
  source: https://api.github.com/repos/aryaminus/controlkeel
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: licensing
  via: dossier-second-ring-2026-09-21.md
- claim: controlkeel is a Phoenix/OTP server with an MCP interface, keeping a capability catalogue per agent id with cost_tier, security_tier, swe_bench_score and context_window_k.
  source: aryaminus/controlkeel:lib/controlkeel/agent/router.ex:35
  publisher: aryaminus/controlkeel
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: controlkeel defines four named autonomy modes (advise, supervised_execute, guarded_autonomy, long_running_autonomy) but infers the mode from session state, defaulting to guarded_autonomy, rather than letting a user pick and write it into config.
  source: aryaminus/controlkeel:lib/controlkeel/agent/autonomy_loop.ex:10,306-327
  publisher: aryaminus/controlkeel
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: controlkeel's selectable policy packs (baseline, cost, security, ai_tools, gdpr plus 15 industry packs) are domain/compliance packs, not alternative profiles of one behavioural axis; its cost pack warns at ratio 0.8 and blocks at 1.0.
  source: aryaminus/controlkeel:priv/policy_packs/cost.json, lib/controlkeel/policy/pack_loader.ex
  publisher: aryaminus/controlkeel
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: controlkeel caps spend and bounds loops but imposes no size cap on always-loaded instruction context.
  source: aryaminus/controlkeel:lib/controlkeel/runtime/bounded_loop*.ex
  publisher: aryaminus/controlkeel
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: claude-snapshot is a Claude-Code-only byte-mover — export to a sha256-checksummed manifest, diff, apply — capturing settings, CLAUDE.md, hooks, plugins, marketplaces and MCP servers with no opinion about content.
  source: adhenawer/claude-snapshot:src/snapshot.mjs:14-18,109-183,224-247
  publisher: adhenawer/claude-snapshot
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: claude-snapshot makes snapshots portable by rewriting the user home to `$HOME` and stripping machine-specific absolute paths such as nvm Node binary pins.
  source: adhenawer/claude-snapshot:src/snapshot.mjs:46,64
  publisher: adhenawer/claude-snapshot
  pub_date: 2026-04
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: tdd-guard is the most-starred of the second ring at 2,346 stars but its README declares it superseded by Probity, which covers Claude Code, Codex and GitHub Copilot CLI and needs no test reporters.
  source: nizos/tdd-guard:README.md:10-14
  publisher: nizos/tdd-guard
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-second-ring-2026-09-21.md
- claim: tdd-guard's multi-target dimension is eleven test-framework reporters, each separately published, not agent runtimes.
  source: nizos/tdd-guard:reporters/
  publisher: nizos/tdd-guard
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-second-ring-2026-09-21.md
- claim: tdd-guard offers one default rule set plus a global on/off and a never-overwritten user override file at `.claude/tdd-guard/data/instructions.md`; there are no named strict/lenient alternatives.
  source: nizos/tdd-guard:docs/custom-instructions.md, docs/quick-commands.md
  publisher: nizos/tdd-guard
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-second-ring-2026-09-21.md
- claim: tdd-guard removed its configurable data directory by ADR for a better security posture and least privilege, fixing `DEFAULT_DATA_DIR = .claude/tdd-guard/data`.
  source: nizos/tdd-guard:docs/adr/003-remove-configurable-data-directory.md
  publisher: nizos/tdd-guard
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-second-ring-2026-09-21.md
- claim: six of the ten second-ring projects enforce or advise a size cap and none of the numbers agree — 200 lines/1500 tokens, 200 with 150 ideal, ~200 prose, 400 lines and 2000-5000 tokens, 32768 bytes plus 150/300 lines, and 300 lines as a bonus.
  source: dossier-second-ring-2026-09-21.md (cross-cutting facts)
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: validation
  via: dossier-second-ring-2026-09-21.md
- claim: only two of the ten second-ring projects collect telemetry at all — agnix opt-in, caliber opt-out via PostHog.
  source: dossier-second-ring-2026-09-21.md (cross-cutting facts)
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: telemetry
  via: dossier-second-ring-2026-09-21.md
- claim: six of the ten second-ring projects ship a GitHub Action, and three ship a pre-commit hook or husky gate, making CI the dominant distribution surface for instruction linting.
  source: dossier-second-ring-2026-09-21.md
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: packaging
  via: dossier-second-ring-2026-09-21.md

## Leads

- GeiserX/LynxPrompt's `BOUNDARIES` / `PLAN_MODE_FREQUENCY` / verbosity triple is the closest external precedent for agent-harness stance variants; read `cli/src/utils/generator.ts:298-345` before designing the variant schema.
- Codex's `project_doc_max_bytes` (32 KiB) is the only size cap in either ring traceable to a runtime mechanism — verify against the live Codex spec.
- Probity (nizos/probity) — the successor to tdd-guard, multi-runtime, not inspected.
- agnix as an embeddable lint engine: agents-md-cookbook already consumes it, so agent-harness could too rather than writing rules from scratch.
- agnix's opt-in telemetry consent shape (`installation_id` + `consent_timestamp`) as a model if agent-harness ever reports beyond the local machine.
- controlkeel's policy packs as a shape for domain overlays distinct from behavioural stances.

## Not found

- Any second-ring project besides LynxPrompt that composes a user-selected behavioural posture into generated config.
- Any project modelling delegation depth or cost posture as a user-selectable variant.
- Any empirical source for the recurring "~200 lines" compliance cliff; cc-audit states it with no citation.
- Whether caliber's prompt cap or its scorer cap wins in practice — the import records the disagreement without resolving it.
- License text for controlkeel (NOASSERTION) and any license at all for c0x12c/ai-toolkit.
