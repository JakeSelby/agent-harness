# Digest: issues #429, #498, #513, #324 and PRs #248, #254, #578

- claim: #429 (open): zero subagent spawns in 19 headless runs; if the stance does not fire, the harness pays about 20% of every run in standing context for a mechanism that never runs; context trimming has a ceiling of about 25% of the prefix, so the threshold needs work removed.
  source: https://github.com/JakeSelby/agent-harness/issues/429
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: medium
  class: mechanism-failure

- claim: #498: with CLAUDE_CONFIG_DIR set, the test suite's sync tests wrote the harness into that real profile and reported FAILED (failures=22); unset, 704 tests pass. The defect is test isolation, not runtime precedence.
  source: https://github.com/JakeSelby/agent-harness/issues/498
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: mechanism-failure

- claim: #513 (open): delegation fired zero times in forty benchmark runs; the counterfactual from stored transcripts puts break-even at 4.8 to 5.9 calls against runs of 17 to 45 on three of four tasks; the tiering hook fires only once a spawn is attempted, so a PostToolUse nudge is proposed, with acceptance of spawns in 3 of 4 micro runs and none on a two-file task.
  source: https://github.com/JakeSelby/agent-harness/issues/513
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: measurement

- claim: #324: the brief-without-cap rate was 3.2 / 3.6 / 3.2 per 100 turns before / during / after brief-guard on one machine.
  source: https://github.com/JakeSelby/agent-harness/issues/324
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-21
  accessed: 2026-09-23
  confidence: high
  class: mechanism-failure

- claim: #248 gave each cost variant per-role model class, effort and soft budget, with budgets set at the measured 90-day p75 per role and band budgets provisional; verifier roles are `posture: fixed`; nothing consumed the table at merge.
  source: https://github.com/JakeSelby/agent-harness/pull/248
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-20
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #254 made brief-guard append the expected spend in output tokens and tool calls to every priced brief, denying nothing.
  source: https://github.com/JakeSelby/agent-harness/pull/254
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-20
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: #578: on Claude Code 2.1.280 with harness 0.12.0, four headless runs showed Workflow-tool agents never pass the Agent hook chain (no band routing, no brief-guard, no role deny); the ledger still records them but with no tool_use_id, so every workflow row reads as an unrerouted spawn.
  source: https://github.com/JakeSelby/agent-harness/pull/578
  publisher: agent-harness (GitHub)
  pub_date: 2026-09-23
  accessed: 2026-09-23
  confidence: high
  class: version
