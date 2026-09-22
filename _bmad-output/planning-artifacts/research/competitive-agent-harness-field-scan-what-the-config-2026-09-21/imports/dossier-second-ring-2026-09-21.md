# Second-ring AI-agent-config tools — inspection notes (2026-09-21)

All data from `gh api` on 2026-09-21. No repo 404'd, but one redirect:
`rely-ai-org/caliber` → **`caliber-ai-org/ai-setup`** (package name `caliber`).
`spartan-stratos/spartan-ai-toolkit` → **`c0x12c/ai-toolkit`** (npm `@c0x12c/ai-toolkit`).

---

## 1. agent-sh/agnix
- 421 stars · created 2026-01-30 · pushed 2026-09-20 · Apache-2.0 (+ LICENSE-MIT, dual) · Rust
- **Structure:** Cargo workspace. Crates: `agnix-core` (rules engine, ~121 files), `agnix-cli`,
  `agnix-lsp`, `agnix-rules`, `agnix-mcp`, `agnix-wasm`. Editor plugins under `editors/{vscode,
  jetbrains,neovim,zed}`. Also ships a GitHub Action (`action.yml`), a pre-commit hook
  (`.pre-commit-hooks.yaml`, `entry: agnix`), npm (`npm/`) and PyPI (`pypi/`) wrappers.
  28,042 blobs in tree, but 26,740 are `website/versioned_docs` Docusaurus snapshots and 319 are
  `tests/fixtures/`.
- **Entry point:** `crates/agnix-cli/src/main.rs`; LSP `crates/agnix-lsp/`; MCP `crates/agnix-mcp/`.
- **MULTI-TARGET: yes.** Target list is `crates/agnix-core/src/config/schema.rs:98-112`
  (`known_tools`): `claude-code, cursor, codex, kiro, copilot, github-copilot, cline, opencode,
  gemini-cli, amp, roo-code, windsurf, generic`. A narrower legacy enum `TargetTool` at
  `crates/agnix-config.rs:924` (`config.rs:924`) = `Generic | ClaudeCode | Cursor | Codex | Kiro`;
  `target` is deprecated in favour of `tools` (warning at schema.rs:133).
  Per-tool rule modules: `crates/agnix-core/src/rules/{claude_md,codex,cursor,copilot,cline,
  opencode,amp,roo,windsurf,gemini_*,kiro...}.rs`.
- **SWITCHABLE PREFERENCE VARIANTS: no.** The only axes are severity threshold and rule
  enable/disable. `.agnix.toml` (repo root): `severity = "Warning"`, `target = "Generic"`,
  `[rules] skills = true / hooks = true / ...`, `disabled_rules = ["XP-001", ...]`, plus
  `[[overrides]] paths = [...] disabled_rules = [...]`. Grep for
  preset|profile|strictness|posture|persona|stance over `config.rs`/`schema.rs` returns nothing.
- **SIZE CAP: yes, two.**
  - `crates/agnix-core/src/rules/claude_md.rs:285` — `const MAX_RECOMMENDED_LINES: usize = 200;`
    (rule CC-MEM-014, message "CLAUDE.md has {} non-empty lines, exceeding the recommended {} line limit").
  - `crates/agnix-core/src/schemas/claude_md.rs:111-116` — "Check if content exceeds token limit
    (~1500 tokens = ~6000 chars)"; `let limit = 1500;` `estimated_tokens = char_count / 4`
    (rule CC-MEM-009).
- **Hooks / telemetry / tests:** pre-commit hook yes; validates *other people's* hooks
  (`rules/hooks/`). Telemetry present and **opt-in**: `crates/agnix-cli/src/telemetry/config.rs:18`
  "Default: false (opt-in only)", with `installation_id` + `consent_timestamp`; a
  `telemetry_stub.rs` exists for builds without it. Tests: unit tests in-module, `tests/fixtures/`
  (319 files), fuzz targets (`fuzz_frontmatter/json/markdown`), benches (`iai_validation.rs`),
  proptest regressions, 15 GH workflows incl. `spec-drift.yml`, `fuzz.yml`, `security.yml`,
  `tool-release-watch.yml`, `mcp-release-watch.yml`. i18n: en/es/zh-CN locale files.

---

## 2. caliber-ai-org/ai-setup (was rely-ai-org/caliber)
- 1,278 stars · created 2026-03-10 · pushed 2026-09-19 · MIT · TypeScript
- **Structure:** Node CLI published as `caliber`. `package.json` `"bin": {"caliber": "./dist/bin.js"}`;
  entry `src/bin.ts` → `src/cli.ts`. Also a GitHub Action (`action.yml`,
  `.github/workflows/caliber-score.yml`) and a Claude plugin (`.claude-plugin/marketplace.json`).
  Uses an LLM to generate config: `src/ai/{generate,refine,refresh,score-refine,prompts}.ts`,
  providers in `src/llm/{anthropic,vertex,openai-compat,claude-cli,cursor-acp,opencode,minimax,
  atlascloud}.ts`.
