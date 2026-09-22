# Teardown — dossier-primary-ring-2026-09-21.md

- claim: rulesync compiles one `.rulesync/` source into 52 unique tool targets, the master list computed as the set-union of per-feature tuples rather than a hand-maintained literal.
  source: dyoshikawa/rulesync:src/types/tool-target-tuples.ts, src/types/tool-targets.ts
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync's per-feature target coverage is uneven — rules 51, skills 50, mcp 45, permissions 38, subagents 37, hooks 37, commands 35, ignore 25, checks 7.
  source: dyoshikawa/rulesync:src/types/tool-target-tuples.ts
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync installs as an npm CLI with `bin: {"rulesync": "dist/cli/index.js"}` and also exports a library build.
  source: dyoshikawa/rulesync:package.json
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync ships thirteen commands including `install` from npm/gh/apm sources, `import`, `convert`, `doctor` and `gitignore`.
  source: dyoshikawa/rulesync:src/cli/commands/
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync writes generated files rather than symlinks and derives `.gitignore`/`.gitattributes` entries via `rulesync gitignore`, CI-checked by `check:gitignore`.
  source: dyoshikawa/rulesync:src/features/
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync records which hook entries it owns in `.claude/.rulesync-hooks-lock.json` (opt-in) so hand-added hooks survive regeneration.
  source: dyoshikawa/rulesync:src/features/hooks/hooks-ownership-lock.ts
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync's `doctor` emits typed diagnostics over config only — eighteen `config/*` codes — with no token budget, no always-loaded-context cap and no contradiction detection between rules.
  source: dyoshikawa/rulesync:src/cli/commands/doctor.ts
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync has no preference variants of its own; its only configuration axis is which targets and features are enabled, and every preset/posture hit is modelling another tool's knob.
  source: dyoshikawa/rulesync:src/types/permissions.ts
  publisher: dyoshikawa/rulesync
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: rulesync is MIT-licensed with 1,457 stars, created 2025-06-18 and pushed 2026-09-21.
  source: https://api.github.com/repos/dyoshikawa/rulesync
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint is the only project in the primary ring that lints the instruction set itself, shipping 90 rules across four JSON catalogs at repo root.
  source: YawLabs/ctxlint:context-lint-rules.json, mcp-config-lint-rules.json, agent-session-lint-rules.json, agent-skill-lint-rules.json
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint reads context files but never writes config for other runtimes; its `--fix` path applies only to its own findings.
  source: YawLabs/ctxlint:src/core/fixer.ts
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint distributes as an npm binary, a composite GitHub Action, a pre-commit hook pinned to `npx` against version 0.27.2 of the npm package with `--strict`, and an MCP server mode.
  source: YawLabs/ctxlint:action.yml, .pre-commit-hooks.yaml, bin/ctxlint.mjs
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint's default token thresholds are info 1000, warning 3000, error 8000, aggregate 5000, tierBreakdown 1000, tierAggregate 4000, overridable per project via `.ctxlintrc`.
  source: YawLabs/ctxlint:src/core/checks/tokens.ts
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint's contradiction detection covers only eight hardcoded tool-choice axes (testing framework, package manager, indentation, semicolons, quotes, naming, CSS, state management), not behavioural stances.
  source: YawLabs/ctxlint:src/core/checks/contradictions.ts
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint has a `tier-tokens/hard-enforcement-missing` rule that flags an always-loaded file for using inviolable framing (NEVER / ALWAYS / DO NOT / MUST NOT).
  source: YawLabs/ctxlint:context-lint-rules.json
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint scans MEMORY.md against a stated Claude Code session-load cap of the first 200 lines / 25KB (`session/memory-index-overflow`).
  source: YawLabs/ctxlint:agent-session-lint-rules.json
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint detects dead hooks — a PreToolUse hook or permissions entry pointing at something that no longer exists — and nine classes of leaked secret in instruction content.
  source: YawLabs/ctxlint:context-lint-rules.json
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint has no preference variants; `--strict` severity escalation is its only global behavioural knob.
  source: YawLabs/ctxlint:src/core/config.ts
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: ctxlint has 9 stars and no CI workflows of its own, despite 79 vitest files and fixtures of deliberately-broken projects.
  source: YawLabs/ctxlint:.github/
  publisher: YawLabs/ctxlint
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-primary-ring-2026-09-21.md
- claim: obra/superpowers is markdown methodology plus shell scripts with no compiler, achieving multi-runtime reach by hand-committed per-host manifests all pointing at the same `skills/` directory.
  source: obra/superpowers:.claude-plugin/, .codex-plugin/, .opencode/plugins/superpowers.js
  publisher: obra/superpowers
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: superpowers has 289,730 stars — the largest in the primary ring — with no preference variants, no instruction linting and no GitHub Actions workflows.
  source: https://api.github.com/repos/obra/superpowers
  publisher: GitHub
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: traction
  via: dossier-primary-ring-2026-09-21.md
