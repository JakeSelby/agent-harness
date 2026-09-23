# Digest: compatibility/catalog.json and compatibility/evidence/ @3020251

- source: compatibility/catalog.json and compatibility/evidence/ @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "Catalog 0.12.0 is released with 12 required_cases; all eight Claude Code and Codex client rows are unqualified with required_for_release false and no evidence linked; Cursor and Grok are planned.", source: "compatibility/catalog.json and compatibility/evidence/ @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: version-compat}
- {claim: "The evidence directory holds 19 native records for 0.9.0-0.11.1 (Claude Code 2.1.273/2.1.278; Codex 0.154.0-alpha.6.2 to 0.155.1), all cases passed, plus 12 model-free lifecycle records; 0.11.1 records cover 11 cases including bmad-workflow, not the current framework-spawn-routing and spawn-confinement.", source: "compatibility/catalog.json and compatibility/evidence/ @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: version-compat}
- {claim: "Limitation: Codex raises none of UserPromptSubmit, SubagentStart or SubagentStop, so the usage feed is a Claude Code capability.", source: "compatibility/catalog.json and compatibility/evidence/ @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Limitation: on Codex output-filter rewrites are never applied (#292); under Codex auto permissions an isolated worker launched from a sandboxed turn has no network and stalls until its deadline (#293).", source: "compatibility/catalog.json and compatibility/evidence/ @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Limitation: from 0.13.0 spawn-hook confinement covers only frameworks a descriptor in policy/integrations/ covers; a rewritten brief still runs unconfined; one confined Claude Code Linux run needed five attempts (#291).", source: "compatibility/catalog.json and compatibility/evidence/ @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: harness-design}
