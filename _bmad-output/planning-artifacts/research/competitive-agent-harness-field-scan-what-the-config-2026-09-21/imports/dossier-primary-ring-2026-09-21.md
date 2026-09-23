# Competitor scan — 10 agent-config repos

Facts from repo contents (shallow clones + `gh api`), 2026-09-21. Stars/dates from
`gh api repos/<owner>/<repo>`. File counts are `git ls-files` at default HEAD.

---

## 1. dyoshikawa/rulesync — the only real multi-runtime compiler

- MIT · 1,457 stars · created 2025-06-18 · pushed 2026-09-21 · 1,240 files.
- TypeScript CLI. Entry point `src/cli/index.ts` → `package.json` `bin: {"rulesync": "dist/cli/index.js"}`.
  Build `tsdown`. Also exports a library (`dist/index.cjs`).
- Commands (`src/cli/commands/`): `generate`, `import`, `convert`, `add`, `init`, `install`
  (npm/gh/apm sources), `fetch`, `mcp`, `gitignore`, `doctor`, `docs`, `update`, `release-notes`.
- **Source of truth**: `.rulesync/` in the project — `rules/*.md`, `skills/<name>/SKILL.md`,
  `subagents/*.md`, `commands/`, `mcp.jsonc`, `hooks.jsonc`, `permissions.jsonc`, `checks/`.
  Config `rulesync.jsonc` (+ `.local` overlay), JSON-schema-published.

### Target tools (the list and where it lives)

`src/types/tool-target-tuples.ts` holds one tuple per **feature**; `src/types/tool-targets.ts`
computes `ALL_TOOL_TARGETS` as their set-union — comment: *"A tool exists iff at least one
feature supports it, so the master list is the union of every feature's tuple — no
separately-maintained literal to drift."*

**52 unique targets**: agentsmd, agentsskills, aiassistant, amp, antigravity-cli,
antigravity-ide, antigravity-plugin, augmentcode, augmentcode-legacy, bob, claudecode,
claudecode-legacy, claudecode-plugin, cline, codebuddy, codexcli, commandcode, continue,
copilot, copilotcli, cortexcode, crush, cursor, deepagents, devin, dsh, factorydroid, goose,
grokcli, hermesagent, junie, kilo, kimi-code, kiro, kiro-cli, kiro-ide, musecode, opencode, pi,
pool, qwencode, reasonix, replit, roo, rovodev, tabnine, takt, vibe, warp, zcode, zed, zoocode.

Per-feature coverage (tuple lengths): rules 51, skills 50, mcp 45, permissions 38, subagents 37,
hooks 37, commands 35, ignore 25, checks 7. `PACKAGING_TOOL_TARGETS = ["antigravity-plugin",
"claudecode-plugin"]`; `LEGACY_TARGETS` excluded from `*` expansion (`src/config/config.ts`).

Per-target emitters live one file per tool per feature: `src/features/rules/cursor-rule.ts`,
`src/features/skills/zcode-skill.ts`, etc. (717 files under `src/features/`). Output is
**generated files**, not symlinks; `.gitignore`/`.gitattributes` entries are derived by
`rulesync gitignore` and CI-checked (`check:gitignore`).

Lockfile-ish: `src/features/hooks/hooks-ownership-lock.ts` writes
`.claude/.rulesync-hooks-lock.json` (`HOOKS_OWNERSHIP_LOCK_VERSION = 1`) recording which hook
entries rulesync owns, so hand-added hooks survive regeneration. Opt-in only.

### Validation / lint

`rulesync doctor` (`src/cli/commands/doctor.ts`) emits typed diagnostics
`{severity, code, file, message, hint, line, column}`. Codes: `config/unknown-target`,
`config/unknown-feature`, `config/deprecated-feature`, `config/invalid-value`,
`config/conflicting-targets`, `config/targets-features-conflict`, `config/unknown-key`,
`config/missing-schema`, `config/outdated-schema`, `config/parse-error`, `config/empty-file`,
`config/not-an-object`, `config/token-env-not-set`, `config/input-root-invalid`,
`config/input-roots-conflict`, `config/input-root-not-found`, `config/input-roots-duplicate`,
`config/no-config-file`. Conflict detection is only pairwise legacy aliases:
`CONFLICTING_TARGET_PAIRS = [["augmentcode","augmentcode-legacy"],["claudecode","claudecode-legacy"]]`.