- claim: gstack installs via a 161 KB bash `./setup` installer and ships ~89 `bin/gstack-*` executables plus compiled gate binaries.
  source: garrytan/gstack:setup, scripts/build.sh
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: gstack projects to 10 hosts by generating `SKILL.md` from `SKILL.md.tmpl`, with a CI `--dry-run` freshness check and per-host `suppressedResolvers` for graceful degradation.
  source: garrytan/gstack:hosts/index.ts, scripts/gen-skill-docs.ts
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: gstack models preferences as five continuous scalar dimensions — scope_appetite, risk_tolerance, detail_preference, autonomy, architecture_care — each defaulting to 0.5, with declared-versus-inferred drift reporting, not named switchable variants.
  source: garrytan/gstack:bin/gstack-developer-profile
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: gstack infers preference values from `~/.gstack/projects/{SLUG}/question-events.jsonl` via `--derive` and flags declared-versus-inferred divergence with `--check-mismatch`.
  source: garrytan/gstack:bin/gstack-developer-profile
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: dossier-primary-ring-2026-09-21.md
- claim: gstack ships analytics binaries — `gstack-analytics`, `gstack-context-bill`, `gstack-community-dashboard` — but has no instruction-size lint; the generated-vs-committed drift check is its only content lint.
  source: garrytan/gstack:bin/
  publisher: garrytan/gstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: telemetry
  via: dossier-primary-ring-2026-09-21.md
- claim: pmstack installs by `curl | bash` into a project or `~/.claude` with `--global` and `--dry-run`, and does not project to any other runtime.
  source: RyanAlberts/pmstack:install.sh, setup
  publisher: RyanAlberts/pmstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: pmstack's `pmstack-lint` is a prompt rather than code — it walks the skill graph against the outputs directory for graph gaps and cross-artifact drift, not instruction content.
  source: RyanAlberts/pmstack:claude-skills/pmstack-lint/SKILL.md
  publisher: RyanAlberts/pmstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: pmstack's executable code is an eval harness (`bin/eval-harness.mjs`, golden baseline, `evals/pmstack-self.yaml`) with no CI workflows and no hooks.
  source: RyanAlberts/pmstack:bin/eval-harness.mjs, evals/golden/baseline.json
  publisher: RyanAlberts/pmstack
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: telemetry
  via: dossier-primary-ring-2026-09-21.md
- claim: wshobson/agents generates six harnesses from one plugin source via `tools/generate.py --harness <codex|copilot|cursor|opencode|antigravity|pi>` driven from a Makefile.
  source: wshobson/agents:tools/generate.py
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: wshobson/agents keeps a per-harness capability matrix as data — including `context_file_max_lines`, `skill_body_max_bytes`, `hooks`, `parallel_agents` — described as the single source of truth for adapters, docs generation and plugin-eval.
  source: wshobson/agents:tools/adapters/capabilities.py
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: wshobson/agents enforces an authoring cap of `_CONTEXT_LINES_CAP = 150` in CI and hard-truncates Codex skills at `_CODEX_SKILL_CAP = 8 * 1024` bytes.
  source: wshobson/agents:tools/adapters/capabilities.py
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
  contradicts: ctxlint's default token thresholds are
- claim: wshobson/agents has no preference variants, only per-command flags such as `[--security-focus] [--performance-critical] [--strict-mode]`.
  source: wshobson/agents:plugins/comprehensive-review/commands/full-review.md
  publisher: wshobson/agents
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: anthropics/skills declares no repo-level license and each skill ships a LICENSE.txt forbidding extraction, reproduction and derivative works, so it is excluded under a permissive-commercial stance and must not be vendored.
  source: anthropics/skills:skills/<name>/LICENSE.txt
  publisher: Anthropic, PBC
  pub_date: 2025-09
  accessed: 2026-09-21
  confidence: high
  class: licensing
  via: dossier-primary-ring-2026-09-21.md
