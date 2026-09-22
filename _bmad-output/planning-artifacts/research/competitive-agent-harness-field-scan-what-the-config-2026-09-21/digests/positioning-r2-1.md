# positioning-r2-1 — how rivals evidence and publish capability

- claim: planning-with-files' headline "3/3 blind A/B wins" is three comparator agents scoring with_skill vs without_skill outputs on 3 of its 5 eval tasks, not a competitor comparison.
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: "Blind" means only that the comparator agents did not know which output was with_skill, with A/B assignment randomized; the judges are LLM agents, not humans — "Three independent comparator agents evaluated pairs of outputs **without knowing which was with_skill vs without_skill**. Assignment was randomized".
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: The Test 1 substrate is 30 objectively-verifiable file/section assertions over 5 tasks, one run per arm, executor claude-sonnet-4-6 — "All assertions are **objectively verifiable** (file existence, section headers, field counts)" — so n=1 per cell and the win is workflow fidelity, not planning quality.
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: The project self-classifies as an "**encoded preference skill** (not capability uplift). Claude can plan without the skill" — the A/B measures conformance to its own format, and it discloses a cost: "The skill uses ~68% more tokens and ~17% more time on average."
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-03
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: Measurement is ongoing, not one-time: five tests across v2.21.0 (2026-03-06), v3.2.0 (2026-07-03) and v3.4.0 (2026-07-06), with Test 3 "Not run in this cycle" and a v2 docket of three designed-but-unrun tasks.
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: Test 5 is a 7-arm, 77-cell competitive benchmark (native, filesystem, naive-plan, pwf v3.4.0, superpowers, spec-kit, memory-bank) on claude-opus-4-8 with deterministic graders — "No LLM grades anything in this test" — but is labelled "an internal v1: the tasks are harness-authored (a disclosed limitation)".
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: The task set and raw runs are NOT published — "all 77 raw run directories ... live in the benchmark workspace, not tracked in this repo" and Test 1's raw data is "in eval-test copy, not tracked in main repo" — so no third party can reproduce either result.
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: claim-gap

- claim: The doc states its own limits in a dedicated section — "What this test does not measure: Trigger rates under varied natural phrasing ... Long-horizon drift and mid-task distractors ... Underspecified-task brainstorming, where superpowers is expected to win. Plan quality as judged output (needs a cross-family jury before it can be reported). Cross-IDE behavior (Claude Code only). Multi-day horizons. None of the above is claimed."
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: It also publishes results that cut against it: unforced triggering was only "2/3" (O1) and "3/5" (O2) for pwf versus 8/8 for always-loaded project rules, and it discloses a grader bug that "had falsely zeroed superpowers' forced-mode process metrics", re-graded before publication.
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: A functional-verification test (Test 4) found "2 of 6 mechanisms were broken on Windows, silently" — session-catchup.py and inject-plan.sh — because "tests/test_path_fix.py contained a working reimplementation of the correct fix but never imported or exercised the actual shipped script".
  source: OthmanAdi/planning-with-files:docs/evals.md
  publisher: planning-with-files
  pub_date: 2026-07
  accessed: 2026-09-21
  confidence: high
  class: evidence-method

- claim: wshobson/agents publishes a per-harness capability matrix covering six harnesses (Claude Code, Codex, Cursor, OpenCode, Antigravity, Pi) against 14 capability rows, generated from code: "This file mirrors the capability matrix in `tools/adapters/capabilities.py`. Edit there; regenerate via `make docs`."
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: The tracked capability rows are, verbatim: "Skills (SKILL.md native) | Subagents (markdown native) | Slash commands | Plugin marketplace | Parallel subagents | Per-agent tool allowlist | `TodoWrite` tool | `Task`/`Agent` spawn tool | MCP servers | Lifecycle hooks | Context file | Context file recommended cap | Skill body hard cap | Bare model aliases", with column headings "Capability | Claude Code | Codex | Cursor | OpenCode | Antigravity | Pi".
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: Unsupported cells are marked with a bare em-dash rather than prose: Plugin marketplace is "—" for Codex, OpenCode and Pi; `TodoWrite` is "—" for Codex, Cursor, Antigravity and Pi; Lifecycle hooks are "—" for Codex and Cursor.
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: Claude Code is the only "source-of-truth" harness; Codex and Cursor are partly committed (registries pointing at source `plugins/`), while OpenCode, Antigravity and Pi are wholly gitignored generated trees — "Native install is **lean**: only small JSON registries ... are committed. The large transformed skill/agent trees stay gitignored — regenerate them locally."
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: The doc pairs the matrix with a second "Graceful degradation" table naming the exact rewrite per source pattern per harness (e.g. `tools: Read, Grep` is "dropped; `sandbox_mode = \"read-only\"` heuristic" on Codex, "dropped (Cursor doesn't honor)" on Cursor) plus "no equivalent — leave as-is" for `TodoWrite` in body, so a reader sees the fallback, not just the gap.
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: The doc discloses adoption friction honestly per harness — "**Antigravity** — no one-step-from-URL install (the lean tradeoff)", the same for OpenCode and Pi — and warns about double-discovery: "If you install globally with `make install-pi` and also run `pi` inside the clone, Pi sees every skill twice and warns on each name."
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: high
  class: capability-matrix

- claim: The harnesses doc carries no explicit "limits of this document" section and no measurement of whether the generated artifacts actually work per harness beyond `make smoke-test` (discovery + spec validation); its stated limits are per-row caveats and install gotchas only.
  source: wshobson/agents:docs/harnesses.md
  publisher: claude-agents
  pub_date: unknown
  accessed: 2026-09-21
  confidence: medium
  class: claim-gap

## Leads

- Round 3: `wshobson/agents:docs/authoring.md` — the "portable-content style guide for plugin authors", the closest analogue to a harness-usable-by-non-authors doc.
- Round 3: `wshobson/agents:tools/adapters/capabilities.py` — the matrix as executable data; the pattern of generating the adoption doc from code rather than maintaining prose.
- Round 3: planning-with-files' `docs/benchmark/index.html` animated benchmark summary — the presentation layer on top of evals, a distinct adoption artifact.
- Round 3: whether any project publishes its task corpus; neither of these two does.

## Not found

- planning-with-files' published task set or raw runs (explicitly untracked in both repos referenced).
- Any human judge anywhere in planning-with-files' evidence; all judging is agent-run or script-run.
- A publication date in `wshobson/agents:docs/harnesses.md` (no date anywhere in the file).
- Any per-harness verification that generated artifacts execute correctly, in either source.
