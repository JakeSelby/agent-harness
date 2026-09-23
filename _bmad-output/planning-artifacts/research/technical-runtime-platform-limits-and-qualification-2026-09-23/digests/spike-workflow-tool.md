# Digest: docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251

- source: docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-22
- accessed: 2026-09-23

- {claim: "On Claude Code 2.1.280 a Workflow script agent() call produces no Agent tool call, so tier-agent-spawns, brief-guard and the constrained-role refusal never run; no hook matcher covers Workflow.", source: "docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "agent() accepts model, effort and agentType; agentType reviewer ran the read-only role in session on its definition model with no isolated worker.", source: "docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "usage-log records workflow agents as subagent rows with the workflow id but empty tool_use_id, so reroute marking never joins; 1,657 historical workflow rows all read as unrerouted.", source: "docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: harness-design}
- {claim: "Workflow fan-out is one level deep: workflow-subagent disallows the Agent tool. Whether PreToolUse fires on a workflow agent own Bash is not measured.", source: "docs/spikes/2026-09-22-workflow-tool-band-routing-and-ledger.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: platform-capability}