- claim: anthropics/skills is pure content — 19 skills, no CLI, no installer, no lint, no hooks, no CI workflows — and its spec file is a 3-line stub redirecting to agentskills.io.
  source: anthropics/skills:spec/agent-skills-spec.md
  publisher: Anthropic, PBC
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: planning-with-files is the primary ring's only real mode system, with a `.mode` marker file carrying composable tokens written by `init-session.sh --autonomous` / `--gated`, yielding legacy, autonomous and gated profiles.
  source: OthmanAdi/planning-with-files:scripts/init-session.sh, scripts/inject-plan.sh
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: planning-with-files treats a root `.mode` as a floor, not a default: a slug may opt into autonomous/gated where the root left it unset but cannot opt out of what the root committed.
  source: OthmanAdi/planning-with-files:scripts/inject-plan.sh
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: planning-with-files degrades honestly on weaker hosts — hosts without a blocking Stop hook get autonomous mode but the completion gate degrades to a notification.
  source: OthmanAdi/planning-with-files:skills/planning-with-files/
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: planning-with-files projects to 11 IDE directories by copy with a `--verify` drift check that exits 1 on drift, explicitly never syncing per-IDE `SKILL.md` frontmatter or IDE-specific hooks.
  source: OthmanAdi/planning-with-files:scripts/sync-ide-folders.py
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: planning-with-files' `plan-doctor.sh` self-checks the mechanism (plan resolution, hook injection, attestation, install surfaces, hook wall-clock) rather than linting instruction content.
  source: OthmanAdi/planning-with-files:scripts/plan-doctor.sh
  publisher: OthmanAdi/planning-with-files
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core projects to 16 runtime families from a "Skill Surface Budget Module" that is the single source of truth for which skills and agents are written to runtime config dirs (ADR-0011).
  source: open-gsd/gsd-core:src/install-profiles.cts, gsd-core/bin/shared/runtime-aliases.manifest.json
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core ships named model profiles — quality, balanced, budget, adaptive, plus an `inherit` sentinel — mapping each agent to a model, the nearest match in the primary ring to a cost posture.
  source: open-gsd/gsd-core:src/model-profiles.cts, src/model-catalog.cts
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core's review depth is a named three-value axis (`quick | standard | deep`) resolved flag → per-path rule → config → default `standard`, auto-downgrading deep to standard past a large-scope file threshold.
  source: open-gsd/gsd-core:src/code-review-depth.cts
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core renders reasoning effort per runtime, with Claude supporting `low|medium|high|xhigh|max` and clamping `minimal` to `low`.
  source: open-gsd/gsd-core:src/model-profiles.cts
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: capability
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core runs 65 lint/check scripts plus 11 custom ESLint rules covering contract, alias, identity and phase-id drift, mutation-score ratchet and coverage gates, but has no always-loaded token budget.
  source: open-gsd/gsd-core:scripts/
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: gsd-core gates secrets with `scripts/secret-scan.sh --diff origin/main --strict` and a `.secretscanignore` requiring an annotation format.
  source: open-gsd/gsd-core:scripts/secret-scan.sh
  publisher: open-gsd/gsd-core
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: addyosmani/agent-skills lints skill anatomy in importable code — frontmatter presence, name equal to directory name, kebab-case, description ≤1024 chars, trigger phrasing, required sections, dead cross-references.
  source: addyosmani/agent-skills:scripts/lib/skill-lint.js
  publisher: addyosmani/agent-skills
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: validation
  via: dossier-primary-ring-2026-09-21.md
- claim: addyosmani/agent-skills maintains its Gemini `.toml` command mirrors by hand — no generator script exists — despite having marketplace manifests for four runtimes.
  source: addyosmani/agent-skills:.gemini/commands/
  publisher: addyosmani/agent-skills
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: packaging
  via: dossier-primary-ring-2026-09-21.md
- claim: addyosmani/agent-skills has no preference variants; its `ship.md` "personas" are three fixed specialist reviewer roles fanned out in parallel.
  source: addyosmani/agent-skills:.claude/commands/ship.md
  publisher: addyosmani/agent-skills
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: high
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
- claim: across the ten primary-ring projects nobody ships named switchable behavioural variants fully; the closest are planning-with-files' `.mode`, gsd-core's model profiles and review depth, and gstack's five scalar dimensions.
  source: dossier-primary-ring-2026-09-21.md (cross-cutting table)
  publisher: internal research import
  pub_date: 2026-09
  accessed: 2026-09-21
  confidence: medium
  class: preference-variants
  via: dossier-primary-ring-2026-09-21.md
  contradicts: LynxPrompt is the only project

## Leads

- agentskills.io/specification — the spec anthropics/skills redirects to; likely the de facto interop contract for skills.
- rulesync's `hooks-ownership-lock.json` pattern as a model for agent-harness owning generated files without clobbering hand edits.
- ctxlint's `.ctxlintrc tokenThresholds` as the closest existing analogue to the always-loaded ratchet; worth checking whether agent-harness could ship a ctxlint config rather than its own linter.
- wshobson's `capabilities.py` matrix as a data shape for per-runtime graceful degradation.
- planning-with-files' root-as-floor precedence rule (#238) as prior art for variant composition across scopes.
- gsd-core ADR-0011 (Skill Surface Budget) and `src/prompt-budget.cts` / `context-utilization.cts`.

## Not found

- Any project with a named behavioural-stance axis (autonomy, testing, commits, delegation) selectable and composed into generated config — in the primary ring.
- Any contradiction detection over behavioural stances rather than tool choices.
- Any per-rule firing measurement, hit rate, or detector-to-rule binding in any of the ten.
- Any agreed number for an always-loaded size cap; the two that exist (ctxlint 4000 tokens tier-aggregate, wshobson 150 lines) are not comparable units.
- Star counts appear anomalous for several repos; the import does not flag or reconcile them.