Size caps are per-target limits, not an instruction budget: `SKILL_DESCRIPTION_MAX_LENGTH = 1024`
(`src/features/skills/skills-utils.ts`), `MAX_FILE_SIZE = 10MB`, `MAX_CARRIED_BYTES = 100MB`.
**No token-budget or always-loaded-context cap. No contradiction detection between rules.**

### Preference variants

**None of its own.** Every hit for preset/posture is *modelling another tool's* knob, e.g.
`src/types/permissions.ts:798` — "The Antigravity CLI's four documented `toolPermission`
autonomy presets" (`request-review` / `proceed-in-sandbox` / `always-proceed` / `strict`), and
:439 — "YOLO cannot be authored at all, being a run-time posture rather than config."
Rulesync's own config axis is *which targets and features are on*, not behavioural profiles.

### Hooks / tests / CI

Models hooks for 37 targets. 461 `*.test.ts` (vitest) + `src/e2e/`. 13 workflows; `cicheck` =
fmt + oxlint + typecheck + test + cspell + secretlint + four generated-content drift checks
(`check:supported-tools` regenerates README/`docs/reference/supported-tools.md` and fails on diff).

---

## 2. YawLabs/ctxlint — the only linter of the instruction set itself

- MIT · 9 stars · created 2026-04-05 · pushed 2026-09-20 · 267 files · v0.27.2.
- TypeScript, esbuild (`build.mjs`). Entry `bin/ctxlint.mjs` → `src/cli.ts`. Also a GitHub
  Action (`action.yml`, composite), a pre-commit hook (`.pre-commit-hooks.yaml`, pinned
  `npx` against version 0.27.2 of the npm package with `--strict`), and an MCP server mode (`node dist/index.js --mcp-server`).
- **Does not project or sync anything.** It reads; it never writes config for other runtimes
  (it has a `--fix` path for its own findings only, `src/core/fixer.ts`).
- Discovers context files across runtimes (`src/core/scanner.ts` `CONTEXT_FILE_PATTERNS`):
  CLAUDE.md / CLAUDE.local.md / `.claude/rules/*.md`, AGENTS.md / AGENT.md / AGENTS.override.md,
  `.cursorrules` + `.cursor/rules/*.{md,mdc}`, `.github/copilot-instructions.md` +
  `.github/instructions/*.md`, `.windsurfrules` + `.windsurf/rules/*.md`, GEMINI.md,
  `.clinerules`, `.aiderules`, `.aide/rules/*.md`, `.amazonq/rules/*.md`, `.goose/instructions.md`,
  `.goosehints`, `.junie/guidelines.md`, `.aiassistant/rules/*.md`, and MCP configs
  (`.mcp.json`, `.cursor/mcp.json`, `~/.codeium/windsurf/mcp_config.json`, …).

### Rules — 90 total, in four JSON catalogs at repo root

Catalog files: `context-lint-rules.json` (43), `mcp-config-lint-rules.json` (29),
`agent-session-lint-rules.json` (13), `agent-skill-lint-rules.json` (5). Each rule:
`{id, category, severity, description, trigger, message, fixable, fixDescription, stability}`.
Implementations in `src/core/checks/<category>.ts`; `src/core/__tests__/catalog-consistency.test.ts`
keeps catalog and code in sync. Prose specs: `CONTEXT_LINT_SPEC.md`, `MCP_CONFIG_LINT_SPEC.md`,
`AGENT_SESSION_LINT_SPEC.md`, `AGENT_SKILL_LINT_SPEC.md`.

**context-lint-rules.json (43)** — categories paths, commands, staleness, tokens, tier-tokens,
redundancy, contradictions, frontmatter, ci-coverage, ci-secrets, hook-coverage, content-secrets:

- paths/not-found, paths/glob-no-match, paths/directory-not-found
- commands/script-not-found, make-target-not-found, no-makefile, npx-not-in-deps,
  tool-not-found, package-json-missing, exit-status-masked, unknown-subcommand,
  gradle-project-not-found, maven-module-not-found
