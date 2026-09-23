# Digest: docs/role-workers.md @3020251

- source: docs/role-workers.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "Read-only and planner roles run as separate native CLI processes, not native subagent threads; hooks reject direct native launches of constrained roles.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Spawn guards are best effort: a brief fingerprint (identical, first 400 chars, or 85% similar) and a harness-role: marker are refused; unreadable session state means no new refusal.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Read confinement is enforced on Claude Code (Read/Grep/Glob against --add-dir roots) and advisory on Codex, whose read-only sandbox can read any native-permitted path.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "No isolated worker reaches the network; a dimension needing the live web goes to an in-session band worker subject to session permissions and the search budget.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "A review role mounts about 30,800 tokens (planner about 43,800) against a recorded, unenforced 50,000 budget, down from about 1,073,900 when the whole checkout was a root.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: cost-measurement}
- {claim: "Codex worker: fresh home, read-only sandbox, no approvals, no inherited env; delegation, apps, remote plugins, memory, hosted search disabled. Claude worker: safe mode, empty MCP config, Read/Grep/Glob only.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "A completed worker result does not certify findings or qualify the client; native acceptance must prove prohibited shell and patch writes do not run and redelegation cannot widen access.", source: "docs/role-workers.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
