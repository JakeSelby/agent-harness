# Digest: docs/qualification-runbook.md @3020251

- source: docs/qualification-runbook.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "The runner refuses a dirty tree; every probe is one short headless paid turn on the cheapest model; smoke_tier.py spends no model turn and is advisory, never qualification.", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "qualification_round.py runs the smoke tier once, then the runner per target from a frozen clone; it exits non-zero unless every case of every target passed and collects all defects before any fix.", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Execution class defaults to standard and assessment class to strong; an assessment class weaker than strong, or an execution class resolving to the assessor model, is refused before any client launches.", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Workers ran 0.7x-1.8x their 82K output budget, so four targets cost 230K-590K output tokens per round, mostly authoring rather than judgement (#338 estimate, not a measurement).", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: cost-measurement}
- {claim: "No Codex round has been driven through the runner; every Codex verdict is reported unverified until a hand qualification is compared and --home-confirmed passed.", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Disposable homes rely on CLAUDE_CONFIG_DIR and CODEX_HOME moving the whole native configuration home; credentials pass by variable name only.", source: "docs/qualification-runbook.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
