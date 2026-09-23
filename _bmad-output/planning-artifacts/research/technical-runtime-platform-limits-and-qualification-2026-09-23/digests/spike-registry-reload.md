# Digest: docs/spikes/2026-09-22-registry-reload.md @3020251

- source: docs/spikes/2026-09-22-registry-reload.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-22
- accessed: 2026-09-23

- {claim: "Claude Code reloads its agent registry mid-session only in interactive sessions (probes on 2.1.278-2.1.280); every headless probe failed with Agent type not found.", source: "docs/spikes/2026-09-22-registry-reload.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Each session writes an agent_listing_delta attachment at start and one per reload; FileChanged fires in both session kinds and is not a safe reload signal; SessionStart model field is not a gate.", source: "docs/spikes/2026-09-22-registry-reload.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: platform-capability}
- {claim: "Codex was not exercised: it has no spawn hook to consume a reload signal.", source: "docs/spikes/2026-09-22-registry-reload.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: high, class: platform-capability}