- staleness/stale (30+ days), staleness/aging (14–30 days)
- tokens/excessive (error), tokens/large (warning), tokens/info, tokens/aggregate
- tier-tokens/section-breakdown, tier-tokens/aggregate, tier-tokens/hard-enforcement-missing
  ("An always-loaded file uses inviolable framing (NEVER / ALWAYS / DO NOT / MUST NOT)…")
- redundancy/tech-mention, redundancy/discoverable-dir, redundancy/duplicate-content
- contradictions/conflict
- frontmatter/missing, missing-field, invalid-value, unclosed, no-activation
- ci/no-release-docs, ci/undocumented-secret
- hook-coverage/dead-hook (a PreToolUse hook or permissions entry in `.claude/settings.json`
  pointing at something that no longer exists)
- content-secrets/{private-key-header, aws-access-key, github-pat, anthropic-key, openai-key,
  npm-token, slack-token, google-api-key, stripe-secret}

**agent-skill (5)**: skill/missing-frontmatter, skill/broken-ref, skill/trigger-collision,
skill/orphaned, skill/dead-tool-restriction.

**agent-session (13)**: session/missing-secret, diverged-file, missing-workflow, stale-memory,
duplicate-memory, consecutive-repeat, cyclic-pattern, memory-index-overflow ("MEMORY.md exceeds
Claude Code's session-load cap. The first 200 lines / 25KB are…"), shared-temp-path,
unverified-gate-claimed-clean, default-branch-accumulation, unresolvable-sha, large-read.

**mcp-config (29)**: mcp-schema/{invalid-json, wrong-root-key, missing-root-key, missing-command,
missing-url, no-name-field, unknown-transport, ambiguous-transport, empty-servers},
mcp-security/{hardcoded-bearer, hardcoded-api-key, secret-in-url, secret-scan-skipped,
http-no-tls}, mcp-commands/{windows-npx-no-wrapper, command-not-found, args-path-missing},
mcp-deprecated/sse-transport, mcp-env/{wrong-syntax, unset-variable, empty-env-block},
mcp-urls/{malformed-url, localhost-in-project-config, missing-path},
mcp-consistency/{same-server-different-config, duplicate-server-name, missing-from-client},
mcp-redundancy/{disabled-server, identical-across-scopes}.

### Size caps (the direct analogue to a 196-line always-loaded ratchet)

`src/core/checks/tokens.ts`:

```ts
export const DEFAULT_TOKEN_THRESHOLDS: TokenThresholds = {
  info: 1000, warning: 3000, error: 8000,
  aggregate: 5000, tierBreakdown: 1000, tierAggregate: 4000,
};
```

Overridable per project via `.ctxlintrc` `tokenThresholds`.

### Conflict detection

`src/core/checks/contradictions.ts` — a hardcoded `DIRECTIVE_CATEGORIES` list of **eight axes**:
testing framework, package manager, indentation style, semicolons, quote style, naming
convention, CSS approach, state management. It clusters conflicting directives across files and
emits one issue per cluster: `` `${category} conflict: "${a.label}" in ${fileA} vs "${b.label}" in ${fileB}` ``.
This is tool-choice contradiction, not behavioural-stance contradiction.

### Config

`src/core/config.ts` `CtxlintConfig` / `KNOWN_CONFIG_KEYS`: `checks`, `ignore`, `ignoreRules`,
`strict`, `tokenThresholds`, `contextFiles`, `exclude`, `mcp`, `mcpOnly`, `mcpGlobal`, `session`,
`sessionOnly`, `skills`, `skillsOnly`, `hooksGlobal`. Unknown keys get a Levenshtein "did you
mean" suggestion. Type-level exhaustiveness guard both directions.

### Preference variants

**None.** Only `--strict` (severity escalation). Every "posture" hit is a code comment about
false-positive tolerance (`src/core/checks/commands.ts:269`, `content-secrets.ts:152`).

### Tests / CI

79 test files (vitest) under `src/**/__tests__/` plus `fixtures/` of deliberately-broken
projects (bloated-claude-md, broken-paths, contradictions, directive-conflict,
masked-exit-status, mcp-configs/*). **No CI workflows of its own** — `.github/` holds only
CODEOWNERS. `test` = `prettier --check . && vitest`.

---

## 3. obra/superpowers

- MIT · 289,730 stars · created 2025-10-09 · pushed 2026-09-20 · 231 files · v6.4.1.
- **Markdown methodology + shell scripts, no compiler.** 119 `.md`, 45 `.sh`, 11 `.js`, 6 `.py`.
- 15 skills under `skills/`: brainstorming, diagnosing-superpowers,
  dispatching-parallel-agents, executing-plans, finishing-a-development-branch,
  receiving-code-review, requesting-code-review, subagent-driven-development,
  systematic-debugging, test-driven-development, using-git-worktrees, using-superpowers,
  verification-before-completion, writing-plans, writing-skills.
- Multi-runtime by **hand-committed manifests pointing at the same `skills/` dir**, not
  generation: `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`,
  `.cursor-plugin/`, `.devin-plugin/`, `.hermes-plugin/{plugin.yaml,__init__.py}`,
  `.kimi-plugin/`, `.muse-plugin/`, `.opencode/plugins/superpowers.js`,
  `.pi/extensions/superpowers.ts`, `.agents/plugins/marketplace.json`,
  `gemini-extension.json`. `index.js` re-exports the OpenCode plugin for directory-form
  registration. `package.json` declares a `pi` block (`extensions`, `skills`).
- Only outbound sync script: `scripts/sync-to-codex-plugin.sh` — rsyncs the checkout into a
  fork of `prime-radiant-inc/openai-codex-plugins` and opens a PR. One-way, one destination.
- Hooks: `hooks/hooks.json` (Claude `SessionStart` on `startup|clear|compact` →
  `hooks/run-hook.cmd session-start`), `hooks/hooks-cursor.json`, `hooks/session-start`.
- Tests: 66 files (`tests/claude-code/run-skill-tests.sh`, `tests/brainstorm-server/*.test.js`,
  `tests/antigravity/`), plus `tests/claude-code/analyze-token-usage.py`.
  `.pre-commit-config.yaml` and `scripts/lint-shell.sh`. **No GitHub Actions workflows.**
- **No preference variants and no instruction linting.**

## 4. garrytan/gstack — closest thing to a stance system, but learned not selected

- MIT · 133,865 stars · created 2026-03-11 · pushed 2026-09-21 · 2,296 files (1,351 `.ts`).
- Bun/TypeScript monorepo. Install entry `./setup` (a 161 KB bash installer); build
  `scripts/build.sh`; ~89 `bin/gstack-*` executables. Compiled gate binaries via
  `bun build --compile` (`browse`, `make-pdf`, diagram-render).
- **Template-based host projection**: every skill is `SKILL.md.tmpl` → generated `SKILL.md`
  with the banner `<!-- AUTO-GENERATED from SKILL.md.tmpl — do not edit directly -->`.
  Generator `scripts/gen-skill-docs.ts` (`bun run gen:skill-docs`), `--dry-run` used by CI as a
  freshness check. Resolvers in `scripts/resolvers/`, placeholders `{{PLACEHOLDER}}`.
- Hosts: `hosts/index.ts` — `export const ALL_HOST_CONFIGS: HostConfig[] = [claude, codex,
  factory, kiro, opencode, slate, cursor, openclaw, hermes, gbrain];` one `hosts/<name>.ts`
  each, plus `hosts/claude/hooks/*` (7 Claude hooks: auq-error-fallback, memorable-user-prompt,
  question-log, question-preference, timeline-stop, spawn-bin, spawned-directive).
  Per-host `suppressedResolvers` do graceful degradation.
- **Preference axes — `bin/gstack-developer-profile`** (supersedes `bin/gstack-builder-profile`,
  now a shim). Stores `~/.gstack/developer-profile.json` with **declared vs inferred** values on
  five continuous dimensions: `['scope_appetite','risk_tolerance','detail_preference','autonomy','architecture_care']`,
  each defaulting to `0.5`. Subcommands `--derive` (recompute from
  `~/.gstack/projects/{SLUG}/question-events.jsonl`), `--gap`, `--trace <dim>`,
  `--check-mismatch` (flags declared ≠ inferred beyond a threshold), `--migrate`, `--vibe`
  (one-word archetype, v2 stub). This is a **scalar preference model, not named switchable
  variants** — you do not pick "autonomy: execute" from a set; the system infers a number and
  reports drift from what you declared.
- Skill-level modes exist but are per-skill behaviours, not a cross-cutting axis:
  `codex/sections/{challenge,consult,review}-mode.md`, `careful/` (destructive-command
  guardrails via a PreToolUse hook), `guard/`, `freeze`/`unfreeze`.
- Tests: 1,462 test files, `test/hermetic-wiring.test.ts` pins hermetic invocation
  (`CLAUDE_CONFIG_DIR`, temp `GSTACK_HOME`, `--strict-mcp-config`). 18 workflows + `.gitlab-ci.yml`,
  `.osv-scanner.toml`, `slop-scan.config.json`.
- Analytics/telemetry present: `bin/gstack-analytics`, `bin/gstack-context-bill`,
  `bin/gstack-community-dashboard`.
- No instruction-size lint; the generated-vs-committed drift check is the only "lint" of content.

## 5. RyanAlberts/pmstack

- MIT · 8 stars · created 2026-04-15 · pushed 2026-09-12 · 182 files (125 `.md`) · v1.2.0.
- Claude Code only. Entry: `install.sh` (curl | bash, clones then runs `./setup`); `./setup`
  copies CLAUDE.md, skills, templates and slash commands into a project or `~/.claude`
  (`--global`, `--dry-run`). **No projection to other runtimes.**
- Executable code is the eval harness: `bin/eval-harness.mjs` (validate/run/report,
  trusted-adapter model), `bin/run-eval.py`, `bin/eval-report.py`, `bin/work-review.mjs`,
  `docs/workspace/eval-engine.mjs`.
- 21 `claude-skills/pmstack-*` + 14 flat `skills/*.md` with `skills/_graph.yaml` and
  `skills/_decision-log.md`.
- "Lint" exists but is an **artifact** lint, not an instruction lint:
  `claude-skills/pmstack-lint/SKILL.md` — "Walks the pmstack skill graph against the outputs/
  directory to find graph gaps…, cross-artifact drift…, and stale candidates". It is a prompt,
  not code.
- Evals: `evals/*.test.mjs`, `evals/golden/baseline.json`, `evals/pmstack-self.yaml`.
  **No CI workflows, no hooks.** No preference variants (one `category: autonomy` row appears
  inside an *example* eval comparing Cursor and Windsurf).

## 6. wshobson/agents — second-best multi-runtime generator

- MIT · 39,855 stars · created 2025-07-24 · pushed 2026-09-21 · 1,175 files (767 `.md`, 292 `.json`, 65 `.py`).
- Source of truth `plugins/<name>/{agents,skills,commands}/*.md` (1,007 files) +
  `.claude-plugin/marketplace.json`. Generator entry **`tools/generate.py`**:
  `--harness <codex|copilot|cursor|opencode|antigravity|pi> [--plugin N] [--all] [--clean] [--prune] [--strict]`,
  driven from a `Makefile` (`generate`, `generate-all`, `validate`, `garden`, `smoke-test`).
- Adapters: `tools/adapters/{codex,copilot,cursor,opencode,antigravity,pi}.py` +
  `base.py` (`HarnessAdapter` ABC) + `capabilities.py`. Outputs are generated files with
  per-harness clean targets in `_HARNESS_TARGETS` (`.codex`, `.agents/plugins`, `.cursor`,
  `.cursor-plugin`, `.opencode` + `opencode.json`, `.copilot/{agents,skills,commands}`,
  `.antigravity`, `.pi/{skills,prompts,agents}`). Static Cursor rules live in
  `tools/adapters/cursor_rules/*.mdc`.
- **Capability matrix** `tools/adapters/capabilities.py` — "Single source of truth consumed by
  adapters (for graceful degradation), the docs generator…, and plugin-eval". Seven harnesses:
  claude-code, codex, copilot, cursor, opencode, antigravity, pi. Fields per harness:
  `skills_native`, `agents_native`, `commands_native`, `plugin_marketplace`, `parallel_agents`,
  `tool_allowlist_per_agent`, `todowrite`, `task_spawn`, `mcp_servers`, `hooks`,
  `context_file_name`, `context_file_max_lines`, `skill_body_max_bytes`, `tool_name_case`,
  `bare_model_aliases`, `notes`.
- **Size caps as data**: `_CONTEXT_LINES_CAP = 150` ("Authoring cap (CI enforces)") and
  `_CODEX_SKILL_CAP = 8 * 1024` ("Hard truncation cap").
- Validation: `tools/validate_generated.py` (per-harness `validate_codex/cursor/opencode/
  antigravity/pi/copilot`, `--strict`), `tools/check_agent_name_collisions.py`,
  `tools/doc_gardener.py`. 6 workflows including `validate.yml`. 94 test-ish files
  (`tools/tests/test_adapters.py`, `test_cli_smoke.py`, …).
- **No preference variants.** Per-command flags only, e.g.
  `plugins/comprehensive-review/commands/full-review.md` argument-hint
  `[--security-focus] [--performance-critical] [--strict-mode]`.

## 7. anthropics/skills — content, and NOT open source

- **License: none declared at repo level** (`gh api` → `license: null`); every skill ships
  `skills/<name>/LICENSE.txt` reading: *"© 2025 Anthropic, PBC. All rights reserved… users may
  not: Extract these materials from the Services or retain copies of these materials outside
  the Services · Reproduce or copy these materials… · Create derivative works based on these
  materials"*. Under a permissive-commercial stance this is **excluded** — no-derivatives,
  no-redistribution. Do not vendor.
- 177,481 stars · created 2025-09-22 · pushed 2026-09-10 · 419 files.
- Pure content: 19 skills under `skills/` (academy-guide, algorithmic-art, brand-guidelines,
  canvas-design, claude-api, discernment-nudge, doc-coauthoring, docx, frontend-design,
  internal-comms, mcp-builder, pdf, pptx, skill-creator, slack-gif-creator, theme-factory,
  web-artifacts-builder, webapp-testing, xlsx). Ships Python helper scripts inside skills
  (70 `.py`) and font/XSD assets; no CLI, no installer, no top-level entry point.
- Projection: none. `.claude-plugin/marketplace.json` declares plugin bundles
  (`document-skills`, `example-skills`) whose `skills` arrays point at `./skills/<name>`.
- `spec/agent-skills-spec.md` is a 3-line stub redirecting to <https://agentskills.io/specification>.
  `template/SKILL.md` is the authoring template.
- No lint, no hooks, no CI workflows, 7 incidental test files.

## 8. OthmanAdi/planning-with-files — the only real *mode* system

- MIT · 27,046 stars · created 2026-01-03 · pushed 2026-09-21 · 729 files
  (206 `.sh`, 196 `.md`, 142 `.py`, 123 `.ps1`).
- Canonical source `skills/planning-with-files/`; entry scripts `scripts/inject-plan.sh`
  (+`.py`), `scripts/init-session.sh`, `scripts/check-complete.sh`, `scripts/gate-stop.sh`,
  `scripts/plan-doctor.sh`, all with PowerShell twins.
- **Projection by copy with drift verification**: `scripts/sync-ide-folders.py` —
  "Syncs shared files from the canonical source (skills/planning-with-files/) to all
  IDE-specific folders… `--verify` to check for drift without making changes (exits 1 if drift
  found)". `IDE_MANIFESTS` targets: `.cursor`, `.gemini`, `.codex`, `.pi` (also the npm package
  root), `.continue`, `.codebuddy`, `.factory`, `.opencode`, `.mastracode`, `.hermes`, `.kiro`.
  Explicitly never synced: `SKILL.md` (per-IDE frontmatter) and IDE-specific hooks/prompts.
- **Switchable modes** — `.mode` marker file next to the plan
  (`.planning/<id>/.mode`, or `./.mode` in legacy root mode), space-separated tokens written by
  `init-session.sh --autonomous` / `--gated`; `--gated` implies autonomous. Third composable
  token `inject-smart` (also `PWF_INJECT=smart`), plus a strictness-lowering `plan-guard-off`.
  Three effective profiles: **legacy** (no `.mode`; byte-identical v2.43 behaviour),
  **autonomous** (per-tool-call injection dropped — "strong models do not need the plan
  re-recited before every tool call, and the per-tick injection is the prompt-injection
  amplifier"), **gated** (adds the Stop-hook completion gate: "the gate is the termination
  oracle: it judges the plan artifact on disk, not the conversation transcript").
  Precedence, from `scripts/inject-plan.sh`: *"Root `.mode` is a FLOOR, not a default that slug
  scope replaces (#238)… A slug may opt into autonomous/gated where the root left it unset; it
  can no longer opt out of what the root committed."* `mode_has()` = raising tokens (either
  file); `mode_relax_allowed()` = the one lowering token needs both.
  Tiering is honest: "Hosts without a blocking Stop hook still get autonomous mode (low
  recitation + ledger). They do not get gate enforcement; the gate degrades to a notification."
- Hooks everywhere (44 hook-path files); `scripts/skill-hook.sh` is the single dispatcher.
- Validation: `scripts/plan-doctor.sh` is a self-check of the *mechanism* (plan resolution, hook
  injection, canonicalizer, attestation, install surfaces, hook wall-clock) — not a lint of
  instruction content. 127 test files (`tests/test_canonical_script_sync.py` etc.), 3 workflows
  (`tests.yml`, `skill-review.yml`, `skill-optimize-apply.yml`).

## 9. open-gsd/gsd-core — the heaviest engineering, and named model profiles

- MIT · 9,702 stars · created 2026-05-22 · pushed 2026-09-21 · 3,594 files
  (1,826 `.md`, 1,224 `.cjs`, 245 `.cts`) · v1.14.0.
- Node/TypeScript. Bins: `gsd-core` → `bin/install.js`, `gsd-tools` →
  `gsd-core/bin/gsd-tools.cjs`, `gsd_run`, `gsd-mcp-server` → `bin/gsd-mcp-server.js`.
  ~238 `.cts` modules in `src/`, compiled to `.cjs` in `gsd-core/`.
- **Projection**: `src/install-profiles.cts` is the "Skill Surface Budget Module — single source
  of truth for which skills/agents are written to the runtime config dirs (ADR-0011)", with
  `stageSkillsForProfile`, `stageAgentsForRuntimeWithConverter`, `stageCommandsForRuntimeFlat`,
  `buildNamespaceBundleMap`, plus `runtime-artifact-layout.cts`, `runtime-homes.cts`,
  `runtime-config-adapter-registry.cts`, `onboard-projection.cts`, `codex-agent-toml.cts`.
  Runtimes come from `gsd-core/bin/shared/runtime-aliases.manifest.json` — 16 families:
  claude, opencode, kilo, codex, copilot, antigravity, cursor, windsurf, augment, trae, qwen,
  hermes, kimi, kimi-code, codebuddy, cline. Committed host shims: `.claude-plugin/`,
  `.opencode/plugins/gsd-core.js`, `.kilo/plugins/gsd-core.js`, `pi/gsd.cjs`, `.clinerules`,
  `vscode/extension.js`. 20 `gen:*` / `regen:derived` scripts produce derived artifacts.
- **Named switchable variants — two real axes:**
  1. Model profiles (`src/model-catalog.cts` → `src/model-profiles.cts`): `MODEL_PROFILES`
     maps each agent to `{quality, balanced, budget, adaptive}` (from `meta.golden/balanced/
     budget` + `adaptiveTierMap[routingTier]`), with `VALID_PROFILES`, plus an `inherit`
     sentinel in `getAgentToModelMapForProfile`. Also `PROVIDER_PRESETS`,
     `RUNTIME_PROFILE_MAP`, `AGENT_DEFAULT_TIERS`/`VALID_AGENT_TIERS`, `nextTier`, and
     `EFFORT_RENDERING` per runtime (claude: `output_config.effort`, supported
     `low|medium|high|xhigh|max`, clamps `minimal`→`low`), `RUNTIMES_WITH_FAST_MODE`.
     This is a cost/quality stance expressed as named alternatives — the nearest match in the
     whole set to a harness "cost posture".
  2. Review depth (`src/code-review-depth.cts`): `type DepthTier = 'quick' | 'standard' | 'deep'`,
     `DEPTH_TIERS`, resolution order flag → per-path rule → config → default `standard`, with
     automatic downgrade `deep → standard` past `LARGE_SCOPE_THRESHOLD` files, and an
     `INVALID_DEPTH` diagnostic.
  Neither is a behavioural stance in the "how autonomous / tests mandatory" sense; there is no
  named alternative for those.
- **Linting**: 65 `scripts/{lint,check}-*.cjs` — contract drift, alias drift, identity drift,
  phase-id drift, allowed-tools parity, command-contract, docs-required, docs-guard-registration,
  eslint-glob-coverage, completion-predicate/ratio drift, default-flip documentation,
  frontmatter scalar grep, mutation-score ratchet, coverage gate, npm integrity — plus 11 custom
  ESLint rules in `eslint-rules/` (`no-adhoc-markdown-parsing`, `no-bare-npm-exec`,
  `no-crlf-fragile-split`, `no-exact-case-env-access`, `no-external-require-in-bin`, …).
  No always-loaded token budget, but `src/prompt-budget.cts` and `src/context-utilization.cts`
  exist. Secret scanning: `scripts/secret-scan.sh --diff origin/main --strict`,
  `.secretscanignore` with a required annotation format.
- Hooks: 42 hook files incl. `hooks/gsd-statusline.js` (model, context-window meter, GSD state).
  Tests: 1,248 files, Stryker mutation testing (`stryker.config.mjs`), 31 workflows,
  544 changesets, `TESTING-STANDARDS.md`.

## 10. addyosmani/agent-skills

- MIT · 98,140 stars · created 2026-02-15 · pushed 2026-09-20 · 198 files · v0.6.10.
- Content-first with a JS validation layer. 31 skill files under `skills/`; commands in
  `.claude/commands/*.md` mirrored as `.gemini/commands/*.toml`; marketplace manifests
  `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`,
  `.agents/plugins/marketplace.json`, `.opencode/skills`. The Gemini `.toml` mirrors are
  hand-maintained — no generator script exists.
- **Lint**: `scripts/validate-skills.js` (thin CLI) over `scripts/lib/skill-lint.js` (317 lines,
  "a single source of truth, importable and unit-testable", rules documented in
  `docs/skill-anatomy.md`). Checks: frontmatter present; `name` present and equal to the
  directory name; directory kebab-case; `description` present and ≤ `MAX_DESCRIPTION_LENGTH =
  1024`; description trigger phrasing (`DESCRIPTION_TRIGGER_NEGATE` catches "do not use this
  when…"); `REQUIRED_SECTIONS` present (with a `SECTION_EXEMPT_SKILLS` allowlist); workflow
  steps must have matching process sections; dead cross-references to unknown skills (warning).
  Siblings: `validate-commands.js`, `validate-reference-links.js`, `validate-artifact-paths.js`,
  `validate-versions.js`, each with a `-test.js` twin.
- Hooks: `hooks/session-start.sh`, `hooks/sdd-cache-{pre,post}.sh`, `hooks/simplify-ignore.sh`,
  each with a `-test.sh`. Evals: 75 files under `evals/cases/*.json` + `scripts/run-evals.js`.
  1 workflow.
- **No preference variants.** `.claude/commands/ship.md` uses "persona" for three fixed
  specialist reviewers (code-reviewer, security-auditor, test-engineer) fanned out in parallel —
  roles, not alternative profiles of one axis. `docs/comparison.md` positions Superpowers as the
  "autonomy over a long run" option, i.e. competitor framing, not a setting.

---

## Cross-cutting

| Capability | Who has it |
| --- | --- |
| Compile one source into many runtimes | rulesync (52 targets, per-feature tuples), wshobson (6 generated harnesses + capability matrix), gsd-core (16 runtime families), gstack (10 hosts via `.tmpl`), planning-with-files (11 IDE dirs by copy+verify) |
| Lint the instruction set itself | ctxlint (90 rules, token budgets, 8-axis contradiction detection), addyosmani (skill-anatomy lint), wshobson (`context_file_max_lines=150`, CI-enforced), rulesync (`doctor`, config-only) |
| Named switchable behavioural variants | **nobody, fully.** Closest: planning-with-files `.mode` (legacy/autonomous/gated + composable tokens, root-as-floor precedence); gsd-core model profiles (quality/balanced/budget/adaptive/inherit) and review depth (quick/standard/deep); gstack's five *scalar* declared-vs-inferred dimensions |
| Contradiction detection across rule files | ctxlint only, and only over eight tool-choice axes |
| Always-loaded size ratchet | ctxlint `tierAggregate: 4000` tokens; wshobson `_CONTEXT_LINES_CAP = 150` |
| Ownership lockfile for generated output | rulesync `.claude/.rulesync-hooks-lock.json` (hooks only, opt-in) |
