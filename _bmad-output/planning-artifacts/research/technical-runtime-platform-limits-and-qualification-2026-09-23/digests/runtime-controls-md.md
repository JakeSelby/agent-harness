# Digest: docs/runtime-controls.md @3020251

- source: docs/runtime-controls.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "One shared policy engine consumes normalized events; a deny wins over allow or rewrite. Codex cannot pause with an ask decision, so a request needing confirmation is denied with its reason.", source: "docs/runtime-controls.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "Hook registration is not activation: Codex requires native trust for the current hooks content. Hosted search and continuation through a running shell are not universally intercepted; hooks are not a sandbox substitute.", source: "docs/runtime-controls.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "Direct native role defaults are not confinement: Codex can reapply parent permission overrides; constrained roles route to isolated CLI workers.", source: "docs/runtime-controls.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "Unnamed-spawn routing is session-scoped: a session routes only to workers its registry held at start or later announced by the runtime; a headless session never reloads; failure to answer leaves the spawn unrouted, never refused.", source: "docs/runtime-controls.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "Codex cumulative token snapshots are counted once; missing measurements stay null; transcript adapters cannot observe nested tool calls absent from the transcript.", source: "docs/runtime-controls.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
