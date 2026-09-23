# Digest: docs/compatibility.md @3020251

- source: docs/compatibility.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-23
- accessed: 2026-09-23

- {claim: "v0.12.0 carries no native qualification: no client has evidence for this source and none is marked required for release; the v0.11.1 stable floor is the last one qualifying the CLIs on macOS and Linux.", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: version-compat}
- {claim: "A capability is qualified for a client only when the client is qualified AND a native acceptance case exercising that capability passed; today no adapter names an acceptance case, so every capability cell reads unqualified.", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Tier restriction is enforced on Claude Code CLI and VS Code (tier-agent-spawns.py rewrites spawns) and advisory on every Codex surface (rewrite gated behind runtime == claude-code) and on the plugin-marketplace install (no hooks).", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Evidence is invalidated per target: shared runtime source minus other runtimes adapter dirs, with bindings.json, capabilities.json and worker.py carved back as shared; only hook.py is runtime-private. Per-case scoping is not implemented and waits on an owner decision (#333).", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Evidence cannot be reused for another client or harness version; its source commit must be an ancestor of the release with no later change under the target invalidation paths; linked failed/unverified results block qualification.", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "The runner appends each finished case to a durable log so a killed round costs one case; --from-progress rebuilds a partial record.", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: high, class: harness-design}
- {claim: "Native Windows is unsupported; WSL2 is not qualified.", source: "docs/compatibility.md @3020251", publisher: "agent-harness", pub_date: 2026-09-23, accessed: 2026-09-23, confidence: medium, class: version-compat}
