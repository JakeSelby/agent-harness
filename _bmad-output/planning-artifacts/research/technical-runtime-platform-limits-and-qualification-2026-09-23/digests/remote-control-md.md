# Digest: docs/remote-control.md @3020251

- source: docs/remote-control.md @3020251
- publisher: agent-harness
- pub_date: 2026-09-22
- accessed: 2026-09-23

- {claim: "Remote Control servers are a Claude Code adapter feature for macOS under launchd; Codex has no equivalent.", source: "docs/remote-control.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "A server that loses the network for ten minutes gives up, archives its sessions and deregisters its environment; re-adoption works only through bridge-pointer.json younger than a four-hour TTL naming a dead pid.", source: "docs/remote-control.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: high, class: platform-capability}
- {claim: "heal SIGTERMs the host at nine minutes of connection errors so launchd relaunches it before the give-up; heal cannot rescue an already deregistered environment.", source: "docs/remote-control.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: harness-design}
- {claim: "A --session-id reattach registers the lost environment a second time and, in 2.1.278, binds to the wrong session, so recovery stays manual.", source: "docs/remote-control.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: medium, class: version-compat}
- {claim: "Workspace trust is per exact directory (worktrees are not trusted by the parent); API keys and cloud-provider credentials do not support Remote Control.", source: "docs/remote-control.md @3020251", publisher: "agent-harness", pub_date: 2026-09-22, accessed: 2026-09-23, confidence: high, class: platform-capability}