- **MULTI-TARGET: yes.** `src/sync/types.ts:12` —
  `export type ProviderId = 'claude' | 'cursor' | 'codex' | 'opencode' | 'github-copilot';`
  and `PROVIDER_IDS` at line 14. Adapters: `src/sync/adapters.ts` (`ADAPTERS: Record<ProviderId,
  ProviderAdapter>` at line 411); writers: `src/writers/{claude,codex,cursor,github-copilot,
  opencode}/index.ts`. Codex+OpenCode share an `agentsStyleAdapter` (adapters.ts:353-354).
- **SWITCHABLE PREFERENCE VARIANTS: no.** A full grep of `src/` for
  profile|preset|variant|persona|stance|posture|strictness|autonomy returns only `PERSONAL_*`
  constants and `--personal` (a learning *scope* flag, `src/cli.ts:379`: "Save as a personal
  learning instead of project-level"). Generation is one fixed prompt set in `src/ai/prompts.ts`
  parameterized by a detected codebase fingerprint (`src/fingerprint/`), not by user preference
  profiles. `src/commands/config.ts` covers LLM provider/model config only.
- **SIZE CAP: yes, as prompt constraints and as score thresholds.**
  - `src/ai/prompts.ts:131` — "CLAUDE.md / AGENTS.md: MUST be under 400 lines for maximum score.
    Aim for 200-350 lines."; :138 "Each skill content: max 150 lines."; :69 "Keep skill content
    under 200 lines."; :347 and :372 repeat "MUST stay under 400 lines" for the refine/diff paths.
  - `src/ai/prompts.ts:109` — "Concise config (6 pts) — total tokens across ALL config files must
    be under 2000 for full points (3500=5pts, 5000=4pts, 8000+=low)".
  - `src/scoring/constants.ts:76` — `TOKEN_BUDGET_THRESHOLDS = [{maxTokens:5000,points:6},
    {8000,5},{12000,4},{16000,2},{24000,1}]`.
  - Note the two disagree (prompt says <2000 tokens, scorer's top band is 5000).
- **Hooks / telemetry / tests:** ships its own hooks (`.claude/hooks/caliber-check-sync.sh`,
  `caliber-freshness-notify.sh`, `caliber-session-freshness.sh`) and installs hooks into user repos
  (`src/lib/hooks.ts`, `src/lib/learning-hooks.ts`, `src/commands/hooks.ts`), plus `.cursor/hooks.json`.
  Telemetry: PostHog, key hardcoded in `src/telemetry/index.ts:12`
  (`POSTHOG_KEY = 'phc_XXrV0pSX4s2QVxVoOaeuyXDvtlRwPAjovt1ttMGVMPp'`), disable via
  `isTelemetryDisabled()`. Tests: vitest `__tests__` dirs throughout src; husky pre-commit; CI
  workflows ci/publish/pr-size.

---

## 3. GeiserX/LynxPrompt
- 48 stars · created 2025-12-20 · pushed 2026-09-21 · Apache-2.0 · TypeScript
- **Structure:** Next.js self-hosted web app (Prisma + Postgres, Docker, Helm chart in `charts/`,
  snap package) **plus** a CLI (`cli/`, bins `lynxprompt`/`lynxp` → `cli/dist/index.js`) **plus** a
  GitHub Action (`action/action.yml`, "LynxPrompt Sync"). Shared option definitions live in
  `packages/shared/src/wizard/`.
- **Entry points:** web `src/app/wizard/page.tsx`; CLI `cli/src/index.ts` → `cli/src/commands/wizard.ts`;
  generation `src/lib/file-generator.ts` (web) and `cli/src/utils/generator.ts` (CLI).
- **MULTI-TARGET: yes, the widest of the ten.** `src/lib/platforms.ts` — header comment: "This file
  is the SINGLE SOURCE OF TRUTH for all supported AI IDE platforms." 743 lines, ~38 platform ids:
  universal, cursor, claude, copilot, windsurf, antigravity, zed, void, trae, firebase, cline,
  roocode, continue, cody, tabnine, supermaven, codegpt, amazonq, augment, kilocode, junie, kiro,
  aider, goose, warp, gemini-cli, opencode, openhands, crush, firebender, plus command variants
  (cursor-command, claude-command, windsurf-workflow, copilot-prompt, continue-prompt,
  opencode-command). A narrower legacy type at `src/types/index.ts:23` `AIPlatformId = cursor |
  claude_code | github_copilot | windsurf | continue | cody`.
- **SWITCHABLE PREFERENCE VARIANTS: YES — the only clear hit in the ten.**
  - Autonomy: `cli/src/index.ts:46` — `.option("--boundaries <level>", "Boundary preset
    (conservative, standard, permissive)")`. Typed at `cli/src/utils/generator.ts:7`:
    `boundaries: "conservative" | "standard" | "permissive";`. Defined at
    `cli/src/utils/generator.ts:298-345` as `const BOUNDARIES: Record<string, {always: string[];
    askFirst: string[]; never: string[]}>` — e.g. conservative puts "Modify any source file" and
    "Run test commands" under askFirst; standard puts "Modify files in src/ or lib/" and "Run build,
    test, and lint commands" under always; permissive adds "Add or update dependencies" to always.
    Composed into output at `cli/src/utils/generator.ts:1156-1207`
    (`const presetBoundaries = BOUNDARIES[options.boundaries] || BOUNDARIES.standard;`) and again at
    :1707. Web path renders a Boundaries section at `src/lib/file-generator.ts:785-825` and
    :1525ff for AGENTS.md.
  - Plan/review ceremony: `packages/shared/src/wizard/ai-behavior.ts:22-28`
    `export const PLAN_MODE_FREQUENCY: WizardOption[] = [always | complex_tasks | multi_file |
    new_features | on_request | never]`, default `complex_tasks`; composed at
    `cli/src/utils/generator.ts:1024-1033` (`planModeDescriptions[options.planModeFrequency]`).
  - Verbosity: `cli/src/commands/wizard.ts:3039-3051` select of `concise | balanced | detailed`,
    default balanced; surfaces in generated text e.g. `src/lib/file-generator.ts:635`
    "- Provide balanced explanations, not too verbose".
  - Also `DeveloperPersona` at `src/types/index.ts:8` (backend|frontend|fullstack|devops|dba|
    infrastructure|sre|mobile|data|ml) — a persona axis, though used for tailoring templates.
  - Test strictness is a *multi-select*, not a variant: `packages/shared/src/wizard/testing.ts:6`
    `TEST_LEVELS = [smoke, unit, integration, e2e]`.
- **SIZE CAP: none found.** No line/byte/token budget on generated files anywhere in
  `file-generator.ts` or the CLI generator.
- **Hooks / telemetry / tests:** no agent hooks. Tests: `tests/{api,components,lib,workflows}`,
  vitest config, codecov.yml, 10 GH workflows (ci, cli-tests, deploy-dev/prod, docker-publish,
  publish-cli, release-chart). Federation between self-hosted instances is a first-class feature
  (`src/lib/federation.ts`, `prisma/migrations-app/.../add_federated_instance`).

---

## 4. Taiizor/agents-md-cookbook
- 19 stars · created 2026-06-14 · pushed 2026-08-08 · MIT · TypeScript (Bun)
- **Structure:** monorepo of two npm packages plus markdown. `packages/linter` (entry
  `packages/linter/src/cli.ts`, `"bin"` in its package.json) and `packages/migrate` (entry
  `packages/migrate/src/cli.ts`). Also a GitHub Action at repo-root `action.yml`. 16 templates
  under `templates/<stack>/AGENTS.md`. Docs: `docs/{anatomy,best-practices,common-mistakes,
  nesting-monorepos}.md`, plus `COMPATIBILITY.md`.
- **MULTI-TARGET: yes, in two senses.**
  - Migration sources: `packages/migrate/src/converters/{aider,claude,cline,copilot,cursor,
    windsurf}.ts`, orchestrated by `packages/migrate/src/orchestrator.ts`.
  - Consumption matrix: `COMPATIBILITY.md` ("Last verified: 2026-06-14"), a table of Cursor /
    Claude Code / Codex / Copilot (coding agent and VS Code chat) / etc. with NATIVE / CONFIG /
    ADAPTER / NO codes. It records "Claude Code | NO (not native) | ADAPTER — symlink
    `ln -s AGENTS.md CLAUDE.md`".
  - It also *delegates* to agnix: `packages/linter/src/engine-agnix.ts` (+ test).
- **SWITCHABLE PREFERENCE VARIANTS: no.** 20 rule modules under `packages/linter/src/rules/`, each
  with a fixed id/severity and per-rule numeric config overrides only. Templates are stack
  variants (django, go, rails, rust…), not preference variants.
- **SIZE CAP: yes, two, with sources.**
  - `packages/linter/src/rules/byte-cap.ts:3-5` — "Codex truncates AGENTS.md at 32 KiB by default."
    `export const CODEX_BYTE_CAP = 32768;` rule XP-007, severity **error**, configurable via
    `{ maxBytes }`.
  - `packages/linter/src/rules/line-budget.ts:3-6` — "Sweet spot is ~100-150 lines"
    `export const SOFT_LINE_LIMIT = 150;` / "Gains reverse hard beyond ~300 lines"
    `export const HEAVY_LINE_LIMIT = 300;` rule AMC-LENGTH, severity warn, message: "Beyond ~300
    lines correctness gains reverse".
- **Hooks / telemetry / tests:** no hooks, no telemetry. Heavy tests: ~35 vitest/bun test files
  incl. `dogfood.test.ts`, `readme.test.ts`, `idempotency.test.ts`, `action-yml.test.ts`.
  CI: `ci.yml`, `codeql.yml`, dependabot lockfile workflow, markdownlint-cli2, lychee link check.

---

## 5a. sisyphusse1-ops/cc-audit
- **0 stars** · created 2026-05-10 · pushed 2026-05-10 (same day; dormant) · MIT · Python
- **Structure:** 6 files total. One dependency-free Python file `cc_audit.py` (240 lines) +
  `action.yml` (composite GitHub Action) + `.github/workflows/audit.yml` + `data/scan-500.json`.
- **Entry point:** `cc_audit.py` (`python cc_audit.py [path] [--json]`).
- **MULTI-TARGET: nominally.** It scans `./CLAUDE.md` and `./AGENTS.md` by filename only; there is
  no target list file and no per-tool rule differences.
- **SWITCHABLE PREFERENCE VARIANTS: no.** Twelve hardcoded rules as keyword-signal tuples,
  `cc_audit.py:34-61` `RULE_SIGNALS: list[tuple[str, list[str]]]`. Only knobs are action inputs
  `fail-on-warning` (default false) and `json-output`.
- **SIZE CAP: yes.** `cc_audit.py:72-73`:
  `COMPLIANCE_CLIFF = 200  # lines — past this, agent compliance drops sharply` and
  `IDEAL_MAX = 150`. Enforced at :137 and :142. No citation for the 200 figure anywhere in the repo.
- **Hooks / telemetry / tests:** none of the three. No test directory at all.
- Also greps for leaked secrets: `ANTI_PATTERNS` at :63-69 (paypal.me, `ghp_`, `sk-`, `AKIA`,
  literal password).
- Action outputs: score (0-100 percent), rules-hit (0-12), leaked-secrets, status pass|warn|fail.

## 5b. sisyphusse1-ops/claude-code-pro-pack
- 35 stars · created 2026-05-10 · pushed 2026-05-10 · MIT · "HTML" (an `index.html` landing page)
- **Structure: markdown only.** 16 files. `CLAUDE.md` (39 lines) and `AGENTS.md` are the product;
  `templates/`, `examples/skill-*.md`, `docs/why-12-rules.md`, `docs/adoption-guide.md`,
  `index.html`, `action.yml`.
- **MULTI-TARGET: yes, by duplication.** `CLAUDE.md:3` — "Drop this file in your project root.
  Claude Code / Codex / Cursor / Hermes all read it." `AGENTS.md:1` — "# AGENTS.md — 12 Rules for
  Codex / OpenCode / Cursor"; :3 "Same 12 rules as `CLAUDE.md`, filename change for Codex-style
  tooling that looks for `AGENTS.md`." The two files are NOT identical — the AGENTS.md wordings of
  rules 5-12 are shortened (diff confirms 8 lines differ), so they can drift.
- **SWITCHABLE PREFERENCE VARIANTS: no.** One fixed 12-rule list, a `## Project specifics` HTML
  comment block for user additions, and a `## Verification checklist`.
- **SIZE CAP: yes, prose only.** `CLAUDE.md:3` — "Keep it short — past ~200 lines compliance drops
  sharply." No mechanism; the linter is the sibling repo cc-audit.
- **Hooks / telemetry / tests:** none.
- Rule 6 is the nearest thing to a cost posture and it is a single fixed statement: "**Hard token
  budget.** Every loop gets a ceiling."

---

## 6. Zandereins/schliff
- 17 stars · created 2026-03-19 · pushed 2026-09-21 · MIT · Python 3.10+, zero runtime deps
- **Structure:** Python package + Claude skill. `pyproject.toml:31` `[project.scripts] schliff =
  "skills.schliff.scripts.cli:main"`. Also `action.yml` ("AGENTS.md Lint (Schliff)"), `install.sh`,
  `web/`, `benchmarks/`, `playground/`, `demo/`, ADRs in `docs/adr/`, specs in `docs/specs/`.
- **MULTI-TARGET: yes, by *file format*, not by runtime.** `skills/schliff/scripts/scoring/formats.ts`
  → `formats.py:13-25`: `FORMAT_SKILL_MD="skill.md"`, `FORMAT_CLAUDE_MD`, `FORMAT_CURSORRULES`,
  `FORMAT_AGENTS_MD`, `FORMAT_SYSTEM_PROMPT`, `FORMAT_UNKNOWN`, with `_BASENAME_MAP`.
  `action.yml` description: "works with any agent tool (Cursor, Codex, Copilot, Claude Code)".
- **SWITCHABLE PREFERENCE VARIANTS: partly, on two different axes.**
  - Scoring weights are named profiles but keyed by *format*, not preference:
    `skills/schliff/scripts/scoring/registry.py:1` — """Scorer Registry — single source of truth for
    scorer lists and weight profiles.""" and :48 `WEIGHT_PROFILES: dict[str, dict[str, float]]`,
    with `_INSTRUCTION_FILE_WEIGHTS = {structure 0.15, triggers 0.20, quality 0.20, edges 0.15,
    efficiency 0.10, composability 0.10, clarity 0.05, security 0.05}` and `SCORER_REGISTRY`
    at :19 adding `operational_coverage` for agents.md only.
  - An **autonomy axis exists for the tool's own auto-fix loop**, as two named modes:
    `docs/adr/0004-both-modes-ship-judge-advisory.md` — "**Autonomous mode:** the loop runs, applies
    patches, re-scores, and only escalates to human at end-verify with N=10 sampling-gate.
    **Advisor mode:** every patch requires per-step human confirmation before being applied." and
    "Autonomous mode is the documented default in the README and CLI help. Advisor is opt-in via
    flag." This governs schliff's behaviour, and is **not** composed into any generated config.
- **SIZE CAP: soft, as scoring bonuses/penalties, not a hard cap.**
  `skills/schliff/scripts/scoring/efficiency.py:201-203` — "Bonus for conciseness: under 300 lines
  with good signal (+5)", `if total_lines <= 300 and density >= 3`. :190 penalizes
  `total_words > 2000 and density < 3`. Comment at :167-168 explicitly rejects a hard cap:
  "The denominator is deliberately NOT capped. Capping it at 1500 words removed a real defect".
- **Hooks / telemetry / tests:** hooks yes — `skills/schliff/hooks/hooks.json` +
  `session-injector.js`. No telemetry found. Tests: 98 files in `skills/schliff/tests/unit/`
  plus `tests/proof/` and `tests/fixtures/`; `eval-suite.json`; `scripts/test-self.sh`
  (dogfooding), `scripts/run-eval.sh`, `scripts/parallel-runner.py`, `benchmarks/`.
  Action inputs: `skill-path`, `eval-suite`, `minimum-score` (default '0'), `comment-on-pr`,
  `schliff-version`. ADR-0004 also fixes the gate as deterministic: "Auto-loop gating uses the
  existing deterministic 15-point regression guard ... The LLM-Judge from Phase P3 is advisory."

---

## 7. c0x12c/ai-toolkit (was spartan-stratos/spartan-ai-toolkit)
- 101 stars · created 2026-03-21 · pushed 2026-06-18 · **no license file detected by the API
  (`license: null`)** · JavaScript. Version 1.27.0.
- **Structure:** npm package `@c0x12c/ai-toolkit`, `"bin": {"ai-toolkit": "./bin/cli.js"}`, entry
  `toolkit/bin/cli.js` (954 lines). Libs `toolkit/lib/{assembler,detector,resolver,packs}.js`.
  Content is markdown: 70 command files in `toolkit/commands/spartan/`, `toolkit/rules/`,
  `toolkit/skills/`, `toolkit/agents/`, `toolkit/frameworks/`, `toolkit/claude-md/` (numbered
  fragments 00-header … 90-footer that the assembler concatenates), `toolkit/packs/*.yaml`,
  `toolkit/templates/`, `toolkit/codex/spartan.zsh`. Also `bridges/{core,telegram}`.
- **MULTI-TARGET: yes.** Target list is inline in `toolkit/bin/cli.js:114` — "Choices: claude-code,
  cursor, windsurf, codex, copilot" — with path mapping at :173-180:
  `cursor: .cursor/rules`, `windsurf: .windsurf/rules`, `copilot: .github/instructions`, plus
  `AGENTS.md` at repo root; codex at `.codex` (global `~/.codex`). `--format=agents-md` exports a
  cross-tool AGENTS.md (:119).
- **SWITCHABLE PREFERENCE VARIANTS: no — the "profiles" are tech-stack profiles.**
  `toolkit/profiles/{go-standard,java-spring,kotlin-micronaut,python-django,python-fastapi,
  react-nextjs,typescript-node,custom}.yaml`. Each declares `stack:`, `architecture:`, `rules:`
  (shared/backend/frontend file lists), `file-types:`, `commands:` and a `review-stages:` list.
  The closest thing to a review-ceremony knob is per-stage on/off:
  `toolkit/profiles/go-standard.yaml` — 7 stages (correctness, stack-conventions, test-coverage,
  architecture, database-api, security, documentation-gaps) each with `enabled: true`. That is a
  toggle set, not named alternative profiles of one axis.
- **SIZE CAP: only for its own authored content, advisory.**
  `toolkit/rules/core/SKILL_AUTHORING.md:169` — "SKILL.md is under 120 lines (split if longer)";
  :59 table row "Under 100 lines | One file is fine".
  `toolkit/commands/spartan/init-project.md:159` — "File is under 200 lines (concise enough for
  Claude to read quickly)". `toolkit/commands/spartan/context-save.md:167` — "Keep under 50 lines."
  A reporting-only budget in `toolkit/scripts/gen-codex-skills.js:184-200` prints a per-skill
  "Token Budget (codex)" table (`tokens = length/4`) but enforces nothing.
- **Hooks / telemetry / tests:** hooks yes — `toolkit/hooks/spartan-check-update.js`,
  `spartan-statusline.js`. No telemetry. Tests: three vitest/node test files
  (`assembler.test.js`, `detector.test.js`, `resolver.test.js`). CI:
  `.github/workflows/{validate,publish,release}.yml`.
- Licensing note for Jake: `gh api` reports `license: null` — no LICENSE file in the tree. Under
  the permissive-commercial stance this is unresolved material.

---

## 8. aryaminus/controlkeel
- 11 stars · created 2026-03-18 · pushed 2026-09-21 · **NOASSERTION** (license file present but
  not SPDX-recognised) · Elixir, v0.4.19, `elixir ~> 1.15`
- **Structure:** a Phoenix/OTP **server**, not a config generator. 1,028 blobs. `lib/controlkeel/`
  with `cli/`, `cloud/`, `mcp/` (MCP server, tools like `ck_token_audit`), `policy/`, `runtime/`,
  `agent/`, `governance/`, `intent/`, `mission.ex` (5,700+ lines). Deployment: Dockerfile,
  fly.toml, docker-compose, `deploy/`, Helm-ish `ops/`. `plugin.json` + `glama.json` for MCP
  directory listing.
- **Entry point:** `lib/controlkeel/cli.ex` / `bin/`; MCP protocol at `lib/controlkeel/mcp/protocol.ex`.
- **MULTI-TARGET: yes.** Two lists:
  - `lib/controlkeel/agent/router.ex:35` `@agents %{...}` — a capability catalogue keyed by agent
    id ("claude-code", "cursor", "windsurf", "kiro", …), each with `capabilities:`, `cost_tier:`,
    `security_tier:`, `swe_bench_score:`, `context_window_k:`, `local:`.
  - `lib/controlkeel/agent/acp_registry.ex:9` `@registry_id_overrides %{"droid" => ["factory-droid"],
    "cursor" => ["cursor"], "cline" => ["cline"], "goose" => ["goose"], "opencode" => ["opencode"]}`,
    synced from `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`.
- **SWITCHABLE PREFERENCE VARIANTS: named modes exist, but they are *derived*, not user-selected
  profiles composed into a config.**
  - `lib/controlkeel/agent/autonomy_loop.ex:10` —
    `@autonomy_modes ["advise", "supervised_execute", "guarded_autonomy", "long_running_autonomy"]`.
    `autonomy_mode/1` (:306-327) honours an explicit `metadata["autonomy_mode"]` /
    `brief["autonomy_mode"]` if it is in the list, otherwise infers from session state, defaulting
    to `"guarded_autonomy"`. `session_autonomy_profile/1` (:12) returns mode + label + human_role +
    operator_posture.
  - `lib/controlkeel/intent/execution_posture.ex:9` `@default_posture` and `build/1` compute
    `exploration_surface / state_surface / api_execution_surface / mutation_surface / shell_role /
    clearance_focus` from the brief's `risk_tier` and `compliance` list — derived, not chosen:
    `"shell_role" => if(regulated?, do: "broad_fallback_only", else: "repo_local_fallback")`.
  - **Selectable policy packs** are the nearest real variant surface: `priv/policy_packs/*.json` —
    baseline, cost, security, ai_tools, gdpr, plus 15 industry packs (healthcare, finance, legal,
    hr, government…). Rules are `{id, category, severity, action: block|warn, plain_message,
    matcher}`. `cost.json` holds a budget posture: `cost.budget_warning` at `ratio_gte: 0.8` (warn)
    and `cost.budget_guard` at `ratio_gte: 1.0` (block). Loaded by
    `lib/controlkeel/policy/pack_loader.ex`. These are domain/compliance packs, not
    autonomy/strictness variants of a single axis.
- **SIZE CAP: none on always-loaded context.** It caps *spend* (cost pack above) and bounds loops
  (`lib/controlkeel/runtime/bounded_loop*.ex`), not instruction-file size.
- **Hooks / telemetry / tests:** MCP server + CLI dispatch rather than editor hooks; `test/` dir
  present; ADRs in `docs/adrs/`; `lib/controlkeel/benchmark/` and eval tooling.
- Licensing note for Jake: NOASSERTION — needs a read of the LICENSE text before use.

---

## 9. adhenawer/claude-snapshot
- **2 stars** · created 2026-04-16 · pushed 2026-04-19 (dormant) · MIT · JavaScript
- **Structure:** a Claude Code **plugin** + Node script. 29 files. `.claude-plugin/plugin.json`
  (v0.3.0) and `.claude-plugin/marketplace.json`; four slash commands as markdown
  (`commands/{export,apply,diff,inspect}.md`); the logic is one file, `src/snapshot.mjs` (882 lines).
- **Entry point:** `src/snapshot.mjs`.
- **MULTI-TARGET: no.** Claude Code only. It captures `~/.claude/settings.json`, `~/.claude/CLAUDE.md`,
  `~/.claude/hooks/*`, `~/.claude.json`, installed plugins, known marketplaces and MCP servers
  (`src/snapshot.mjs:14-18, 109-183`).
- **SWITCHABLE PREFERENCE VARIANTS: no.** It is a byte-mover: export → manifest with sha256
  checksums (`src/snapshot.mjs:224-247`) → diff → apply. No opinion about content.
- **SIZE CAP: none.**
- **Hooks / telemetry / tests:** it *captures* hooks but installs none. No telemetry.
  Tests: `tests/snapshot.test.mjs` with `tests/fixtures/fake-claude-home/` and a
  `golden-manifest.json`; CI `.github/workflows/test.yml`; `docs/SMOKE_TEST.md`.
- Relevant detail: `sanitizeSettings()` (:64) and `normalizePaths()` (:46) rewrite `<user-home>` →
  `$HOME` and strip machine-specific absolute paths (e.g. nvm Node binary pins) so a snapshot is
  portable.

---

## 10. nizos/tdd-guard
- **2,346 stars** (largest of the ten) · created 2025-07-07 · pushed 2026-09-14 · MIT · TypeScript
- **Structure:** npm CLI + Claude Code hook. `package.json` `"bin": {"tdd-guard":
  "dist/cli/tdd-guard.js"}`, entry `src/cli/tdd-guard.ts`. `src/hooks/` implements the hook events
  (PreToolUse-style `processHookData.ts`, `sessionHandler.ts`, `userPromptHandler.ts`,
  `postToolLint.ts`, `testCounter.ts`). Validation is LLM-backed:
  `src/validation/models/{ClaudeAgentSdk,ClaudeCli,AnthropicApi}.ts` against prompts in
  `src/validation/prompts/{rules,system-prompt,response,file-types}.ts`. Also ships a
  Claude plugin (`plugin/{hooks,skills}`, plugin.json v1.3.0).
- **MULTI-TARGET: no for agent runtimes; yes for test frameworks.** README:15 "Automated
  Test-Driven Development enforcement for **Claude Code**." The multi-target dimension is
  `reporters/{vitest,jest,pytest,phpunit,go,rust,rspec,minitest,junit5,dotnet,storybook}` — 11
  language reporters, each a separately published package. Note the deprecation banner, README:10-14:
  "**TDD Guard grew into [Probity](https://github.com/nizos/probity)**: the same TDD enforcement,
  now for Claude Code, Codex, and GitHub Copilot CLI, with more reliable validation and no test
  reporters to set up. New projects should start there."
- **SWITCHABLE PREFERENCE VARIANTS: no — one fixed rule set plus an on/off toggle and a
  user-override file.**
  - On/off: `docs/quick-commands.md` — "`tdd-guard on` - Enables TDD Guard enforcement /
    `tdd-guard off` - Disables"; implemented via the UserPromptSubmit hook
    (`src/hooks/userPromptHandler.ts`).
  - Override, not variant: `docs/custom-instructions.md` — "You can override these default rules by
    creating a custom instructions file at `.claude/tdd-guard/data/instructions.md`… Your custom
    instructions are never overwritten." The defaults live in `src/validation/prompts/rules.ts`
    (59 lines). There is exactly one default rule set; no named strict/lenient alternatives.
  - Model choice is a config axis but not a behavioural profile: `src/config/Config.ts:12-20` —
    `DEFAULT_MODEL_VERSION = 'claude-sonnet-4-6'`, `DEFAULT_CLIENT: ClientType = 'sdk'`,
    `VALID_CLIENTS = new Set(['api','cli','sdk'])`, with legacy `MODEL_TYPE_TO_CLIENT` mapping.
    Env vars `TDD_GUARD_ANTHROPIC_API_KEY`, `TDD_GUARD_MODEL_VERSION`, `LINTER_TYPE=eslint`,
    `USE_SYSTEM_CLAUDE`.
- **SIZE CAP: none.** `src/validation/prompts/rules.ts` is 59 lines with no length rule; no cap on
  the user's `instructions.md`.
- **Hooks / telemetry / tests:** hooks are the whole product. No telemetry. Tests are extensive —
  co-located `*.test.ts` beside nearly every source file, plus `test/utils/factories/`,
  vitest config, `docs/adr/` (6 ADRs), CI `ci.yml` + `security.yml`.
- Data dir is fixed by design: `docs/adr/003-remove-configurable-data-directory.md` — chosen for
  "Better security posture - Follows principle of least privilege". `DEFAULT_DATA_DIR =
  .claude/tdd-guard/data`.

---

# Synthesis: are working preferences modelled as switchable named variants?

**One of the ten does it: GeiserX/LynxPrompt. The other nine ship a single fixed rule set plus
on/off toggles, severity thresholds, or stack/domain packs.**

Evidence for the one:
- Autonomy as a named preset composed into the generated file —
  `cli/src/index.ts:46` `.option("--boundaries <level>", "Boundary preset (conservative, standard,
  permissive)")`; `cli/src/utils/generator.ts:298` `const BOUNDARIES: Record<string, {always,
  askFirst, never}>`; composed at `cli/src/utils/generator.ts:1157`
  `const presetBoundaries = BOUNDARIES[options.boundaries] || BOUNDARIES.standard;`.
- Plan/review ceremony as a six-value named axis — `packages/shared/src/wizard/ai-behavior.ts:22`
  `PLAN_MODE_FREQUENCY = [always, complex_tasks, multi_file, new_features, on_request, never]`,
  rendered at `cli/src/utils/generator.ts:1024-1033`.
- Verbosity as a three-value named axis — `cli/src/commands/wizard.ts:3040-3051`
  (concise | balanced | detailed).
- These are *composed* into the output for ~38 runtimes via `src/lib/platforms.ts` /
  `src/lib/file-generator.ts`, which is the composition property in question.
- What LynxPrompt does *not* model: test strictness (it is a multi-select of levels, not a
  posture), delegation depth (absent entirely), and cost posture (absent entirely).

Near-misses, and why they do not count:
- **Zandereins/schliff** has a genuine autonomy axis as two named modes — autonomous vs advisor,
  `docs/adr/0004-both-modes-ship-judge-advisory.md`, "Autonomous mode is the documented default…
  Advisor is opt-in via flag" — but it governs schliff's own patch loop, not a generated config.
  Its `WEIGHT_PROFILES` (`scoring/registry.py:48`) are keyed by file format, not by preference.
- **aryaminus/controlkeel** has four named autonomy modes
  (`agent/autonomy_loop.ex:10` `["advise","supervised_execute","guarded_autonomy",
  "long_running_autonomy"]`) and a derived execution posture
  (`intent/execution_posture.ex`), but the mode is inferred from session state and defaults to
  `guarded_autonomy`; there is no user-facing "pick your posture" that is then written into a
  config file. Its selectable packs (`priv/policy_packs/*.json`) are domain/compliance packs —
  healthcare, gdpr, finance, cost — not alternative profiles of one behavioural axis.
- **c0x12c/ai-toolkit** has `toolkit/profiles/*.yaml`, but the axis is tech stack
  (`stack: go-standard`, `architecture: clean`), and the review dimension is a set of seven
  independently `enabled: true` stages — on/off toggles, not named alternatives.
- **caliber-ai-org/ai-setup**, the most sophisticated generator of the ten, is the clearest
  counter-example: it has 5 provider adapters, an LLM generation pipeline, scoring, and hooks, and
  zero preference axes. A full grep of `src/` for profile|preset|variant|persona|stance|posture|
  strictness|autonomy returns nothing but `PERSONAL_LEARNINGS_FILE` and a `--personal` scope flag.
  Its behaviour is derived from a codebase fingerprint, not from stated working preferences.
- **agnix**, **agents-md-cookbook**, **cc-audit**, **pro-pack**, **claude-snapshot** and
  **tdd-guard** are all single-rule-set: their only axes are severity, rule enable/disable
  (`.agnix.toml disabled_rules`, `[rules] skills = true`), numeric thresholds
  (`{ maxBytes }`, `{ softLimit }`, `minimum-score`), or a global on/off (`tdd-guard off`).

Cross-cutting facts:
- Six of ten enforce or advise a size cap, and the numbers do not agree:
  200 lines / 1500 tokens (agnix), 200 lines with 150 ideal (cc-audit, stated without a source),
  ~200 lines prose (pro-pack), 400 lines and 2000-5000 tokens (caliber, internally inconsistent),
  32,768 bytes hard-error plus 150/300 lines warn (cookbook, the only one that cites a mechanism —
  Codex's `project_doc_max_bytes` truncation), 300 lines as a scoring bonus (schliff).
  LynxPrompt, controlkeel, claude-snapshot and tdd-guard have none.
- Two collect telemetry: agnix (opt-in, with `consent_timestamp`) and caliber (PostHog, key
  hardcoded at `src/telemetry/index.ts:12`, opt-out).
- Two have no license or a non-SPDX one: `c0x12c/ai-toolkit` (`license: null`) and
  `aryaminus/controlkeel` (NOASSERTION).
